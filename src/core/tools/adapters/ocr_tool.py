"""
OCR Tool — адаптер для OCRService.

Извлечение текста из файлов (PDF, изображения).
"""

from __future__ import annotations

from typing import Any

from src.core.base import ToolContext, ToolResult
from .base_tool_adapter import BaseToolAdapter


class OCRTool(BaseToolAdapter):
    """Обёртка OCRService → ITool."""

    _tool_id = "ocr_service"
    _name = "OCR распознавание"
    _description = "Извлечение текста из PDF и изображений"
    _permissions = ["contract.read"]
    _policy_tags = ["extraction"]
    _risk_level = "low"
    _sync_mode = "async"

    _input_schema = {
        "type": "object",
        "properties": {
            "file_path": {"type": "string"},
        },
        "required": ["file_path"],
    }

    _output_schema = {
        "type": "object",
        "properties": {
            "extracted_text": {"type": "string"},
        },
    }

    def __init__(self, ocr_service: Any) -> None:
        self._ocr_service = ocr_service

    async def _do_execute(self, input_data: dict[str, Any], context: ToolContext) -> ToolResult:
        try:
            file_path = input_data["file_path"]

            result = self._ocr_service.extract(file_path=file_path)

            return ToolResult(
                success=True,
                data={
                    "extracted_text": result.get("extracted_text", ""),
                },
            )
        except Exception as e:
            return ToolResult(success=False, error=str(e))
