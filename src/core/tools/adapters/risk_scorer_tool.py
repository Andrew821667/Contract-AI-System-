"""
Risk Scorer Tool — адаптер для src.services.risk_scorer / risk_analyzer.

Оценка рисков контракта.
"""

from __future__ import annotations

from typing import Any

from src.core.base import ToolContext, ToolResult
from .base_tool_adapter import BaseToolAdapter


class RiskScorerTool(BaseToolAdapter):
    """Обёртка RiskAnalyzer/RiskScorer → ITool."""

    _tool_id = "risk_scorer"
    _name = "Оценка рисков"
    _description = "Анализирует риски контракта: финансовые, юридические, операционные"
    _permissions = ["contract.read", "analysis.execute"]
    _policy_tags = ["analysis", "risk"]
    _risk_level = "medium"
    _sync_mode = "async"

    _input_schema = {
        "type": "object",
        "properties": {
            "contract_id": {"type": "string"},
            "contract_text": {"type": "string"},
            "contract_type": {"type": "string"},
        },
        "required": ["contract_text"],
    }

    _output_schema = {
        "type": "object",
        "properties": {
            "overall_score": {"type": "number"},
            "risk_level": {"type": "string"},
            "risks": {"type": "array"},
        },
    }

    def __init__(self, risk_service: Any) -> None:
        self._risk_service = risk_service

    async def _do_execute(self, input_data: dict[str, Any], context: ToolContext) -> ToolResult:
        contract_text = input_data["contract_text"]
        contract_type = input_data.get("contract_type", "general")

        result = self._risk_service.analyze_risks(
            text=contract_text,
            contract_type=contract_type,
        )

        return ToolResult(
            success=True,
            data={
                "overall_score": result.get("overall_score", 0),
                "risk_level": result.get("risk_level", "LOW"),
                "risks": result.get("risks", []),
            },
        )
