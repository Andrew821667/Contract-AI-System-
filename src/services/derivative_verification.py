# -*- coding: utf-8 -*-
"""
Derivative Verification Service — трёхэтапная сверка производного документа
с основным договором.

Этапы:
1. **Реквизиты** — rule-based:
   - В ребёнке должен быть упомянут номер/дата parent.
   - Контрагенты совпадают (или ребёнок — подмножество сторон parent).
   - Валюта согласуется.
2. **Противоречия** — LLM-анализ: найти условия в child, противоречащие parent.
   Если LLM недоступен или сторонний дочерний документ (акт/приложение) — этап
   помечается skipped.
3. **Diff** — DocumentDiffService.compare_documents по text-режиму над parsed_text.
   Имеет смысл для доп.соглашений / редакций parent; для актов/приложений
   часто нерелевантен → возвращаем общий список изменений без агрессивной
   интерпретации.

Возвращает DerivativeVerification (Base SQLAlchemy), сохранённый в БД.
"""
from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

from loguru import logger
from sqlalchemy.orm import Session

from src.models import Contract
from src.models.auth_models import User
from src.models.contract_relations_models import (
    ContractRelation,
    DerivativeVerification,
)
from src.services.main_contract_finder import extract_contract_refs


# relation_types, для которых diff обычно полезен
_DIFF_RELEVANT = {"supplementary_agreement", "addendum", "termination", "custom"}
# relation_types, для которых LLM-анализ противоречий полезен
_CONTRADICTIONS_RELEVANT = {
    "supplementary_agreement",
    "specification",
    "addendum",
    "termination",
    "custom",
}


