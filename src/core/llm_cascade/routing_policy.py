"""
LLM Routing Policy — tenant/org-level policies для выбора моделей.

Определяет: какие модели разрешены, cost budget, confidentiality level,
local-first vs external toggle.
"""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, field_validator
from loguru import logger
from sqlalchemy.orm import Session

from src.core.llm_models import (
    DEEPSEEK_FLASH_MODEL,
    DEEPSEEK_PRO_MODEL,
    normalize_model_name,
    normalize_reasoning_model_name,
    normalize_standard_model_name,
)


class LLMRoutingPolicy(BaseModel):
    """Политика маршрутизации LLM для tenant/org."""

    # Allowed models (empty = all allowed)
    allowed_models: list[str] = Field(default_factory=list)
    # Blocked models
    blocked_models: list[str] = Field(default_factory=list)
    # Preferred model for standard tasks
    default_model: str | None = None
    # Preferred model for high-sensitivity
    high_sensitivity_model: str | None = None
    # Cost control
    max_cost_per_request_usd: float = 0.50
    daily_budget_usd: float = 50.0
    monthly_budget_usd: float = 1000.0
    # Confidentiality
    confidentiality_level: str = "standard"  # standard | confidential | restricted
    # Local-first: prefer local/on-premise models
    local_first: bool = False
    local_models: list[str] = Field(default_factory=lambda: ["qwen3:7b"])
    # External allowed (if False, only local models used)
    external_allowed: bool = True
    # Fallback mode
    fallback_mode: str = "cascade"  # cascade | local_only | fail_fast | queue
    # Max retries across cascade
    max_cascade_retries: int = 3
    # Temperature overrides by task type
    temperature_overrides: dict[str, float] = Field(default_factory=dict)

    @field_validator("allowed_models", "blocked_models")
    @classmethod
    def normalize_model_lists(cls, models: list[str]) -> list[str]:
        return [normalize_model_name(model) for model in models]

    @field_validator("default_model")
    @classmethod
    def normalize_default_model(cls, model: str | None) -> str | None:
        return normalize_standard_model_name(model) if model else None

    @field_validator("high_sensitivity_model")
    @classmethod
    def normalize_high_sensitivity_model(cls, model: str | None) -> str | None:
        return normalize_reasoning_model_name(model) if model else None

    @field_validator("local_models")
    @classmethod
    def keep_local_models_local(cls, models: list[str]) -> list[str]:
        normalized = [normalize_model_name(model) for model in models]
        cloud_models = {DEEPSEEK_FLASH_MODEL, DEEPSEEK_PRO_MODEL}
        local = [model for model in normalized if model not in cloud_models]
        return local or ["qwen3:7b"]


class LLMRoutingPolicyService:
    """Сервис получения и применения LLM routing policies."""

    # Default policy (platform-level)
    _DEFAULT_POLICY = LLMRoutingPolicy()

    _CACHE_MAX = 128

    def __init__(self, db: Session) -> None:
        self.db = db
        from collections import OrderedDict
        self._policy_cache: OrderedDict[str, LLMRoutingPolicy] = OrderedDict()

    def get_policy(
        self,
        org_id: str | None = None,
        tenant_id: str | None = None,
    ) -> LLMRoutingPolicy:
        """
        Получить LLM routing policy (cascade: tenant -> org -> platform default).
        """
        cache_key = f"{tenant_id or ''}:{org_id or ''}"
        if cache_key in self._policy_cache:
            self._policy_cache.move_to_end(cache_key)
            return self._policy_cache[cache_key]

        # Try to load from DB (Policy table with policy_type="llm_routing")
        from src.core.policies.models import Policy

        policy_data: dict[str, Any] | None = None

        # 1. Org-level
        if org_id:
            p = self.db.query(Policy).filter(
                Policy.level == "organization",
                Policy.scope_id == org_id,
                Policy.policy_type == "llm_routing",
                Policy.active.is_(True),
            ).first()
            if p:
                policy_data = p.rules or {}

        # 2. Tenant-level (if no org policy)
        if policy_data is None and tenant_id:
            p = self.db.query(Policy).filter(
                Policy.level == "tenant",
                Policy.scope_id == tenant_id,
                Policy.policy_type == "llm_routing",
                Policy.active.is_(True),
            ).first()
            if p:
                policy_data = p.rules or {}

        # 3. Platform default
        if policy_data is None:
            p = self.db.query(Policy).filter(
                Policy.level == "platform",
                Policy.policy_type == "llm_routing",
                Policy.active.is_(True),
            ).first()
            if p:
                policy_data = p.rules or {}

        if policy_data:
            try:
                policy = LLMRoutingPolicy(**policy_data)
            except Exception as exc:
                logger.warning(f"Invalid LLM routing policy data: {exc}")
                policy = self._DEFAULT_POLICY
        else:
            policy = self._DEFAULT_POLICY

        self._policy_cache[cache_key] = policy
        if len(self._policy_cache) > self._CACHE_MAX:
            self._policy_cache.popitem(last=False)
        return policy

    def apply_policy(
        self,
        model: str,
        policy: LLMRoutingPolicy,
        task_type: str = "",
        sensitivity: str = "normal",
    ) -> tuple[str, str]:
        """
        Применить policy к выбранной модели.

        Returns: (final_model, reason)
        """
        model = normalize_model_name(model)

        # Check blocked
        if model in policy.blocked_models:
            model = policy.default_model or DEEPSEEK_FLASH_MODEL
            return model, f"Модель заблокирована политикой, переключено на {model}"

        # Check allowed list
        if policy.allowed_models and model not in policy.allowed_models:
            model = policy.allowed_models[0] if policy.allowed_models else DEEPSEEK_FLASH_MODEL
            return model, f"Модель не в списке разрешённых, переключено на {model}"

        # Local-first enforcement
        if policy.local_first and not policy.external_allowed:
            if model not in policy.local_models:
                model = policy.local_models[0] if policy.local_models else "qwen3:7b"
                return model, f"External модели запрещены, переключено на локальную {model}"

        # Sensitivity override
        if sensitivity in ("high", "restricted") and policy.high_sensitivity_model:
            model = policy.high_sensitivity_model
            return model, f"Высокая чувствительность -> {model}"

        # Confidentiality enforcement
        if policy.confidentiality_level == "restricted":
            if model not in policy.local_models:
                model = policy.local_models[0] if policy.local_models else "qwen3:7b"
                return model, f"Restricted confidentiality -> только локальные модели: {model}"

        return model, "Политика применена, модель не изменена"

    def clear_cache(self) -> None:
        """Очистить кеш политик."""
        self._policy_cache.clear()
