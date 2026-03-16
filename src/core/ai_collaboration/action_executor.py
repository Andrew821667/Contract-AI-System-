"""
AI Action Execution Service — выполнение одобренных AI-действий.

Полный lifecycle:
  parse → normalize → policy check → threshold → execute/approval/block → audit

Принимает AIAction со статусом approved, выполняет его через tools/agents,
записывает результат и аудит.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from loguru import logger
from sqlalchemy.orm import Session

from src.core.base import ToolContext
from src.core.interfaces import IAuditLogger
from src.core.policies.resolver import MultiLevelPolicyResolver
from src.core.tools.invoker import ToolInvocationService
from .models import AIAction, AIAuditRecord


# ── Маппинг action_type → tool_id ────────────────────────────────────────────
# Действия, выполняемые через зарегистрированные tools
_ACTION_TOOL_MAP: dict[str, str] = {
    "analyze_risks": "risk_scorer",
    "extract_clauses": "clause_extractor",
    "search_knowledge": "rag_search",
    "parse_document": "document_parser",
    "generate_contract": "contract_generator",
}

# Действия, выполняемые напрямую (результат уже в payload)
_DIRECT_ACTION_TYPES: set[str] = {
    "explain_finding",
    "suggest_clause",
    "modify_clause",
    "create_comment_draft",
    "suggest_risk_mitigation",
    "create_summary",
    "compare_versions",
    "translate_clause",
    "answer_question",
    "draft_negotiation_response",
}

# Действия, требующие обязательного approval (независимо от confidence)
_ALWAYS_REQUIRE_APPROVAL: set[str] = {
    "modify_clause",
    "generate_contract",
    "assign_reviewer",
    "change_workflow_status",
    "send_notification",
}

# Risk level по типу действия (для policy checks)
_ACTION_RISK_LEVELS: dict[str, str] = {
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
            if action.approval_required or action.action_type in _ALWAYS_REQUIRE_APPROVAL:
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

        # Execute
        tool_id = _ACTION_TOOL_MAP.get(action.action_type)
        if tool_id:
            return await self._execute_via_tool(action, tool_id, user_id)

        if action.action_type in _DIRECT_ACTION_TYPES:
            return await self._execute_direct(action, user_id)

        logger.warning(f"Unknown action_type: {action.action_type}")
        action.execution_status = "failed"
        action.payload = {**(action.payload or {}), "error": f"Unknown action_type: {action.action_type}"}
        self.db.flush()
        return False

    async def _check_policy(self, action: AIAction, user_id: str) -> bool:
        """Проверить policy для действия."""
        risk_level = _ACTION_RISK_LEVELS.get(action.action_type, "medium")
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
            action.executed_at = datetime.utcnow()
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
        action.executed_at = datetime.utcnow()
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
