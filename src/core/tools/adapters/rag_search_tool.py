"""
RAG Search Tool — адаптер для src.services.rag_service / enhanced_rag.

Семантический поиск по базе знаний (ChromaDB).
"""

from __future__ import annotations

from typing import Any

from src.core.base import ToolContext, ToolResult
from .base_tool_adapter import BaseToolAdapter


class RAGSearchTool(BaseToolAdapter):
    """Обёртка RAGService → ITool."""

    _tool_id = "rag_search"
    _name = "Поиск по базе знаний"
    _description = "Семантический поиск по юридическим документам и прецедентам"
    _permissions = ["knowledge_base.read"]
    _policy_tags = ["search", "rag", "knowledge"]
    _risk_level = "low"
    _sync_mode = "sync"

    _input_schema = {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Поисковый запрос"},
            "top_k": {"type": "integer", "default": 5, "minimum": 1, "maximum": 20},
            "doc_type_filter": {"type": "string"},
        },
        "required": ["query"],
    }

    _output_schema = {
        "type": "object",
        "properties": {
            "results": {"type": "array"},
            "count": {"type": "integer"},
        },
    }

    def __init__(self, rag_service: Any) -> None:
        self._rag = rag_service

    async def _do_execute(self, input_data: dict[str, Any], context: ToolContext) -> ToolResult:
        try:
            query = input_data["query"]
            top_k = input_data.get("top_k", 5)

            results = self._rag.search(query=query, top_k=top_k)

            return ToolResult(
                success=True,
                data={
                    "results": results if isinstance(results, list) else [],
                    "count": len(results) if isinstance(results, list) else 0,
                },
            )
        except Exception as e:
            return ToolResult(success=False, error=str(e))
