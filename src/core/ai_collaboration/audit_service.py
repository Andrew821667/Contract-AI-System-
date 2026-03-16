"""
AI Audit Service — реализация IAuditLogger для AI-контекста.

Записывает все AI-действия в ai_audit_records + общий audit_logs.
"""

from __future__ import annotations

from typing import Any

from loguru import logger
from sqlalchemy.orm import Session

from src.core.base import AuditEvent, PolicyDecision
from src.models.auth_models import AuditLog
from .models import AIAuditRecord


class AIAuditService:
    """Аудит AI-действий. Реализует IAuditLogger."""

    def __init__(self, db: Session) -> None:
        self.db = db

    async def log(
        self,
        actor: str,
        action: str,
        target: str,
        payload: dict[str, Any] | None = None,
        result: str = "success",
        policy_decision: PolicyDecision | None = None,
        session_id: str | None = None,
        correlation_id: str | None = None,
    ) -> AuditEvent:
        """Записать событие аудита."""

        # 1. AI audit record (если есть session)
        if session_id:
            ai_record = AIAuditRecord(
                session_id=session_id,
                actor=actor,
                event_type=action,
                details={
                    "target": target,
                    "payload": payload,
                    "result": result,
                    "policy_decision": policy_decision.model_dump() if policy_decision else None,
                    "correlation_id": correlation_id,
                },
            )
            self.db.add(ai_record)

        # 2. Общий AuditLog (для compliance)
        severity = "info"
        if result in ("blocked", "rejected"):
            severity = "warning"
        elif result == "failed":
            severity = "error"

        # Извлекаем user_id из actor (user:xxx → xxx)
        user_id = None
        if actor.startswith("user:"):
            user_id = actor[5:]

        general_log = AuditLog(
            user_id=user_id,
            action=f"ai.{action}",
            resource_type="ai_session" if session_id else "system",
            resource_id=session_id or target,
            status=result,
            details={
                "actor": actor,
                "target": target,
                "correlation_id": correlation_id,
                **({"policy": policy_decision.reason} if policy_decision else {}),
            },
            severity=severity,
        )
        self.db.add(general_log)
        self.db.flush()

        event = AuditEvent(
            actor=actor,
            action=action,
            target=target,
            result=result,
            payload=payload or {},
            policy_decision=policy_decision,
            session_id=session_id,
            correlation_id=correlation_id,
        )

        logger.debug(f"Audit: {actor} → {action} → {target} = {result}")
        return event
