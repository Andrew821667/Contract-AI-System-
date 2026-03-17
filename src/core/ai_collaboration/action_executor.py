"""
AI Action Execution Service — выполнение одобренных AI-действий.

Полный lifecycle:
  parse → normalize → policy check → threshold → execute/approval/block → audit

Принимает AIAction со статусом approved, выполняет его через tools/agents,
записывает результат и аудит.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from loguru import logger
from sqlalchemy.orm import Session

from src.core.base import ToolContext
from src.core.interfaces import IAuditLogger
from src.core.policies.resolver import MultiLevelPolicyResolver
from src.core.tools.invoker import ToolInvocationService
from .action_policy import AIActionPolicyService
from .models import AIAction, AIAuditRecord


class AIActionExecutionService:
    """Выполнение AI-действий через tool invoker с policy enforcement."""

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
        self.action_policy = AIActionPolicyService(db)

    async def execute_action(self, action: AIAction, user_id: str) -> bool:
        """
        Выполнить действие с полным lifecycle:
        1. Проверить статус (approved или auto-approved pending)
        2. Policy check (если resolver доступен)
        3. Execute (tool или direct)
        4. Audit

        Returns:
            True если выполнено успешно.
        """
        if action.execution_status not in ("approved", "pending"):
            logger.warning(f"Action {action.id} status='{action.execution_status}' — cannot execute")
            return False

        # Pending actions: проверяем, можно ли auto-execute
        if action.execution_status == "pending":
            if self.action_policy.is_approval_required(action.action_type, action.confidence):
                logger.info(f"Action {action.id} requires approval — skipping auto-execute")
                return False

        # Policy check
        if self.policy_resolver:
            allowed = await self._check_policy(action, user_id)
            if not allowed:
                action.execution_status = "blocked"
                self.db.flush()
                self._record_audit(action, "action_blocked", {
                    "reason": "policy_check_failed",
                    "user_id": user_id,
                })
                return False

        # Execute — определяем способ выполнения через policy
        tool_id = self.action_policy.get_tool_id(action.action_type)
        if tool_id:
            return await self._execute_via_tool(action, tool_id, user_id)

        if self.action_policy.is_direct_execution(action.action_type):
            return await self._execute_direct(action, user_id)

        logger.warning(f"Unknown action_type: {action.action_type}")
        action.execution_status = "failed"
        action.payload = {**(action.payload or {}), "error": f"Unknown action_type: {action.action_type}"}
        self.db.flush()
        return False

    async def _check_policy(self, action: AIAction, user_id: str) -> bool:
        """Проверить policy для действия."""
        risk_level = self.action_policy.get_risk_level(action.action_type)
        action_name = f"ai_action.{action.action_type}"

        # Получаем document_id через session
        session = action.session
        document_id = session.document_id if session else None

        decision = await self.policy_resolver.resolve(
            action=action_name,
            user_id=user_id,
            document_id=document_id,
            context={"risk_level": risk_level},
        )

        self._record_audit(action, "policy_check", {
            "action": action_name,
            "risk_level": risk_level,
            "allowed": decision.allowed,
            "reason": decision.reason,
        })

        return decision.allowed

    async def _execute_via_tool(self, action: AIAction, tool_id: str, user_id: str) -> bool:
        """Выполнить действие через зарегистрированный tool."""
        context = ToolContext(
            user_id=user_id,
            session_id=action.session_id,
            invoker=f"ai_action:{action.id}",
        )

        input_data = action.payload or {}
        result = await self.tool_invoker.invoke(tool_id, input_data, context)

        if result.success:
            action.execution_status = "executed"
            action.executed_at = datetime.now(timezone.utc)
            action.payload = {**(action.payload or {}), "result": result.data}
        else:
            action.execution_status = "failed"
            action.payload = {**(action.payload or {}), "error": result.error}

        self.db.flush()

        self._record_audit(action, "action_executed" if result.success else "action_failed", {
            "tool_id": tool_id,
            "success": result.success,
            "duration_ms": result.duration_ms,
        })

        return result.success

    async def _execute_direct(self, action: AIAction, user_id: str) -> bool:
        """Выполнить действие напрямую — результат уже в payload."""
        action.execution_status = "executed"
        action.executed_at = datetime.now(timezone.utc)
        self.db.flush()

        self._record_audit(action, "action_executed", {
            "action_type": action.action_type,
            "direct_execution": True,
        })

        return True

    def _record_audit(self, action: AIAction, event_type: str, details: dict[str, Any]) -> None:
        """Записать аудит-запись."""
        record = AIAuditRecord(
            session_id=action.session_id,
            action_id=action.id,
            actor=f"ai_action:{action.id}",
            event_type=event_type,
            details=details,
        )
        self.db.add(record)
        self.db.flush()
