"""
Complexity Scorer Tool — адаптер для ComplexityScorer.

Оценка сложности контракта.
"""

from __future__ import annotations

from typing import Any

from src.core.base import ToolContext, ToolResult
from .base_tool_adapter import BaseToolAdapter


class ComplexityScorerTool(BaseToolAdapter):
    """Обёртка ComplexityScorer → ITool."""

    _tool_id = "complexity_scorer"
    _name = "Оценка сложности"
    _description = "Оценивает сложность контракта: лексическую, структурную, юридическую"
    _permissions = ["contract.read"]
    _policy_tags = ["analysis"]
    _risk_level = "low"
    _sync_mode = "sync"

    _input_schema = {
        "type": "object",
        "properties": {
            "contract_text": {"type": "string"},
        },
        "required": ["contract_text"],
    }

    _output_schema = {
        "type": "object",
        "properties": {
            "complexity_score": {"type": "number"},
            "complexity_level": {"type": "string"},
        },
    }

    def __init__(self, complexity_service: Any) -> None:
        self._complexity_service = complexity_service

    async def _do_execute(self, input_data: dict[str, Any], context: ToolContext) -> ToolResult:
        try:
            contract_text = input_data["contract_text"]

            result = self._complexity_service.analyze(text=contract_text)

            return ToolResult(
                success=True,
                data={
                    "complexity_score": result.get("complexity_score", 0),
                    "complexity_level": result.get("complexity_level", "LOW"),
                },
            )
        except Exception as e:
            return ToolResult(success=False, error=str(e))
