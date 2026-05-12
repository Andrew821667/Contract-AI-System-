# -*- coding: utf-8 -*-
"""
Main Contract Finder — поиск основного договора для производного документа.

При загрузке доп.соглашения / спецификации / приложения / акта мы по тексту
производного документа пытаемся найти, к какому основному договору он относится.

Стратегия:
1. Из текста ребёнка извлечь реквизиты — номер договора, дату, ИНН сторон.
2. Сделать SQL-выборку кандидатов из contracts (только основные, в пределах
   организации/пользователя), у которых хоть какой-то атрибут совпадает.
3. Отскорить совпадения, вернуть top-N с confidence ∈ [0..1].

Возвращаем кандидатов; фактическая привязка делается отдельным API-вызовом
после подтверждения пользователя.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Iterable, List, Optional

from loguru import logger
from sqlalchemy import or_
from sqlalchemy.orm import Session

from src.models import Contract, ContractParty, Counterparty
from src.models.auth_models import User


# ── Regex для извлечения реквизитов ────────────────────────────────────────

# Номер договора: «Договору № 12-АБВ/2025», «по договору N 42»
_CONTRACT_NUMBER_RE = re.compile(
    r"договор[ауеоюя]*\s*(?:№|N|#)\s*([A-Za-zА-Яа-я0-9./\-_]{1,50})",
    re.IGNORECASE,
)

# Дата договора: «от 01.01.2024», «от 01.01.24», «от 1 января 2024»
_DATE_NUMERIC_RE = re.compile(r"от\s+(\d{1,2})[./-](\d{1,2})[./-](\d{2,4})", re.IGNORECASE)
_RU_MONTHS = {
    "январ": 1, "феврал": 2, "март": 3, "апрел": 4, "ма": 5, "июн": 6,
    "июл": 7, "август": 8, "сентябр": 9, "октябр": 10, "ноябр": 11, "декабр": 12,
}
_DATE_TEXT_RE = re.compile(
    r"от\s+«?\s*(\d{1,2})\s*»?\s+([а-я]+)\s+(\d{4})\s*(?:г\.?|года)?",
    re.IGNORECASE,
)

# ИНН: 10 или 12 цифр подряд
_INN_RE = re.compile(r"\b(\d{10}|\d{12})\b")


@dataclass
class ExtractedContractRefs:
    """Реквизиты, извлечённые из текста производного документа."""

    numbers: List[str] = field(default_factory=list)
    dates: List[datetime] = field(default_factory=list)
    inns: List[str] = field(default_factory=list)
    raw_evidence: List[str] = field(default_factory=list)

    @property
    def empty(self) -> bool:
        return not (self.numbers or self.dates or self.inns)


@dataclass
class ParentCandidate:
    """Кандидат на основной договор."""

    contract_id: str
    file_name: str
    contract_number: Optional[str]
    contract_date: Optional[str]
    counterparties: List[dict]
    score: float
    confidence: float
    matched_fields: List[str]


def extract_contract_refs(text: str) -> ExtractedContractRefs:
    """Извлечь номер/дату/ИНН из текста производного документа.

    Работает по preamble — берём первые ~4000 символов, чтобы не уехать в
    тело документа (там встречаются ссылки на другие договоры).
    """
    if not text:
        return ExtractedContractRefs()

    snippet = text[:4000]
    refs = ExtractedContractRefs()

    for match in _CONTRACT_NUMBER_RE.finditer(snippet):
        number = match.group(1).strip(".,;:")
        if number and number not in refs.numbers:
            refs.numbers.append(number)
            refs.raw_evidence.append(match.group(0))

    for match in _DATE_NUMERIC_RE.finditer(snippet):
        d, m, y = match.groups()
        try:
            year = int(y)
            if year < 100:
                year += 2000 if year < 70 else 1900
            dt = datetime(year, int(m), int(d))
            if dt not in refs.dates:
                refs.dates.append(dt)
                refs.raw_evidence.append(match.group(0))
        except (ValueError, TypeError):
            continue

    for match in _DATE_TEXT_RE.finditer(snippet):
        d, mname, y = match.groups()
        month = _ru_month_index(mname)
        if not month:
            continue
        try:
            dt = datetime(int(y), month, int(d))
            if dt not in refs.dates:
                refs.dates.append(dt)
                refs.raw_evidence.append(match.group(0))
        except (ValueError, TypeError):
            continue

    for match in _INN_RE.finditer(snippet):
        inn = match.group(1)
        if inn not in refs.inns:
            refs.inns.append(inn)

    return refs


def _ru_month_index(name: str) -> Optional[int]:
    name = name.lower()
    for stem, idx in _RU_MONTHS.items():
        if name.startswith(stem):
            return idx
    return None


# ── Service ────────────────────────────────────────────────────────────────


class MainContractFinderService:
    """Поиск кандидатов на основной договор по реквизитам производного."""

    def __init__(self, scope_organization_id: Optional[str] = None) -> None:
        self.scope_organization_id = scope_organization_id

    def find_candidates(
        self,
        db: Session,
        text: str,
        current_user: User,
        organization_id: Optional[str] = None,
        exclude_contract_id: Optional[str] = None,
        limit: int = 5,
    ) -> List[ParentCandidate]:
        """Вернуть top-N кандидатов на основной договор."""
        org_id = organization_id or self.scope_organization_id

        refs = extract_contract_refs(text or "")
        if refs.empty:
            logger.info("MainContractFinder: no extractable refs — skipping search")
            return []

        # Базовый запрос: только основные договоры (не derivative), не deleted,
        # в пределах организации/пользователя.
        query = db.query(Contract).filter(
            Contract.document_type == "contract",
            Contract.status != "deleted",
        )
        if exclude_contract_id:
            query = query.filter(Contract.id != exclude_contract_id)

        if org_id:
            query = query.filter(
                or_(Contract.organization_id == org_id, Contract.organization_id.is_(None))
            )
        elif current_user.role != "admin":
            query = query.filter(
                or_(
                    Contract.assigned_to == current_user.id,
                    Contract.organization_id.is_(None),
                )
            )

        # Pre-filter: оставляем только тех, у кого хоть что-то совпадает.
        filters = []
        if refs.numbers:
            filters.append(
                Contract.contract_number.in_([n for n in refs.numbers if n])
            )
        if refs.dates:
            filters.append(Contract.contract_date.in_(refs.dates))
        if refs.inns:
            # Нужны договоры, где есть contract_party с counterparty.inn ∈ inns
            filters.append(
                Contract.id.in_(
                    db.query(ContractParty.contract_id)
                    .join(Counterparty, ContractParty.counterparty_id == Counterparty.id)
                    .filter(Counterparty.inn.in_(refs.inns))
                    .subquery()
                    .select()
                )
            )

        if not filters:
            return []
        query = query.filter(or_(*filters))

        # Берём кандидатов с запасом, потом скорим в Python.
        candidates: Iterable[Contract] = query.order_by(
            Contract.created_at.desc()
        ).limit(limit * 5).all()

        scored: List[ParentCandidate] = []
        for c in candidates:
            score, matched = self._score(c, refs, db)
            if score <= 0:
                continue
            confidence = min(score / 100.0, 1.0)
            cps = self._counterparties_for(c, db)
            scored.append(
                ParentCandidate(
                    contract_id=c.id,
                    file_name=c.file_name,
                    contract_number=c.contract_number,
                    contract_date=(
                        c.contract_date.isoformat() if c.contract_date else None
                    ),
                    counterparties=cps,
                    score=score,
                    confidence=round(confidence, 3),
                    matched_fields=matched,
                )
            )

        scored.sort(key=lambda x: x.score, reverse=True)
        return scored[:limit]

    @staticmethod
    def _score(
        contract: Contract,
        refs: ExtractedContractRefs,
        db: Session,
    ) -> tuple[float, List[str]]:
        score = 0.0
        matched: List[str] = []

        if contract.contract_number and refs.numbers:
            normalized_contract = contract.contract_number.strip().lower()
            for n in refs.numbers:
                ln = n.strip().lower()
                if ln == normalized_contract:
                    score += 50
                    matched.append("contract_number")
                    break
                if ln in normalized_contract or normalized_contract in ln:
                    score += 30
                    matched.append("contract_number_partial")
                    break

        if contract.contract_date and refs.dates:
            cd = contract.contract_date
            for d in refs.dates:
                if cd.date() == d.date():
                    score += 20
                    matched.append("contract_date")
                    break

        if refs.inns:
            inn_match = (
                db.query(ContractParty)
                .join(Counterparty, ContractParty.counterparty_id == Counterparty.id)
                .filter(
                    ContractParty.contract_id == contract.id,
                    Counterparty.inn.in_(refs.inns),
                )
                .first()
            )
            if inn_match:
                score += 25
                matched.append("counterparty_inn")

        return score, matched

    @staticmethod
    def _counterparties_for(contract: Contract, db: Session) -> List[dict]:
        rows = (
            db.query(ContractParty, Counterparty)
            .join(Counterparty, ContractParty.counterparty_id == Counterparty.id)
            .filter(ContractParty.contract_id == contract.id)
            .all()
        )
        return [
            {"id": cp.id, "name": cp.name, "inn": cp.inn, "role": party.role}
            for party, cp in rows
        ]


__all__ = [
    "MainContractFinderService",
    "ParentCandidate",
    "ExtractedContractRefs",
    "extract_contract_refs",
]