class DerivativeVerificationService:
    """Сервис трёхэтапной сверки. Не делает LLM-вызовы прямо в __init__."""

    def __init__(self, max_diff_lines: int = 200, max_llm_chars: int = 12_000) -> None:
        self.max_diff_lines = max_diff_lines
        self.max_llm_chars = max_llm_chars

    # ── Public API ──────────────────────────────────────────────────────────

    def verify(
        self,
        db: Session,
        relation: ContractRelation,
        current_user: Optional[User] = None,
    ) -> DerivativeVerification:
        started = time.time()

        parent: Optional[Contract] = (
            db.query(Contract).filter(Contract.id == relation.parent_contract_id).first()
        )
        child: Optional[Contract] = (
            db.query(Contract).filter(Contract.id == relation.child_contract_id).first()
        )
        if not parent or not child:
            return self._save(
                db=db,
                relation=relation,
                parent_id=relation.parent_contract_id,
                child_id=relation.child_contract_id,
                overall="error",
                status="failed",
                requisites=None,
                contradictions=None,
                diff=None,
                error="Не удалось загрузить parent или child из БД",
                duration_ms=0,
                created_by=current_user.id if current_user else None,
            )

        requisites = self._verify_requisites(parent, child)
        contradictions, llm_model, contr_status = self._verify_contradictions(
            db, parent, child, relation
        )
        diff = self._verify_diff(parent, child, relation)

        overall = self._compute_overall(requisites, contradictions, diff)

        status = "completed"
        if contr_status == "skipped" and any(s.get("severity") == "critical" for s in requisites["mismatches"]):
            status = "partial"

        return self._save(
            db=db,
            relation=relation,
            parent_id=parent.id,
            child_id=child.id,
            overall=overall,
            status=status,
            requisites=requisites,
            contradictions=contradictions,
            diff=diff,
            llm_model=llm_model,
            duration_ms=int((time.time() - started) * 1000),
            created_by=current_user.id if current_user else None,
        )

    # ── Step 1: requisites ──────────────────────────────────────────────────

    def _verify_requisites(self, parent: Contract, child: Contract) -> Dict[str, Any]:
        mismatches: List[Dict[str, Any]] = []

        # 1) Поиск ссылки на parent в тексте child
        refs = extract_contract_refs(child.parsed_text or "")

        if parent.contract_number:
            child_numbers = [n.strip().lower() for n in refs.numbers if n]
            parent_n = parent.contract_number.strip().lower()
            number_found = any(parent_n == n or parent_n in n or n in parent_n for n in child_numbers)
            if not number_found:
                mismatches.append({
                    "field": "contract_number",
                    "severity": "warning",
                    "parent_value": parent.contract_number,
                    "child_value": refs.numbers or None,
                    "message": (
                        "В производном документе не найдено указание на номер основного договора"
                        if not refs.numbers
                        else "В производном документе указан другой номер договора"
                    ),
                })

        if parent.contract_date:
            parent_d = parent.contract_date.date()
            child_dates = [d.date() for d in refs.dates]
            if child_dates and parent_d not in child_dates:
                mismatches.append({
                    "field": "contract_date",
                    "severity": "warning",
                    "parent_value": parent.contract_date.isoformat(),
                    "child_value": [d.isoformat() for d in child_dates],
                    "message": "Дата договора в производном документе не совпадает с основным",
                })

        # 2) Контрагенты
        parent_cps = {p.get("counterparty_id") for p in (parent.parties_summary or []) if p.get("counterparty_id")}
        child_cps = {p.get("counterparty_id") for p in (child.parties_summary or []) if p.get("counterparty_id")}
        if parent_cps and child_cps:
            common = parent_cps & child_cps
            if not common:
                mismatches.append({
                    "field": "counterparties",
                    "severity": "critical",
                    "parent_value": list(parent_cps),
                    "child_value": list(child_cps),
                    "message": "Контрагенты основного и производного документа не пересекаются",
                })
            elif child_cps - parent_cps:
                mismatches.append({
                    "field": "counterparties",
                    "severity": "info",
                    "parent_value": list(parent_cps),
                    "child_value": list(child_cps),
                    "message": "В производном документе появились новые контрагенты",
                })

        # 3) Валюта
        if parent.currency and child.currency and parent.currency != child.currency:
            mismatches.append({
                "field": "currency",
                "severity": "warning",
                "parent_value": parent.currency,
                "child_value": child.currency,
                "message": "Валюты основного и производного документов отличаются",
            })

        # 4) Период действия (если у child указан и выходит за рамки parent)
        if parent.effective_to and child.contract_date and child.contract_date > parent.effective_to:
            mismatches.append({
                "field": "effective_period",
                "severity": "warning",
                "parent_value": parent.effective_to.isoformat(),
                "child_value": child.contract_date.isoformat(),
                "message": "Производный документ датирован после окончания действия основного договора",
            })

        return {"ok": len(mismatches) == 0, "mismatches": mismatches}

    # ── Step 2: contradictions (LLM) ────────────────────────────────────────

    def _verify_contradictions(
        self,
        db: Session,
        parent: Contract,
        child: Contract,
        relation: ContractRelation,
    ) -> tuple[Dict[str, Any], Optional[str], str]:
        """Возвращает (contradictions_dict, llm_model_name, status)."""
        if relation.relation_type not in _CONTRADICTIONS_RELEVANT:
            return (
                {
                    "count": 0,
                    "items": [],
                    "skipped": True,
                    "reason": f"Для типа '{relation.relation_type}' анализ противоречий не применяется",
                },
                None,
                "skipped",
            )

        parent_text = (parent.parsed_text or "").strip()
        child_text = (child.parsed_text or "").strip()
        if not parent_text or not child_text:
            return (
                {
                    "count": 0,
                    "items": [],
                    "skipped": True,
                    "reason": "Текст одного из документов не извлечён",
                },
                None,
                "skipped",
            )

        try:
            from src.services.llm_gateway import LLMGateway
            gateway = LLMGateway()
        except Exception as exc:
            logger.warning(f"LLMGateway init failed: {exc}")
            return (
                {"count": 0, "items": [], "skipped": True, "reason": "LLM недоступен"},
                None,
                "skipped",
            )

        # Усечём тексты, чтобы влезть в контекст
        p_text = parent_text[: self.max_llm_chars]
        c_text = child_text[: self.max_llm_chars]

        custom_hint = ""
        if relation.relation_type == "custom" and (relation.custom_label or relation.custom_prompt):
            custom_hint = (
                f"\nТип документа: {relation.custom_label or '(не указан)'}.\n"
                f"Доп. инструкция: {relation.custom_prompt or '(нет)'}\n"
            )

        prompt = f"""Ты — юрист, проверяешь производный документ на противоречия с основным договором.

ОСНОВНОЙ ДОГОВОР (parent):
\"\"\"{p_text}\"\"\"

ПРОИЗВОДНЫЙ ДОКУМЕНТ (child, тип: {relation.relation_type}):{custom_hint}
\"\"\"{c_text}\"\"\"

Найди условия в производном документе, которые ПРОТИВОРЕЧАТ основному, либо выходят за рамки
полномочий, предоставленных основным. Верни СТРОГО валидный JSON в формате:
{{
  "items": [
    {{
      "clause": "цитата из child (1-2 предложения)",
      "parent_reference": "соответствующее условие из parent или null",
      "severity": "critical|warning|info",
      "rationale": "краткое объяснение противоречия"
    }}
  ]
}}
Если противоречий нет — верни {{"items": []}}.
"""

        try:
            data = gateway.call(
                prompt=prompt,
                response_format="json",
                use_cache=True,
                db_session=db,
            )
            items = data.get("items", []) if isinstance(data, dict) else []
            llm_model = getattr(gateway, "model", None) or getattr(gateway, "provider", None)
            return (
                {"count": len(items), "items": items, "skipped": False},
                llm_model,
                "completed",
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"LLM contradictions failed: {exc}")
            return (
                {
                    "count": 0,
                    "items": [],
                    "skipped": True,
                    "reason": f"Ошибка LLM: {exc}",
                },
                None,
                "skipped",
            )

    # ── Step 3: diff ────────────────────────────────────────────────────────

    def _verify_diff(
        self,
        parent: Contract,
        child: Contract,
        relation: ContractRelation,
    ) -> Dict[str, Any]:
        if relation.relation_type not in _DIFF_RELEVANT:
            return {
                "skipped": True,
                "reason": f"Для типа '{relation.relation_type}' diff обычно нерелевантен",
                "total_changes": 0,
                "by_category": {},
                "items": [],
            }

        parent_text = (parent.parsed_text or "").strip()
        child_text = (child.parsed_text or "").strip()
        if not parent_text or not child_text:
            return {
                "skipped": True,
                "reason": "Текст одного из документов не извлечён",
                "total_changes": 0,
                "by_category": {},
                "items": [],
            }

        try:
            from src.services.document_diff_service import DocumentDiffService
            svc = DocumentDiffService()
            changes = svc.compare_documents(parent_text, child_text, mode="text")
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"DocumentDiffService failed: {exc}")
            return {
                "skipped": True,
                "reason": f"Ошибка diff: {exc}",
                "total_changes": 0,
                "by_category": {},
                "items": [],
            }

        # Убираем шум (короткие пробелы), агрегируем по категориям
        by_category: Dict[str, int] = {}
        items: List[Dict[str, Any]] = []
        for ch in changes:
            content = (ch.get("new_content") or ch.get("old_content") or "").strip()
            if len(content) < 3:
                continue
            cat = ch.get("change_category", "textual")
            by_category[cat] = by_category.get(cat, 0) + 1
            if len(items) < self.max_diff_lines:
                items.append({
                    "change_type": ch.get("change_type"),
                    "change_category": cat,
                    "old_content": ch.get("old_content"),
                    "new_content": ch.get("new_content"),
                })

        return {
            "skipped": False,
            "total_changes": sum(by_category.values()),
            "by_category": by_category,
            "items": items,
            "truncated": sum(by_category.values()) > len(items),
        }

    # ── Aggregation ─────────────────────────────────────────────────────────

    @staticmethod
    def _compute_overall(
        requisites: Dict[str, Any],
        contradictions: Dict[str, Any],
        diff: Dict[str, Any],
    ) -> str:
        # critical если есть critical в реквизитах или противоречиях
        for m in requisites.get("mismatches", []):
            if m.get("severity") == "critical":
                return "critical"
        for c in contradictions.get("items", []) if not contradictions.get("skipped") else []:
            if c.get("severity") == "critical":
                return "critical"

        if requisites.get("mismatches") or (contradictions.get("count") or 0) > 0:
            return "warnings"
        # diff сам по себе — не повод для warnings; это нормальное состояние редакции
        return "ok"

    # ── Persistence ─────────────────────────────────────────────────────────

    @staticmethod
    def _save(
        *,
        db: Session,
        relation: ContractRelation,
        parent_id: str,
        child_id: str,
        overall: str,
        status: str,
        requisites: Optional[Dict[str, Any]],
        contradictions: Optional[Dict[str, Any]],
        diff: Optional[Dict[str, Any]],
        error: Optional[str] = None,
        llm_model: Optional[str] = None,
        duration_ms: int = 0,
        created_by: Optional[str] = None,
    ) -> DerivativeVerification:
        verif = DerivativeVerification(
            relation_id=relation.id,
            parent_contract_id=parent_id,
            child_contract_id=child_id,
            overall_assessment=overall,
            requisites=requisites,
            contradictions=contradictions,
            diff=diff,
            llm_model=llm_model,
            duration_ms=duration_ms,
            status=status,
            error=error,
            created_by=created_by,
        )
        db.add(verif)
        db.commit()
        db.refresh(verif)
        return verif


__all__ = ["DerivativeVerificationService"]
