"""Agent Adapters — обёртки legacy-агентов в IAgent protocol."""

from .base_agent_adapter import BaseAgentAdapter
from .registry_bootstrap import bootstrap_agent_registry

__all__ = [
    "BaseAgentAdapter",
    "bootstrap_agent_registry",
]
