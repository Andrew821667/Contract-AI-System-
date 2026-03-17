"""
Version Intelligence Service — интеллектуальное сравнение версий документов.

Сравнение версий, выявление существенных изменений, рекомендации.
Работает через ToolInvocationService (policy + audit на каждый вызов).
"""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from loguru import logger
from sqlalchemy.orm import Session

from src.core.base import ToolContext
from src.core.interfaces import IAuditLogger
from src.core.policies.resolver import MultiLevelPolicyResolver
from src.core.tools.invoker import ToolInvocationService

from .schemas import (
    MaterialChangeResponse,
    VersionCompareRequest,
    VersionCompareResponse,
)

# In-memory кеш сравнений (per-process). В production → Redis.
# Bounded: максимум 256 записей, LRU-вытеснение.
from functools import lru_cache as _lru_cache
from collections import OrderedDict

_COMPARISON_CACHE_MAX = 256


class _BoundedCache:
    """Простой LRU-кеш с ограничением по размеру."""
    def __init__(self, maxsize: int = _COMPARISON_CACHE_MAX):
        self._data: OrderedDict[str, dict[str, Any]] = OrderedDict()
        self._maxsize = maxsize

    def get(self, key: str) -> dict[str, Any] | None:
        if key in self._data:
            self._data.move_to_end(key)
            return self._data[key]
        return None

    def __setitem__(self, key: str, value: dict[str, Any]) -> None:
        if key in self._data:
            self._data.move_to_end(key)
        self._data[key] = value
        if len(self._data) > self._maxsize:
            self._data.popitem(last=False)

    def __contains__(self, key: str) -> bool:
        return key in self._data


_comparison_cache = _BoundedCache()


