"""
Contract Generator Tool — адаптер для src.services.contract_generation_service.

Генерация документов по шаблону.
"""

from __future__ import annotations

from typing import Any

from src.core.base import ToolContext, ToolResult
from .base_tool_adapter import BaseToolAdapter


class ContractGeneratorTool(BaseToolAdapter):
    """Обёртка ContractGenerationService → ITool."""

    _tool_id = "contract_generator"
    _name = "Генератор договоров"
    _description = "Генерирует договор по шаблону и параметрам"
    _permissions = ["contract.write", "generation.execute"]
    _policy_tags = ["generation", "document"]
    _risk_level = "high"
    _sync_mode = "async"

    _input_schema = {
        "type": "object",
        "properties": {
            "contract_type": {"type": "string"},
            "template_id": {"type": "string"},
            "parameters": {"type": "object"},
        },
        "required": ["contract_type", "parameters"],
    }

    _output_schema = {
        "type": "object",
        "properties": {
            "document_id": {"type": "string"},
            "content": {"type": "string"},
            "format": {"type": "string"},
        },
    }

    def __init__(self, generation_service: Any) -> None:
        self._generator = generation_service

    async def _do_execute(self, input_data: dict[str, Any], context: ToolContext) -> ToolResult:
        try:
            result = self._generator.generate(
                contract_type=input_data["contract_type"],
                template_id=input_data.get("template_id"),
                parameters=input_data["parameters"],
            )

            return ToolResult(
                success=True,
                data={
                    "document_id": result.get("document_id", ""),
                    "content": result.get("content", ""),
                    "format": result.get("format", "docx"),
                },
            )
        except Exception as e:
            return ToolResult(success=False, error=str(e))
