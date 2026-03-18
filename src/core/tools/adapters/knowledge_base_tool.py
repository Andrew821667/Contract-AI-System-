"""
Knowledge Base Tool — адаптер для KnowledgeBaseService.

Поиск по базе знаний.
"""

from __future__ import annotations

from typing import Any

from src.core.base import ToolContext, ToolResult
from .base_tool_adapter import BaseToolAdapter


class KnowledgeBaseTool(BaseToolAdapter):
    """Обёртка KnowledgeBaseService → ITool."""

    _tool_id = "knowledge_base"
    _name = "База знаний"
    _description = "Семантический поиск по базе знаний: законы, практика, шаблоны"
    _permissions = ["knowledge.read"]
    _policy_tags = ["search", "knowledge"]
    _risk_level = "low"
    _sync_mode = "sync"

    _input_schema = {
        "type": "object",
        "properties": {
            "query": {"type": "string"},
            "limit": {"type": "integer"},
        },
        "required": ["query"],
    }

    _output_schema = {
        "type": "object",
        "properties": {
            "results": {"type": "array", "items": {"type": "object"}},
        },
    }

    def __init__(self, knowledge_service: Any) -> None:
        self._knowledge_service = knowledge_service

    async def _do_execute(self, input_data: dict[str, Any], context: ToolContext) -> ToolResult:
        query = input_data["query"]
        limit = input_data.get("limit", 10)

        result = self._knowledge_service.search(query=query, limit=limit)

        return ToolResult(
            success=True,
            data={
                "results": result.get("results", []),
            },
        )
