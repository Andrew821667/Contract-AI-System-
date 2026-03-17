"""
AI Action Policy Service — управление политиками AI-действий.

Читает правила из БД (таблица ai_action_policies).
Если запись не найдена — fallback на хардкод-константы.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from loguru import logger
from sqlalchemy.orm import Session

from .models import AIActionPolicy


# ── Fallback-константы (legacy) ───────────────────────────────
_DEFAULT_TOOL_MAP: dict[str, str] = {
    "analyze_risks": "risk_scorer",
    "extract_clauses": "clause_extractor",
    "search_knowledge": "rag_search",
    "parse_document": "document_parser",
    "generate_contract": "contract_generator",
}

_DEFAULT_DIRECT_ACTIONS: set[str] = {
    "explain_finding", "suggest_clause", "modify_clause",
    "create_comment_draft", "suggest_risk_mitigation", "create_summary",
    "compare_versions", "translate_clause", "answer_question",
    "draft_negotiation_response",
}

_DEFAULT_ALWAYS_APPROVE: set[str] = {
    "modify_clause", "generate_contract", "assign_reviewer",
    "change_workflow_status", "send_notification",
}

_DEFAULT_RISK_LEVELS: dict[str, str] = {
    "explain_finding": "low",
    "suggest_clause": "medium",
    "modify_clause": "high",
    "create_comment_draft": "low",
    "suggest_risk_mitigation": "medium",
    "create_summary": "low",
    "compare_versions": "low",
    "translate_clause": "low",
    "answer_question": "low",
    "draft_negotiation_response": "medium",
    "analyze_risks": "medium",
    "extract_clauses": "low",
    "search_knowledge": "low",
    "parse_document": "low",
    "generate_contract": "high",
    "assign_reviewer": "medium",
    "change_workflow_status": "high",
    "send_notification": "medium",
}


@dataclass
class ActionPolicyDecision:
    """Результат lookup политики для конкретного action_type."""

    action_type: str
    risk_level: str
    approval_required: bool
    auto_approve_threshold: float
    tool_id: str | None
    direct_execution: bool
    allowed_roles: list[str] | None
    from_db: bool  # True если из БД, False если fallback


class AIActionPolicyService:
    """Сервис чтения политик AI-действий (DB-first, fallback на константы)."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self._cache: dict[str, ActionPolicyDecision] = {}

    def get_policy(self, action_type: str) -> ActionPolicyDecision:
        """Получить политику для action_type."""
        if action_type in self._cache:
            return self._cache[action_type]

        policy = (
            self.db.query(AIActionPolicy)
            .filter(
                AIActionPolicy.action_type == action_type,
                AIActionPolicy.active.is_(True),
            )
            .first()
        )

        if policy:
            decision = ActionPolicyDecision(
                action_type=action_type,
                risk_level=policy.risk_level,
                approval_required=policy.approval_required,
                auto_approve_threshold=policy.auto_approve_threshold,
                tool_id=policy.tool_id,
                direct_execution=policy.direct_execution,
                allowed_roles=policy.allowed_roles,
                from_db=True,
            )
        else:
            # Fallback на хардкод-константы
            decision = ActionPolicyDecision(
                action_type=action_type,
                risk_level=_DEFAULT_RISK_LEVELS.get(action_type, "medium"),
                approval_required=action_type in _DEFAULT_ALWAYS_APPROVE,
                auto_approve_threshold=0.9,
                tool_id=_DEFAULT_TOOL_MAP.get(action_type),
                direct_execution=action_type in _DEFAULT_DIRECT_ACTIONS,
                allowed_roles=None,
                from_db=False,
            )

        self._cache[action_type] = decision
        return decision

    def is_approval_required(self, action_type: str, confidence: float) -> bool:
        """Нужен ли approval для действия с данным confidence."""
        policy = self.get_policy(action_type)
        if policy.approval_required:
            return True
        return confidence < policy.auto_approve_threshold

    def get_tool_id(self, action_type: str) -> str | None:
        """Получить tool_id для выполнения действия."""
        return self.get_policy(action_type).tool_id

    def is_direct_execution(self, action_type: str) -> bool:
        """Является ли действие direct (результат уже в payload)."""
        return self.get_policy(action_type).direct_execution

    def get_risk_level(self, action_type: str) -> str:
        """Получить risk level для действия."""
        return self.get_policy(action_type).risk_level

    def clear_cache(self) -> None:
        """Очистить кэш (вызывать после обновления политик)."""
        self._cache.clear()

    def seed_defaults(self) -> int:
        """
        Заполнить БД дефолтными политиками из констант.
        Пропускает уже существующие записи.
        Returns: количество созданных записей.
        """
        all_types = set(_DEFAULT_RISK_LEVELS.keys())
        existing = {
            row.action_type
            for row in self.db.query(AIActionPolicy.action_type).all()
        }

        created = 0
        for action_type in sorted(all_types - existing):
            policy = AIActionPolicy(
                action_type=action_type,
                risk_level=_DEFAULT_RISK_LEVELS.get(action_type, "medium"),
                approval_required=action_type in _DEFAULT_ALWAYS_APPROVE,
                auto_approve_threshold=0.9,
                tool_id=_DEFAULT_TOOL_MAP.get(action_type),
                direct_execution=action_type in _DEFAULT_DIRECT_ACTIONS,
                description=f"Auto-generated policy for {action_type}",
            )
            self.db.add(policy)
            created += 1

        if created:
            self.db.flush()
            logger.info(f"Seeded {created} AI action policies")

        return created