class VersionIntelligenceService:
    """
    Сервис интеллектуального сравнения версий.

    Pipeline:
    1. compare_versions — сравнить две версии через document_diff
    2. detect_material_changes — выделить существенные изменения
    3. get_change_recommendations — получить рекомендации по изменениям
    """

    def __init__(
        self,
        db: Session,
        tool_invoker: ToolInvocationService,
        audit_logger: IAuditLogger,
        policy_resolver: MultiLevelPolicyResolver | None = None,
    ) -> None:
        self.db = db
        self.tool_invoker = tool_invoker
        self.audit_logger = audit_logger
        self.policy_resolver = policy_resolver

    # ------------------------------------------------------------------
    # 1. Сравнение версий
    # ------------------------------------------------------------------

    async def compare_versions(
        self,
        request: VersionCompareRequest,
        user_id: str,
        org_id: str | None = None,
    ) -> VersionCompareResponse:
        """
        Сравнить две версии документа.

        Вызывает document_diff, при deep_analysis дополнительно risk_scorer
        для оценки влияния изменений.
        """
        # ── Policy check ─────────────────────────────────────────────
        await self._check_policy("version.compare", user_id, org_id, request.document_id)

        comparison_id = str(uuid4())

        # ── Контекст для вызовов tools ───────────────────────────────
        ctx = ToolContext(
            user_id=user_id,
            organization_id=org_id,
            document_id=request.document_id,
            invoker=f"version_service:{comparison_id}",
            metadata={"comparison_id": comparison_id},
        )

        # ── Вызываем document_diff ───────────────────────────────────
        diff_result = await self.tool_invoker.invoke(
            "document_diff",
            {
                "document_id": request.document_id,
                "from_version_id": request.from_version_id,
                "to_version_id": request.to_version_id,
            },
            ctx,
        )

        diff_data = diff_result.data if diff_result.success else {}
        raw_changes: list[dict[str, Any]] = diff_data.get("changes", [])

        # ── Deep analysis через risk_scorer (если включён) ───────────
        risk_data: dict[str, Any] = {}
        if request.deep_analysis and raw_changes:
            risk_result = await self.tool_invoker.invoke(
                "risk_scorer",
                {
                    "document_id": request.document_id,
                    "changes": raw_changes,
                    "mode": "version_diff",
                },
                ctx,
            )
            if risk_result.success:
                risk_data = risk_result.data

        # ── Формируем MaterialChangeResponse ─────────────────────────
        risk_by_change: dict[str, dict[str, Any]] = {
            r.get("change_id", ""): r
            for r in risk_data.get("change_risks", [])
        }

        material_changes: list[MaterialChangeResponse] = []
        by_type: dict[str, int] = {}
        by_category: dict[str, int] = {}

        for change in raw_changes:
            change_id = change.get("id", str(uuid4()))
            change_type = change.get("type", "modified")
            change_category = change.get("category", "general")

            by_type[change_type] = by_type.get(change_type, 0) + 1
            by_category[change_category] = by_category.get(change_category, 0) + 1

            risk_info = risk_by_change.get(change_id, {})

            mc = MaterialChangeResponse(
                change_id=change_id,
                change_type=change_type,
                change_category=change_category,
                section_name=change.get("section_name"),
                clause_number=change.get("clause_number"),
                old_content=change.get("old_content"),
                new_content=change.get("new_content"),
                semantic_description=change.get("semantic_description"),
                impact_direction=risk_info.get("impact_direction"),
                severity=risk_info.get("severity"),
                recommendation=risk_info.get("recommendation"),
                requires_review=risk_info.get("requires_review", False),
            )
            material_changes.append(mc)

        # ── Общая оценка и саммари ───────────────────────────────────
        overall_assessment = diff_data.get("overall_assessment", "Сравнение завершено")
        executive_summary = diff_data.get(
            "executive_summary",
            f"Обнаружено {len(raw_changes)} изменений между версиями.",
        )

        # ── Сохраняем результат в in-memory кеш ─────────────────────
        comparison_record = {
            "comparison_id": comparison_id,
            "document_id": request.document_id,
            "from_version_id": request.from_version_id,
            "to_version_id": request.to_version_id,
            "changes": [mc.model_dump() for mc in material_changes],
            "by_type": by_type,
            "by_category": by_category,
            "overall_assessment": overall_assessment,
            "executive_summary": executive_summary,
        }
        _comparison_cache[comparison_id] = comparison_record

        # ── Audit log ────────────────────────────────────────────────
        await self.audit_logger.log(
            actor=user_id,
            action="version.compare",
            target=request.document_id,
            payload={
                "comparison_id": comparison_id,
                "from_version_id": request.from_version_id,
                "to_version_id": request.to_version_id,
                "total_changes": len(raw_changes),
                "deep_analysis": request.deep_analysis,
            },
            result="success" if diff_result.success else "failed",
        )

        logger.info(
            f"Сравнение версий завершено: comparison_id={comparison_id}, "
            f"doc={request.document_id}, changes={len(raw_changes)}"
        )

        return VersionCompareResponse(
            comparison_id=comparison_id,
            total_changes=len(raw_changes),
            by_type=by_type,
            by_category=by_category,
            overall_assessment=overall_assessment,
            material_changes=material_changes,
            executive_summary=executive_summary,
        )

    # ------------------------------------------------------------------
    # 2. Выявление существенных изменений
    # ------------------------------------------------------------------

    async def detect_material_changes(
        self,
        comparison_id: str,
        user_id: str,
    ) -> list[MaterialChangeResponse]:
        """
        Выделить существенные изменения из результата сравнения.

        Фильтрует изменения, где requires_review=True или category=legal.
        """
        comparison = self._load_comparison(comparison_id)
        changes: list[dict[str, Any]] = comparison.get("changes", [])

        material: list[MaterialChangeResponse] = []
        for change in changes:
            is_substantive = change.get("requires_review", False)
            is_legal = change.get("change_category") == "legal"

            if is_substantive or is_legal:
                material.append(MaterialChangeResponse(**change))

        logger.info(
            f"Существенные изменения: comparison_id={comparison_id}, "
            f"total={len(changes)}, material={len(material)}"
        )

        return material

    # ------------------------------------------------------------------
    # 3. Рекомендации по изменениям
    # ------------------------------------------------------------------

    async def get_change_recommendations(
        self,
        comparison_id: str,
        user_id: str,
    ) -> dict[str, Any]:
        """
        Получить рекомендации по изменениям (принять / отклонить / обсудить).

        Возвращает:
            accept_count, reject_count, negotiate_count, recommendations list
        """
        comparison = self._load_comparison(comparison_id)
        changes: list[dict[str, Any]] = comparison.get("changes", [])

        accept_count = 0
        reject_count = 0
        negotiate_count = 0
        recommendations: list[dict[str, Any]] = []

        for change in changes:
            rec = change.get("recommendation", "")
            severity = change.get("severity")

            if severity in ("low", None) and not change.get("requires_review", False):
                action = "accept"
                accept_count += 1
            elif severity == "critical" or "отклонить" in (rec or "").lower():
                action = "reject"
                reject_count += 1
            else:
                action = "negotiate"
                negotiate_count += 1

            recommendations.append({
                "change_id": change.get("change_id"),
                "action": action,
                "reason": rec or f"Северити: {severity or 'не определено'}",
                "clause_number": change.get("clause_number"),
                "section_name": change.get("section_name"),
            })

        logger.info(
            f"Рекомендации сформированы: comparison_id={comparison_id}, "
            f"accept={accept_count}, reject={reject_count}, negotiate={negotiate_count}"
        )

        return {
            "accept_count": accept_count,
            "reject_count": reject_count,
            "negotiate_count": negotiate_count,
            "recommendations": recommendations,
        }

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _load_comparison(self, comparison_id: str) -> dict[str, Any]:
        """Загрузить результат сравнения из кеша."""
        record = _comparison_cache.get(comparison_id)
        if record is None:
            raise ValueError(f"Результат сравнения {comparison_id} не найден")
        return record

    async def _check_policy(
        self,
        action: str,
        user_id: str,
        org_id: str | None,
        document_id: str | None = None,
    ) -> None:
        """Проверить политику; при отказе — выбросить PermissionError."""
        if self.policy_resolver is None:
            return

        decision = await self.policy_resolver.resolve(
            action=action,
            user_id=user_id,
            organization_id=org_id,
            document_id=document_id,
        )
        if not decision.allowed:
            raise PermissionError(
                f"Действие '{action}' заблокировано политикой: {decision.reason}"
            )
