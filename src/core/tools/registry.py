"""
Tool Registry — реестр инструментов.

Все tools регистрируются здесь. Оркестратор и агенты получают tools ТОЛЬКО через registry.
Реализует IToolRegistry.
"""

from __future__ import annotations

from loguru import logger

from src.core.interfaces import ITool


class ToolRegistryService:
    """In-memory реестр инструментов + DB sync."""

    def __init__(self) -> None:
        self._tools: dict[str, ITool] = {}

    def register(self, tool: ITool) -> None:
        """Зарегистрировать инструмент."""
        tid = tool.tool_id
        if tid in self._tools:
            logger.warning(f"Tool '{tid}' уже зарегистрирован — перезаписываем")
        self._tools[tid] = tool
        logger.info(f"Tool зарегистрирован: {tid} ({tool.name})")

    def get(self, tool_id: str) -> ITool | None:
        """Получить инструмент по ID."""
        return self._tools.get(tool_id)

    def list_all(self) -> list[ITool]:
        """Все зарегистрированные инструменты."""
        return list(self._tools.values())

    def list_by_tags(self, tags: list[str]) -> list[ITool]:
        """Инструменты, содержащие хотя бы один из указанных тегов."""
        tag_set = set(tags)
        return [
            t for t in self._tools.values()
            if tag_set & set(t.policy_tags)
        ]

    def list_by_risk_level(self, max_risk: str) -> list[ITool]:
        """Инструменты с risk_level не выше указанного."""
        _order = {"low": 0, "medium": 1, "high": 2, "critical": 3}
        max_idx = _order.get(max_risk, 3)
        return [
            t for t in self._tools.values()
            if _order.get(t.risk_level, 0) <= max_idx
        ]

    def unregister(self, tool_id: str) -> bool:
        """Удалить инструмент из реестра."""
        if tool_id in self._tools:
            del self._tools[tool_id]
            logger.info(f"Tool удалён: {tool_id}")
            return True
        return False

    @property
    def count(self) -> int:
        return len(self._tools)
