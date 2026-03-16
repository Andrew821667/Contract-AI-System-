"""
Template Manager Tool — адаптер для TemplateManager.

Рендеринг шаблонов контрактов.
"""

from __future__ import annotations

from typing import Any

from src.core.base import ToolContext, ToolResult
from .base_tool_adapter import BaseToolAdapter


class TemplateManagerTool(BaseToolAdapter):
    """Обёртка TemplateManager → ITool."""

    _tool_id = "template_manager"
    _name = "Менеджер шаблонов"
    _description = "Рендеринг шаблонов контрактов с подстановкой переменных"
    _permissions = ["contract.read", "generation.execute"]
    _policy_tags = ["generation", "templates"]
    _risk_level = "medium"
    _sync_mode = "sync"

    _input_schema = {
        "type": "object",
        "properties": {
            "template_type": {"type": "string"},
            "variables": {"type": "object"},
        },
        "required": ["template_type", "variables"],
    }

    _output_schema = {
        "type": "object",
        "properties": {
            "rendered_text": {"type": "string"},
        },
    }

    def __init__(self, template_service: Any) -> None:
        self._template_service = template_service

    async def _do_execute(self, input_data: dict[str, Any], context: ToolContext) -> ToolResult:
        try:
            template_type = input_data["template_type"]
            variables = input_data["variables"]

            result = self._template_service.generate(
                template_type=template_type,
                variables=variables,
            )

            return ToolResult(
                success=True,
                data={
                    "rendered_text": result.get("rendered_text", ""),
                },
            )
        except Exception as e:
            return ToolResult(success=False, error=str(e))
