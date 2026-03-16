"""
Clause Library Tool — адаптер для ClauseLibraryService.

Поиск типовых клауз в библиотеке.
"""

from __future__ import annotations

from typing import Any

from src.core.base import ToolContext, ToolResult
from .base_tool_adapter import BaseToolAdapter


class ClauseLibraryTool(BaseToolAdapter):
    """Обёртка ClauseLibraryService → ITool."""

    _tool_id = "clause_library"
    _name = "Библиотека клауз"
    _description = "Поиск типовых клауз по запросу и типу"
    _permissions = ["contract.read"]
    _policy_tags = ["search", "clauses"]
    _risk_level = "low"
    _sync_mode = "sync"

    _input_schema = {
        "type": "object",
        "properties": {
            "query": {"type": "string"},
            "clause_type": {"type": "string"},
        },
        "required": ["query"],
    }

    _output_schema = {
        "type": "object",
        "properties": {
            "clauses": {"type": "array", "items": {"type": "object"}},
        },
    }

    def __init__(self, clause_library_service: Any) -> None:
        self._clause_library_service = clause_library_service

    async def _do_execute(self, input_data: dict[str, Any], context: ToolContext) -> ToolResult:
        try:
            query = input_data["query"]
            clause_type = input_data.get("clause_type")

            result = self._clause_library_service.search(
                query=query,
                clause_type=clause_type,
            )

            return ToolResult(
                success=True,
                data={
                    "clauses": result.get("clauses", []),
                },
            )
        except Exception as e:
            return ToolResult(success=False, error=str(e))
