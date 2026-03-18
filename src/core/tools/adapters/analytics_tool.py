"""
Analytics Tool — адаптер для AnalyticsService.

Получение метрик и аналитики.
"""

from __future__ import annotations

from typing import Any

from src.core.base import ToolContext, ToolResult
from .base_tool_adapter import BaseToolAdapter


class AnalyticsTool(BaseToolAdapter):
    """Обёртка AnalyticsService → ITool."""

    _tool_id = "analytics"
    _name = "Аналитика"
    _description = "Получение метрик и аналитики по контрактам за период"
    _permissions = ["analytics.read"]
    _policy_tags = ["analytics"]
    _risk_level = "low"
    _sync_mode = "sync"

    _input_schema = {
        "type": "object",
        "properties": {
            "metric_type": {"type": "string"},
            "date_from": {"type": "string", "format": "date"},
            "date_to": {"type": "string", "format": "date"},
        },
        "required": ["metric_type", "date_from", "date_to"],
    }

    _output_schema = {
        "type": "object",
        "properties": {
            "metrics": {"type": "object"},
        },
    }

    def __init__(self, analytics_service: Any) -> None:
        self._analytics_service = analytics_service

    async def _do_execute(self, input_data: dict[str, Any], context: ToolContext) -> ToolResult:
        metric_type = input_data["metric_type"]
        date_from = input_data["date_from"]
        date_to = input_data["date_to"]

        result = self._analytics_service.analyze(
            metric_type=metric_type,
            date_from=date_from,
            date_to=date_to,
        )

        return ToolResult(
            success=True,
            data={
                "metrics": result.get("metrics", {}),
            },
        )
