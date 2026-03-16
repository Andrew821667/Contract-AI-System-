"""
Agent Registry — реестр специализированных агентов.

Оркестратор делегирует задачи агентам ТОЛЬКО через registry.
"""

from __future__ import annotations

from loguru import logger

from src.core.interfaces import IAgent


class AgentRegistryService:
    """In-memory реестр агентов."""

    def __init__(self) -> None:
        self._agents: dict[str, IAgent] = {}

    def register(self, agent: IAgent) -> None:
        """Зарегистрировать агента."""
        aid = agent.agent_id
        if aid in self._agents:
            logger.warning(f"Agent '{aid}' уже зарегистрирован — перезаписываем")
        self._agents[aid] = agent
        logger.info(f"Agent зарегистрирован: {aid} ({agent.name}, spec={agent.specialization})")

    def get(self, agent_id: str) -> IAgent | None:
        """Получить агента по ID."""
        return self._agents.get(agent_id)

    def list_all(self) -> list[IAgent]:
        """Все зарегистрированные агенты."""
        return list(self._agents.values())

    def find_for_task(self, task_type: str) -> list[IAgent]:
        """Найти агентов, способных выполнить данный тип задачи."""
        return [
            a for a in self._agents.values()
            if task_type in (a.task_types or [])
        ]

    def unregister(self, agent_id: str) -> bool:
        """Удалить агента из реестра."""
        if agent_id in self._agents:
            del self._agents[agent_id]
            logger.info(f"Agent удалён: {agent_id}")
            return True
        return False

    @property
    def count(self) -> int:
        return len(self._agents)
