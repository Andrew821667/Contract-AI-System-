"""
AI Approval Service — одобрение/отклонение AI-действий.

Обрабатывает решения пользователей по предложенным AI-действиям.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from loguru import logger
from sqlalchemy.orm import Session

from .models import AIAction, AIActionApproval, AIAuditRecord


class AIApprovalService:
    """Сервис одобрения AI-действий."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def approve(
        self,
        action_id: str,
        approver_id: str,
        comment: str | None = None,
    ) -> AIAction | None:
        """Одобрить действие."""
        action = self._get_pending_action(action_id)
        if not action:
            return None

        approval = AIActionApproval(
            action_id=action_id,
            approver_id=approver_id,
            decision="approve",
            comment=comment,
        )
        self.db.add(approval)
        action.execution_status = "approved"
        self.db.flush()

        self._record_audit(action, approver_id, "action_approved", {"comment": comment})
        logger.info(f"AIAction {action_id} approved by {approver_id}")
        return action

    def reject(
        self,
        action_id: str,
        approver_id: str,
        comment: str | None = None,
    ) -> AIAction | None:
        """Отклонить действие."""
        action = self._get_pending_action(action_id)
        if not action:
            return None

        approval = AIActionApproval(
            action_id=action_id,
            approver_id=approver_id,
            decision="reject",
            comment=comment,
        )
        self.db.add(approval)
        action.execution_status = "rejected"
        self.db.flush()

        self._record_audit(action, approver_id, "action_rejected", {"comment": comment})
        logger.info(f"AIAction {action_id} rejected by {approver_id}")
        return action

    def edit_and_approve(
        self,
        action_id: str,
        approver_id: str,
        edited_payload: dict[str, Any],
        comment: str | None = None,
    ) -> AIAction | None:
        """Отредактировать и одобрить действие."""
        action = self._get_pending_action(action_id)
        if not action:
            return None

        approval = AIActionApproval(
            action_id=action_id,
            approver_id=approver_id,
            decision="edit_and_approve",
            comment=comment,
            edited_payload=edited_payload,
        )
        self.db.add(approval)

        # Заменяем payload на отредактированный
        action.payload = edited_payload
        action.execution_status = "approved"
        self.db.flush()

        self._record_audit(action, approver_id, "action_edited_and_approved", {
            "comment": comment,
            "edited": True,
        })
        logger.info(f"AIAction {action_id} edited & approved by {approver_id}")
        return action

    def get_pending_actions(self, session_id: str) -> list[AIAction]:
        """Список действий, ожидающих одобрения."""
        return (
            self.db.query(AIAction)
            .filter(
                AIAction.session_id == session_id,
                AIAction.execution_status == "pending",
                AIAction.approval_required.is_(True),
            )
            .order_by(AIAction.created_at)
            .all()
        )

    def _get_pending_action(self, action_id: str) -> AIAction | None:
        """Получить action в статусе pending."""
        action = self.db.query(AIAction).filter(AIAction.id == action_id).first()
        if not action:
            logger.warning(f"AIAction {action_id} not found")
            return None
        if action.execution_status != "pending":
            logger.warning(f"AIAction {action_id} is not pending (status={action.execution_status})")
            return None
        return action

    def _record_audit(
        self, action: AIAction, approver_id: str, event_type: str, details: dict[str, Any]
    ) -> None:
        record = AIAuditRecord(
            session_id=action.session_id,
            action_id=action.id,
            actor=f"user:{approver_id}",
            event_type=event_type,
            details=details,
        )
        self.db.add(record)
        self.db.flush()
