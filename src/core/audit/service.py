"""
Audit Query Service — запросы к аудит-логу.

Объединяет данные из AuditLog (general) и AIAuditRecord (AI-specific).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from src.models.auth_models import AuditLog
from src.core.ai_collaboration.models import AIAuditRecord


class AuditQueryService:
    """Сервис запросов к аудиту."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def get_document_audit_trail(
        self,
        document_id: str,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Полный audit trail для документа."""
        # General audit logs
        general = (
            self.db.query(AuditLog)
            .filter(
                AuditLog.resource_id == document_id,
            )
            .order_by(AuditLog.created_at.desc())
            .limit(limit)
            .all()
        )

        result: list[dict[str, Any]] = []
        for log in general:
            result.append({
                "id": log.id,
                "source": "general",
                "actor": log.user_id,
                "action": log.action,
                "status": log.status,
                "severity": log.severity,
                "details": log.details,
                "created_at": log.created_at.isoformat() if log.created_at else None,
            })

        return sorted(result, key=lambda x: x.get("created_at", ""), reverse=True)

    def get_session_audit_trail(
        self,
        session_id: str,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Audit trail для AI-сессии."""
        records = (
            self.db.query(AIAuditRecord)
            .filter(AIAuditRecord.session_id == session_id)
            .order_by(AIAuditRecord.created_at.desc())
            .limit(limit)
            .all()
        )

        return [
            {
                "id": r.id,
                "source": "ai",
                "actor": r.actor,
                "event_type": r.event_type,
                "details": r.details,
                "model_used": r.model_used,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in records
        ]

    def get_user_activity(
        self,
        user_id: str,
        since: datetime | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """Активность пользователя."""
        query = self.db.query(AuditLog).filter(AuditLog.user_id == user_id)
        if since:
            query = query.filter(AuditLog.created_at >= since)
        logs = query.order_by(AuditLog.created_at.desc()).limit(limit).all()

        return [
            {
                "id": log.id,
                "action": log.action,
                "resource_type": log.resource_type,
                "resource_id": log.resource_id,
                "status": log.status,
                "created_at": log.created_at.isoformat() if log.created_at else None,
            }
            for log in logs
        ]
