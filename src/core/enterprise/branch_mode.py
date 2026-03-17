"""
Branch Mode — standalone / embedded deployment model.

Standalone: полная автономная инсталляция (own DB, own LLM, own policies)
Embedded: встроен в существующую систему (shared identity, shared tools, delegated policies)
"""
from __future__ import annotations
from enum import Enum
from typing import Any
from pydantic import BaseModel, Field
from loguru import logger
from sqlalchemy.orm import Session


class BranchMode(str, Enum):
    STANDALONE = "standalone"
    EMBEDDED = "embedded"


class BranchConfig(BaseModel):
    """Конфигурация branch mode."""
    mode: BranchMode = BranchMode.STANDALONE
    # Standalone settings
    own_database: bool = True
    own_llm_gateway: bool = True
    own_policies: bool = True
    # Embedded settings — parent system bindings
    parent_system_url: str | None = None
    parent_identity_provider: str | None = None  # URL for shared identity
    shared_tool_registry: bool = False
    shared_policy_bindings: bool = False
    # Sync settings
    sync_enabled: bool = False
    sync_interval_seconds: int = 300  # 5 minutes
    sync_entities: list[str] = Field(
        default_factory=lambda: ["policies", "users", "tools"]
    )


class BranchModeService:
    """Управление режимом развёртывания."""

    def __init__(self, db: Session, config: BranchConfig | None = None) -> None:
        self.db = db
        self.config = config or BranchConfig()

    @property
    def mode(self) -> BranchMode:
        return self.config.mode

    @property
    def is_standalone(self) -> bool:
        return self.config.mode == BranchMode.STANDALONE

    @property
    def is_embedded(self) -> bool:
        return self.config.mode == BranchMode.EMBEDDED

    def get_config(self) -> dict[str, Any]:
        """Получить текущую конфигурацию."""
        return self.config.model_dump()

    def should_use_local(self, resource_type: str) -> bool:
        """Определить, использовать локальный или shared ресурс."""
        if self.is_standalone:
            return True  # Всё локальное
        # In embedded mode — check config
        if resource_type == "identity":
            return self.config.parent_identity_provider is None
        if resource_type == "tools":
            return not self.config.shared_tool_registry
        if resource_type == "policies":
            return not self.config.shared_policy_bindings
        return True  # Default to local

    def get_sync_status(self) -> dict[str, Any]:
        """Статус синхронизации (для embedded mode)."""
        if self.is_standalone:
            return {"mode": "standalone", "sync": "not_applicable"}
        return {
            "mode": "embedded",
            "sync_enabled": self.config.sync_enabled,
            "sync_interval": self.config.sync_interval_seconds,
            "sync_entities": self.config.sync_entities,
            "parent_url": self.config.parent_system_url,
        }
