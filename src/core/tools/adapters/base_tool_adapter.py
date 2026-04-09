"""
Base Tool Adapter — базовый класс для адаптеров существующих сервисов.

Оборачивает существующий сервис в ITool интерфейс,
обеспечивая единообразную валидацию и метаданные.
"""

from __future__ import annotations

from typing import Any

import jsonschema
from loguru import logger

from src.core.base import ToolContext, ToolResult, ValidationResult


class BaseToolAdapter:
    """
    Базовый адаптер: реализует общую логику ITool.

    Подклассы должны определить:
    - _tool_id, _name, _description
    - _input_schema, _output_schema
    - _permissions, _policy_tags, _risk_level, _sync_mode
    - async _do_execute(input_data, context) -> ToolResult
    """

    _tool_id: str = ""
    _name: str = ""
    _description: str = ""
    _input_schema: dict[str, Any] = {}
    _output_schema: dict[str, Any] = {}
    _permissions: list[str] = []
    _policy_tags: list[str] = []
    _risk_level: str = "low"
    _sync_mode: str = "sync"

    @property
    def tool_id(self) -> str:
        return self._tool_id

    @property
    def name(self) -> str:
        return self._name

    @property
    def description(self) -> str:
        return self._description

    @property
    def input_schema(self) -> dict[str, Any]:
        return self._input_schema

    @property
    def output_schema(self) -> dict[str, Any]:
        return self._output_schema

    @property
    def permissions(self) -> list[str]:
        return self._permissions

    @property
    def policy_tags(self) -> list[str]:
        return self._policy_tags

    @property
    def risk_level(self) -> str:
        return self._risk_level

    @property
    def sync_mode(self) -> str:
        return self._sync_mode

    def validate_input(self, input_data: dict[str, Any]) -> ValidationResult:
        """Валидация по JSON Schema."""
        if not self._input_schema:
            return ValidationResult(valid=True)
        try:
            jsonschema.validate(instance=input_data, schema=self._input_schema)
            return ValidationResult(valid=True)
        except jsonschema.ValidationError as e:
            return ValidationResult(valid=False, errors=[e.message])

    def _get_service(self) -> Any:
        """Return the wrapped service. Override in subclasses if attribute name differs."""
        # Convention: first non-None private attr that isn't _tool_id etc.
        for attr in vars(self):
            if attr.startswith("_") and attr not in (
                "_tool_id", "_name", "_description", "_input_schema",
                "_output_schema", "_permissions", "_policy_tags",
                "_risk_level", "_sync_mode",
            ):
                return getattr(self, attr, None)
        return None

    async def execute(self, input_data: dict[str, Any], context: ToolContext) -> ToolResult:
        """Точка входа — делегирует в _do_execute с логированием ошибок."""
        if self._get_service() is None:
            return ToolResult(
                success=False,
                error=f"Tool '{self._tool_id}' недоступен: сервис не инициализирован",
            )
        try:
            return await self._do_execute(input_data, context)
        except Exception as e:
            logger.error(f"Tool {self._tool_id} failed: {e}", exc_info=True)
            return ToolResult(success=False, error=str(e))

    async def _do_execute(self, input_data: dict[str, Any], context: ToolContext) -> ToolResult:
        """Подклассы реализуют этот метод."""
        raise NotImplementedError
