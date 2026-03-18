"""
Recommendation Tool — адаптер для RecommendationGenerator.

Генерация рекомендаций на основе findings.
"""

from __future__ import annotations

from typing import Any

from src.core.base import ToolContext, ToolResult
from .base_tool_adapter import BaseToolAdapter


class RecommendationTool(BaseToolAdapter):
    """Обёртка RecommendationGenerator → ITool."""

    _tool_id = "recommendation_generator"
    _name = "Генерация рекомендаций"
    _description = "Генерирует рекомендации на основе найденных проблем и типа контракта"
    _permissions = ["contract.read", "analysis.execute"]
    _policy_tags = ["analysis"]
    _risk_level = "low"
    _sync_mode = "sync"

    _input_schema = {
        "type": "object",
        "properties": {
            "findings": {"type": "array", "items": {"type": "object"}},
            "contract_type": {"type": "string"},
        },
        "required": ["findings", "contract_type"],
    }

    _output_schema = {
        "type": "object",
        "properties": {
            "recommendations": {"type": "array", "items": {"type": "object"}},
        },
    }

    def __init__(self, recommendation_service: Any) -> None:
        self._recommendation_service = recommendation_service

    async def _do_execute(self, input_data: dict[str, Any], context: ToolContext) -> ToolResult:
        findings = input_data["findings"]
        contract_type = input_data["contract_type"]

        result = self._recommendation_service.generate(
            findings=findings,
            contract_type=contract_type,
        )

        return ToolResult(
            success=True,
            data={
                "recommendations": result.get("recommendations", []),
            },
        )
