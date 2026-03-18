"""
Document Parser Tool — адаптер для src.services.document_parser.

Парсинг документов (PDF, DOCX, XML) → структурированный текст.
"""

from __future__ import annotations

from typing import Any

from src.core.base import ToolContext, ToolResult
from .base_tool_adapter import BaseToolAdapter


class DocumentParserTool(BaseToolAdapter):
    """Обёртка DocumentParser → ITool."""

    _tool_id = "document_parser"
    _name = "Парсер документов"
    _description = "Извлекает текст и структуру из PDF, DOCX, XML файлов"
    _permissions = ["contract.read"]
    _policy_tags = ["parsing", "intake"]
    _risk_level = "low"
    _sync_mode = "sync"

    _input_schema = {
        "type": "object",
        "properties": {
            "file_path": {"type": "string", "description": "Путь к файлу"},
            "file_type": {"type": "string", "enum": ["pdf", "docx", "xml", "txt"]},
        },
        "required": ["file_path"],
    }

    _output_schema = {
        "type": "object",
        "properties": {
            "text": {"type": "string"},
            "sections": {"type": "array"},
            "metadata": {"type": "object"},
        },
    }

    def __init__(self, parser_service: Any) -> None:
        """
        Args:
            parser_service: Экземпляр src.services.document_parser.DocumentParser
        """
        self._parser = parser_service

    async def _do_execute(self, input_data: dict[str, Any], context: ToolContext) -> ToolResult:
        file_path = input_data["file_path"]
        result = self._parser.parse(file_path)
        return ToolResult(
            success=True,
            data={
                "text": result.get("text", ""),
                "sections": result.get("sections", []),
                "metadata": result.get("metadata", {}),
            },
        )
