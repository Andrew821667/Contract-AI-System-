"""
Clause Extractor Tool — адаптер для src.services.clause_extractor.

Извлечение клауз (пунктов) из текста контракта.
"""

from __future__ import annotations

from typing import Any

from src.core.base import ToolContext, ToolResult
from .base_tool_adapter import BaseToolAdapter


class ClauseExtractorTool(BaseToolAdapter):
    """Обёртка ClauseExtractor → ITool."""

    _tool_id = "clause_extractor"
    _name = "Извлечение клауз"
    _description = "Извлекает и классифицирует пункты договора"
    _permissions = ["contract.read", "analysis.execute"]
    _policy_tags = ["analysis", "clauses"]
    _risk_level = "low"
    _sync_mode = "sync"

    _input_schema = {
        "type": "object",
        "properties": {
            "contract_id": {"type": "string"},
            "contract_text": {"type": "string"},
        },
        "required": ["contract_text"],
    }

    _output_schema = {
        "type": "object",
        "properties": {
            "clauses": {"type": "array"},
            "count": {"type": "integer"},
        },
    }

    def __init__(self, extractor_service: Any) -> None:
        self._extractor = extractor_service

    async def _do_execute(self, input_data: dict[str, Any], context: ToolContext) -> ToolResult:
        try:
            text = input_data["contract_text"]
            clauses = self._extractor.extract_clauses(text)

            return ToolResult(
                success=True,
                data={
                    "clauses": clauses if isinstance(clauses, list) else [],
                    "count": len(clauses) if isinstance(clauses, list) else 0,
                },
            )
        except Exception as e:
            return ToolResult(success=False, error=str(e))
