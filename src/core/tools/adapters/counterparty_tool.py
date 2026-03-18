"""
Counterparty Tool — адаптер для CounterpartyService.

Поиск информации о контрагенте по ИНН.
"""

from __future__ import annotations

from typing import Any

from src.core.base import ToolContext, ToolResult
from .base_tool_adapter import BaseToolAdapter


class CounterpartyTool(BaseToolAdapter):
    """Обёртка CounterpartyService → ITool."""

    _tool_id = "counterparty_lookup"
    _name = "Проверка контрагента"
    _description = "Поиск информации о контрагенте по ИНН: название, адрес, статус"
    _permissions = ["contract.read"]
    _policy_tags = ["lookup", "verification"]
    _risk_level = "low"
    _sync_mode = "sync"

    _input_schema = {
        "type": "object",
        "properties": {
            "inn": {"type": "string"},
        },
        "required": ["inn"],
    }

    _output_schema = {
        "type": "object",
        "properties": {
            "company_name": {"type": "string"},
            "address": {"type": "string"},
            "status": {"type": "string"},
        },
    }

    def __init__(self, counterparty_service: Any) -> None:
        self._counterparty_service = counterparty_service

    async def _do_execute(self, input_data: dict[str, Any], context: ToolContext) -> ToolResult:
        inn = input_data["inn"]

        result = self._counterparty_service.lookup(inn=inn)

        return ToolResult(
            success=True,
            data={
                "company_name": result.get("company_name", ""),
                "address": result.get("address", ""),
                "status": result.get("status", "unknown"),
            },
        )
