"""
Workflow Tool — адаптер для AI-triggered workflow operations.

Позволяет AI автоматически запускать и продвигать workflows:
- start_workflow: найти и запустить подходящий workflow
- advance_workflow: завершить текущую задачу и продвинуть
"""

from __future__ import annotations

from typing import Any

from loguru import logger

from src.core.base import ToolContext, ToolResult
from .base_tool_adapter import BaseToolAdapter


class WorkflowTool(BaseToolAdapter):
    """AI-управление маршрутами согласования."""

    _tool_id = "workflow_manager"
    _name = "Управление workflow"
    _description = "Запуск и продвижение маршрутов согласования документов через AI"
    _permissions = ["workflow.manage", "workflow.advance"]
    _policy_tags = ["workflow", "automation"]
    _risk_level = "high"
    _sync_mode = "sync"

    _input_schema = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["start", "advance"],
                "description": "start — запустить workflow, advance — продвинуть текущий",
            },
            "document_id": {"type": "string"},
            "document_type": {"type": "string", "description": "Тип документа (для start)"},
            "risk_level": {"type": "string", "description": "Уровень риска (для start)"},
            "org_id": {"type": "string", "description": "ID организации (для start)"},
            "decision": {
                "type": "string",
                "enum": ["approve", "reject", "return_for_revision"],
                "description": "Решение по задаче (для advance)",
            },
            "comment": {"type": "string", "description": "Комментарий к решению"},
        },
        "required": ["action", "document_id"],
    }

    _output_schema = {
        "type": "object",
        "properties": {
            "status": {"type": "string"},
            "execution_id": {"type": "string"},
            "task_id": {"type": "string"},
            "message": {"type": "string"},
        },
    }

    def __init__(self, workflow_engine: Any) -> None:
        self._engine = workflow_engine

    async def _do_execute(self, input_data: dict[str, Any], context: ToolContext) -> ToolResult:
        action = input_data["action"]
        document_id = input_data["document_id"]

        if not self._engine:
            return ToolResult(success=False, error="WorkflowEngine не инициализирован")

        if action == "start":
            return await self._handle_start(input_data, document_id, context)
        elif action == "advance":
            return await self._handle_advance(input_data, document_id, context)
        else:
            return ToolResult(success=False, error=f"Неизвестное действие: {action}")

    async def _handle_start(self, input_data: dict[str, Any], document_id: str, context: ToolContext) -> ToolResult:
        document_type = input_data.get("document_type", "contract")
        risk_level = input_data.get("risk_level")
        org_id = input_data.get("org_id") or context.organization_id

        execution = self._engine.ai_start_workflow(
            document_id=document_id,
            document_type=document_type,
            risk_level=risk_level,
            org_id=org_id,
        )

        if not execution:
            return ToolResult(
                success=True,
                data={
                    "status": "no_match",
                    "message": "Подходящий workflow не найден",
                },
            )

        return ToolResult(
            success=True,
            data={
                "status": "started",
                "execution_id": execution.id,
                "message": f"Workflow запущен: {execution.id}",
            },
        )

    async def _handle_advance(self, input_data: dict[str, Any], document_id: str, context: ToolContext) -> ToolResult:
        decision = input_data.get("decision", "approve")
        comment = input_data.get("comment")

        task = self._engine.ai_advance_workflow(
            document_id=document_id,
            decision=decision,
            comment=comment,
            ai_session_id=context.session_id,
        )

        if not task:
            return ToolResult(
                success=True,
                data={
                    "status": "no_task",
                    "message": "Нет активных задач для продвижения",
                },
            )

        return ToolResult(
            success=True,
            data={
                "status": "advanced",
                "task_id": task.id,
                "decision": decision,
                "message": f"Задача {task.step_name} завершена с решением: {decision}",
            },
        )
