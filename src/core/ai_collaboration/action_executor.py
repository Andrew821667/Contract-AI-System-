"""
AI Action Execution Service — выполнение одобренных AI-действий.

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
from src.core.tools.invoker import ToolInvocationService
from .models import AIAction, AIAuditRecord


# Маппинг action_type → tool_id (какой tool вызывать для какого типа действия)
_ACTION_TOOL_MAP: dict[str, str] = {
    "analyze_risks": "risk_scorer",
    "extract_clauses": "clause_extractor",
    "search_knowledge": "rag_search",
    "parse_document": "document_parser",
    "generate_contract": "contract_generator",
}


class AIActionExecutionService:
    """Выполнение AI-действий через tool invoker."""

    def __init__(
        self,
        db: Session,
        tool_invoker: ToolInvocationService,
        audit_logger: IAuditLogger,
    ) -> None:
        self.db = db
        self.tool_invoker = tool_invoker
        self.audit_logger = audit_logger

    async def execute_action(self, action: AIAction, user_id: str) -> bool:
        """
        Выполнить одобренное действие.

        Returns:
            True если выполнено успешно.
        """
        if action.execution_status not in ("approved", "pending"):
            logger.warning(f"Action {action.id} has status '{action.execution_status}' — cannot execute")
            return False

        # Действия, выполняемые через tool
        tool_id = _ACTION_TOOL_MAP.get(action.action_type)
        if tool_id:
            return await self._execute_via_tool(action, tool_id, user_id)

        # Действия, выполняемые напрямую (без tool)
        return await self._execute_direct(action, user_id)

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

        # Audit
        self._record_audit(action, "action_executed" if result.success else "action_failed", {
            "tool_id": tool_id,
            "success": result.success,
            "duration_ms": result.duration_ms,
        })

        return result.success

    async def _execute_direct(self, action: AIAction, user_id: str) -> bool:
        """
        Выполнить действие напрямую (explain_finding, suggest_clause, create_comment_draft).
        Эти действия не вызывают tool — их результат уже в payload.
        """
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
