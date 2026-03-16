"""
Smart Composer Tool — адаптер для SmartComposer.

Генерация текста на основе контекста и инструкции.
"""

from __future__ import annotations

from typing import Any

from src.core.base import ToolContext, ToolResult
from .base_tool_adapter import BaseToolAdapter


class SmartComposerTool(BaseToolAdapter):
    """Обёртка SmartComposer → ITool."""

    _tool_id = "smart_composer"
    _name = "Умный композер"
    _description = "Генерирует текст контракта на основе контекста и инструкции"
    _permissions = ["contract.read", "generation.execute"]
    _policy_tags = ["generation", "negotiation"]
    _risk_level = "medium"
    _sync_mode = "async"

    _input_schema = {
        "type": "object",
        "properties": {
            "context": {"type": "string"},
            "instruction": {"type": "string"},
        },
        "required": ["context", "instruction"],
    }

    _output_schema = {
        "type": "object",
        "properties": {
            "composed_text": {"type": "string"},
        },
    }

    def __init__(self, composer_service: Any) -> None:
        self._composer_service = composer_service

    async def _do_execute(self, input_data: dict[str, Any], context: ToolContext) -> ToolResult:
        try:
            ctx = input_data["context"]
            instruction = input_data["instruction"]

            result = self._composer_service.generate(
                context=ctx,
                instruction=instruction,
            )

            return ToolResult(
                success=True,
                data={
                    "composed_text": result.get("composed_text", ""),
                },
            )
        except Exception as e:
            return ToolResult(success=False, error=str(e))
