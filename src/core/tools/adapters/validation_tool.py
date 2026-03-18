"""
Validation Tool — адаптер для ValidationService.

Валидация контракта на корректность.
"""

from __future__ import annotations

from typing import Any

from src.core.base import ToolContext, ToolResult
from .base_tool_adapter import BaseToolAdapter


class ValidationTool(BaseToolAdapter):
    """Обёртка ValidationService → ITool."""

    _tool_id = "contract_validator"
    _name = "Валидация контракта"
    _description = "Проверяет контракт на корректность: обязательные поля, структура, логика"
    _permissions = ["contract.read"]
    _policy_tags = ["validation"]
    _risk_level = "low"
    _sync_mode = "sync"

    _input_schema = {
        "type": "object",
        "properties": {
            "contract_text": {"type": "string"},
            "contract_type": {"type": "string"},
        },
        "required": ["contract_text", "contract_type"],
    }

    _output_schema = {
        "type": "object",
        "properties": {
            "valid": {"type": "boolean"},
            "issues": {"type": "array", "items": {"type": "object"}},
        },
    }

    def __init__(self, validation_service: Any) -> None:
        self._validation_service = validation_service

    async def _do_execute(self, input_data: dict[str, Any], context: ToolContext) -> ToolResult:
        contract_text = input_data["contract_text"]
        contract_type = input_data["contract_type"]

        result = self._validation_service.analyze(
            text=contract_text,
            contract_type=contract_type,
        )

        return ToolResult(
            success=True,
            data={
                "valid": result.get("valid", False),
                "issues": result.get("issues", []),
            },
        )
