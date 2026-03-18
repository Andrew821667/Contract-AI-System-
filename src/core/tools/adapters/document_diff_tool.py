"""
Document Diff Tool — адаптер для DocumentDiffService.

Сравнение двух версий документа.
"""

from __future__ import annotations

from typing import Any

from src.core.base import ToolContext, ToolResult
from .base_tool_adapter import BaseToolAdapter


class DocumentDiffTool(BaseToolAdapter):
    """Обёртка DocumentDiffService → ITool."""

    _tool_id = "document_diff"
    _name = "Сравнение документов"
    _description = "Сравнивает две версии документа и выдаёт diff с подсчётом изменений"
    _permissions = ["contract.read"]
    _policy_tags = ["comparison"]
    _risk_level = "low"
    _sync_mode = "sync"

    _input_schema = {
        "type": "object",
        "properties": {
            "text_a": {"type": "string"},
            "text_b": {"type": "string"},
        },
        "required": ["text_a", "text_b"],
    }

    _output_schema = {
        "type": "object",
        "properties": {
            "diff_html": {"type": "string"},
            "changes_count": {"type": "integer"},
        },
    }

    def __init__(self, diff_service: Any) -> None:
        self._diff_service = diff_service

    async def _do_execute(self, input_data: dict[str, Any], context: ToolContext) -> ToolResult:
        text_a = input_data["text_a"]
        text_b = input_data["text_b"]

        result = self._diff_service.compare(text_a=text_a, text_b=text_b)

        return ToolResult(
            success=True,
            data={
                "diff_html": result.get("diff_html", ""),
                "changes_count": result.get("changes_count", 0),
            },
        )
