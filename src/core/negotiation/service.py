# -*- coding: utf-8 -*-
"""
NegotiationService — AI-assisted переговоры и генерация возражений.

Pipeline:
1. start_negotiation — создать процесс переговоров
2. generate_objections — сгенерировать возражения через tool pipeline
3. select_objections — выбрать возражения для протокола
4. prepare_position — подготовить переговорную позицию через smart_composer
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

from .models import Negotiation, NegotiationObjection
from .schemas import (
    NegotiationStartRequest,
    NegotiationStartResponse,
    ObjectionGenerateRequest,
    ObjectionResponse,
    ObjectionSelectionRequest,
    ObjectionSelectionResponse,
    NegotiationPositionRequest,
    NegotiationPositionResponse,
)


class NegotiationService:
    """Сервис AI-assisted переговоров и генерации возражений."""

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
    # 1. Запуск переговоров
    # ------------------------------------------------------------------

    async def start_negotiation(
        self,
        request: NegotiationStartRequest,
        user_id: str,
        org_id: str | None = None,
    ) -> NegotiationStartResponse:
        """Создать процесс переговоров по документу."""
        await self._check_policy("negotiation.start", user_id, org_id, request.document_id)

        negotiation_id = str(uuid4())

        negotiation = Negotiation(
            id=negotiation_id,
            document_id=request.document_id,
            user_id=user_id,
            analysis_id=request.analysis_id,
            goal=request.goal,
            status="active",
            objections_count=0,
            by_priority={},
        )
        self.db.add(negotiation)
        self.db.flush()

        await self.audit_logger.log(
            actor=user_id,
            action="negotiation.start",
            target=request.document_id,
            payload={
                "negotiation_id": negotiation_id,
                "goal": request.goal[:200],
                "analysis_id": request.analysis_id,
            },
            result="success",
        )

        logger.info(
            f"Переговоры запущены: negotiation_id={negotiation_id}, "
            f"document={request.document_id}, user={user_id}"
        )

        return NegotiationStartResponse(
            negotiation_id=negotiation_id,
            status="active",
            objections_count=0,
            by_priority={},
        )

    # ------------------------------------------------------------------
    # 2. Генерация возражений
    # ------------------------------------------------------------------

    async def generate_objections(
        self,
        request: ObjectionGenerateRequest,
        user_id: str,
        org_id: str | None = None,
    ) -> list[ObjectionResponse]:
        """
        Сгенерировать возражения через tool pipeline.

        Pipeline: risk_scorer → clause_extractor → формирование возражений.
        """
        await self._check_policy("negotiation.generate_objections", user_id, org_id)

        negotiation = (
            self.db.query(Negotiation)
            .filter(Negotiation.id == request.negotiation_id)
            .first()
        )
        if not negotiation:
            raise ValueError(f"Переговоры {request.negotiation_id} не найдены")

        ctx = ToolContext(
            user_id=user_id,
            organization_id=org_id,
            document_id=negotiation.document_id,
            invoker=f"negotiation_service:{negotiation.id}",
            metadata={"negotiation_id": negotiation.id},
        )

        # ── Получаем риски через risk_scorer ──────────────────────────
        risk_result = await self.tool_invoker.invoke(
            "risk_scorer",
            {
                "document_id": negotiation.document_id,
                "risk_ids": request.risk_ids,
            },
            ctx,
        )

        risks: list[dict[str, Any]] = []
        if risk_result.success and risk_result.data:
            risks = risk_result.data.get("risks", [])

        # ── Получаем клаузы через clause_extractor ────────────────────
        clause_result = await self.tool_invoker.invoke(
            "clause_extractor",
            {"document_id": negotiation.document_id},
            ctx,
        )

        clauses: list[dict[str, Any]] = []
        if clause_result.success and clause_result.data:
            clauses = clause_result.data.get("clauses", [])

        # ── Формируем возражения ──────────────────────────────────────
        objections: list[ObjectionResponse] = []
        by_priority: dict[str, int] = {}

        for risk in risks:
            objection_id = str(uuid4())
            priority = self._risk_to_priority(risk.get("severity", "medium"))
            auto_priority = self._calculate_auto_priority(risk)

            by_priority[priority] = by_priority.get(priority, 0) + 1

            # Сохраняем в DB
            obj = NegotiationObjection(
                id=objection_id,
                negotiation_id=negotiation.id,
                issue_description=risk.get("description", ""),
                legal_basis=risk.get("legal_basis", ""),
                risk_explanation=risk.get("consequences", ""),
                alternative_formulation=risk.get("recommendation", ""),
                alternative_reasoning=risk.get("reasoning", ""),
                priority=priority,
                auto_priority=auto_priority,
                confidence=risk.get("confidence", 0.8),
                risk_id=risk.get("id"),
            )
            self.db.add(obj)

            objections.append(ObjectionResponse(
                objection_id=objection_id,
                issue_description=obj.issue_description,
                legal_basis=obj.legal_basis,
                risk_explanation=obj.risk_explanation,
                alternative_formulation=obj.alternative_formulation,
                alternative_reasoning=obj.alternative_reasoning,
                priority=priority,
                auto_priority=auto_priority,
                confidence=obj.confidence,
            ))

        # Обновляем negotiation
        negotiation.objections_count = len(objections)
        negotiation.by_priority = by_priority
        self.db.flush()

        await self.audit_logger.log(
            actor=user_id,
            action="negotiation.generate_objections",
            target=negotiation.document_id,
            payload={
                "negotiation_id": negotiation.id,
                "objections_count": len(objections),
                "by_priority": by_priority,
            },
            result="success",
        )

        logger.info(
            f"Возражения сгенерированы: negotiation={negotiation.id}, "
            f"count={len(objections)}, by_priority={by_priority}"
        )

        return objections

    # ------------------------------------------------------------------
    # 3. Выбор возражений
    # ------------------------------------------------------------------

    async def select_objections(
        self,
        request: ObjectionSelectionRequest,
        user_id: str,
    ) -> ObjectionSelectionResponse:
        """Выбрать возражения для включения в протокол переговоров."""
        # Сбросить предыдущий выбор
        self.db.query(NegotiationObjection).filter(
            NegotiationObjection.negotiation_id == request.negotiation_id,
        ).update({"selected": False, "selection_order": None})

        # Установить новый выбор
        for idx, obj_id in enumerate(request.selected_objection_ids):
            self.db.query(NegotiationObjection).filter(
                NegotiationObjection.id == obj_id,
                NegotiationObjection.negotiation_id == request.negotiation_id,
            ).update({"selected": True, "selection_order": idx})

        # Обновляем статус
        negotiation = (
            self.db.query(Negotiation)
            .filter(Negotiation.id == request.negotiation_id)
            .first()
        )
        if negotiation:
            negotiation.status = "review"

        self.db.flush()

        logger.info(
            f"Возражения выбраны: negotiation={request.negotiation_id}, "
            f"selected={len(request.selected_objection_ids)}"
        )

        return ObjectionSelectionResponse(
            status="review",
            selected_count=len(request.selected_objection_ids),
        )

    # ------------------------------------------------------------------
    # 4. Подготовка позиции
    # ------------------------------------------------------------------

    async def prepare_position(
        self,
        request: NegotiationPositionRequest,
        user_id: str,
        org_id: str | None = None,
    ) -> NegotiationPositionResponse:
        """Подготовить переговорную позицию через smart_composer tool."""
        await self._check_policy("negotiation.prepare_position", user_id, org_id)

        negotiation = (
            self.db.query(Negotiation)
            .filter(Negotiation.id == request.negotiation_id)
            .first()
        )
        if not negotiation:
            raise ValueError(f"Переговоры {request.negotiation_id} не найдены")

        # Собираем выбранные возражения для контекста
        selected_objections = (
            self.db.query(NegotiationObjection)
            .filter(
                NegotiationObjection.negotiation_id == negotiation.id,
                NegotiationObjection.selected.is_(True),
            )
            .order_by(NegotiationObjection.selection_order)
            .all()
        )

        ctx = ToolContext(
            user_id=user_id,
            organization_id=org_id,
            document_id=negotiation.document_id,
            invoker=f"negotiation_service:{negotiation.id}",
            metadata={"negotiation_id": negotiation.id},
        )

        # Вызываем smart_composer для генерации позиции
        composer_result = await self.tool_invoker.invoke(
            "smart_composer",
            {
                "context": {
                    "goal": negotiation.goal,
                    "strategy": request.strategy,
                    "focus_areas": request.focus_areas or [],
                    "objections": [
                        {
                            "issue": o.issue_description,
                            "legal_basis": o.legal_basis,
                            "priority": o.priority,
                        }
                        for o in selected_objections
                    ],
                },
                "instruction": f"Подготовить переговорную позицию. Стратегия: {request.strategy}",
            },
            ctx,
        )

        position_text = ""
        key_arguments: list[str] = []
        concession_candidates: list[str] = []
        red_lines: list[str] = []

        if composer_result.success and composer_result.data:
            data = composer_result.data
            position_text = data.get("composed_text", "")
            key_arguments = data.get("key_arguments", [])
            concession_candidates = data.get("concession_candidates", [])
            red_lines = data.get("red_lines", [])

        # Сохраняем позицию
        negotiation.position_text = position_text
        negotiation.position_metadata = {
            "strategy": request.strategy,
            "focus_areas": request.focus_areas,
            "key_arguments": key_arguments,
            "concession_candidates": concession_candidates,
            "red_lines": red_lines,
        }
        self.db.flush()

        await self.audit_logger.log(
            actor=user_id,
            action="negotiation.prepare_position",
            target=negotiation.document_id,
            payload={
                "negotiation_id": negotiation.id,
                "strategy": request.strategy,
                "objections_used": len(selected_objections),
            },
            result="success",
        )

        logger.info(
            f"Позиция подготовлена: negotiation={negotiation.id}, "
            f"strategy={request.strategy}, arguments={len(key_arguments)}"
        )

        return NegotiationPositionResponse(
            position_text=position_text,
            key_arguments=key_arguments,
            concession_candidates=concession_candidates,
            red_lines=red_lines,
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _risk_to_priority(severity: str) -> str:
        """Маппинг severity → priority."""
        return {
            "critical": "critical",
            "significant": "high",
            "high": "high",
            "moderate": "medium",
            "medium": "medium",
            "minor": "low",
            "low": "low",
        }.get(severity.lower(), "medium")

    @staticmethod
    def _calculate_auto_priority(risk: dict[str, Any]) -> int:
        """Автоматический приоритет 1-100 на основе severity и probability."""
        severity_score = {
            "critical": 90, "significant": 75, "high": 75,
            "moderate": 50, "medium": 50, "minor": 25, "low": 25,
        }.get(risk.get("severity", "medium").lower(), 50)

        probability = risk.get("probability", 0.5)
        return min(100, int(severity_score * (0.5 + probability * 0.5)))

    async def _check_policy(
        self,
        action: str,
        user_id: str,
        org_id: str | None = None,
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
