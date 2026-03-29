"""
Cascade Manager — управление 3-уровневой LLM cascade.

Уровни:
1. Orchestration (fast/cheap) — маршрутизация, планирование
2. Agent (domain) — специализированные задачи
3. Tool (deterministic) — вычисления, парсинг, валидация

При недоступности LLM — graceful fallback.
"""
from __future__ import annotations

from typing import Any

from loguru import logger

from .routing_policy import LLMRoutingPolicy, LLMRoutingPolicyService
from .fallback import FallbackHandler, FallbackMode


# Cascade levels with default model preferences
CASCADE_LEVELS: dict[str, dict[str, Any]] = {
    "orchestration": {
        "description": "Fast/cheap — маршрутизация и планирование",
        "preferred_models": ["deepseek-chat", "gemini-2.5-flash"],
        "max_tokens": 2048,
        "temperature": 0.1,
    },
    "agent": {
        "description": "Domain-specific — анализ, генерация, переговоры",
        "preferred_models": ["deepseek-chat", "claude-sonnet-4-6-20250227"],
        "max_tokens": 4096,
        "temperature": 0.3,
    },
    "expert": {
        "description": "Expert — сложные юридические задачи",
        "preferred_models": ["claude-sonnet-4-6-20250227", "gpt-5.4"],
        "max_tokens": 4096,
        "temperature": 0.2,
    },
}


class CascadeManager:
    """
    Управление 3-уровневой cascade.

    Выбирает модель с учётом:
    - Cascade level (orchestration / agent / expert)
    - LLM routing policy (tenant/org)
    - Fallback mode (cascade / local_only / fail_fast / queue)
    """

    def __init__(
        self,
        routing_policy_service: LLMRoutingPolicyService,
        fallback_handler: FallbackHandler,
    ) -> None:
        self.routing_policy_service = routing_policy_service
        self.fallback_handler = fallback_handler

    def select_model_for_level(
        self,
        cascade_level: str,
        task_type: str = "",
        sensitivity: str = "normal",
        org_id: str | None = None,
        tenant_id: str | None = None,
    ) -> dict[str, Any]:
        """
        Выбрать модель для указанного cascade level.

        Returns:
            {"model": str, "temperature": float, "max_tokens": int,
             "reason": str, "fallback_chain": list[str]}
        """
        level_config = CASCADE_LEVELS.get(cascade_level, CASCADE_LEVELS["agent"])
        policy = self.routing_policy_service.get_policy(org_id=org_id, tenant_id=tenant_id)

        # Default model from level
        model = level_config["preferred_models"][0]

        # Apply policy
        model, reason = self.routing_policy_service.apply_policy(
            model=model,
            policy=policy,
            task_type=task_type,
            sensitivity=sensitivity,
        )

        # Temperature: policy override > level default
        temperature = policy.temperature_overrides.get(
            task_type, level_config.get("temperature", 0.3)
        )

        # Build fallback chain based on policy
        fallback_chain = self._build_fallback_chain(model, policy, level_config)

        logger.info(
            f"Cascade select: level={cascade_level}, model={model}, "
            f"reason={reason}, fallbacks={fallback_chain}"
        )

        return {
            "model": model,
            "temperature": temperature,
            "max_tokens": level_config["max_tokens"],
            "reason": reason,
            "fallback_chain": fallback_chain,
            "policy": policy.model_dump(),
        }

    def _build_fallback_chain(
        self,
        primary_model: str,
        policy: LLMRoutingPolicy,
        level_config: dict[str, Any],
    ) -> list[str]:
        """Построить fallback chain с учётом policy."""
        if policy.fallback_mode == "fail_fast":
            return []  # No fallbacks

        if policy.fallback_mode == "local_only":
            return [m for m in policy.local_models if m != primary_model]

        # cascade mode: level preferred -> all available
        chain: list[str] = []
        all_models = ["deepseek-chat", "gemini-2.5-flash", "claude-sonnet-4-6-20250227", "gpt-5.4"]

        # Level preferred first
        for m in level_config.get("preferred_models", []):
            if m != primary_model and m not in chain:
                if m not in policy.blocked_models:
                    if not policy.allowed_models or m in policy.allowed_models:
                        chain.append(m)

        # Then remaining available models
        for m in all_models:
            if m != primary_model and m not in chain:
                if m not in policy.blocked_models:
                    if not policy.allowed_models or m in policy.allowed_models:
                        chain.append(m)

        # Limit by max_cascade_retries
        return chain[: policy.max_cascade_retries]

    async def execute_with_fallback(
        self,
        cascade_level: str,
        call_fn,  # async (model: str, temperature: float, max_tokens: int) -> Any
        task_type: str = "",
        sensitivity: str = "normal",
        org_id: str | None = None,
        tenant_id: str | None = None,
    ) -> dict[str, Any]:
        """
        Выполнить LLM вызов с fallback.

        Args:
            call_fn: async callable(model, temperature, max_tokens) -> response

        Returns:
            {"result": Any, "model_used": str, "attempts": int, "fallback_used": bool}
        """
        selection = self.select_model_for_level(
            cascade_level=cascade_level,
            task_type=task_type,
            sensitivity=sensitivity,
            org_id=org_id,
            tenant_id=tenant_id,
        )

        models_to_try = [selection["model"]] + selection["fallback_chain"]

        for attempt, model in enumerate(models_to_try, start=1):
            try:
                result = await call_fn(
                    model,
                    selection["temperature"],
                    selection["max_tokens"],
                )
                return {
                    "result": result,
                    "model_used": model,
                    "attempts": attempt,
                    "fallback_used": model != selection["model"],
                }
            except Exception as exc:
                logger.warning(
                    f"Cascade attempt {attempt}/{len(models_to_try)} failed "
                    f"(model={model}): {exc}"
                )
                # Record failure for circuit breaker
                self.fallback_handler.record_failure(model)

        # All attempts failed
        fallback_result = await self.fallback_handler.handle_total_failure(
            cascade_level=cascade_level,
            task_type=task_type,
        )

        return {
            "result": fallback_result,
            "model_used": None,
            "attempts": len(models_to_try),
            "fallback_used": True,
        }
