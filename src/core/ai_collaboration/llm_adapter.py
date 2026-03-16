"""
LLM Router Adapter — мост между существующими LLMGateway/ModelRouter и ILLMRouter.

Оборачивает sync-методы LLMGateway в async-интерфейс ILLMRouter,
используя ModelRouter для выбора модели.
"""

from __future__ import annotations

import asyncio
from typing import Any

from loguru import logger

from src.core.base import LLMProfile
from src.services.llm_gateway import LLMGateway
from src.services.model_router import ModelRouter


# Маппинг model name → provider для LLMGateway
_MODEL_TO_PROVIDER: dict[str, str] = {
    "deepseek-v3": "deepseek",
    "deepseek-chat": "deepseek",
    "claude-sonnet-4-20250514": "claude",
    "gpt-4o": "openai",
    "gpt-4o-mini": "openai",
}

# Маппинг task_type → complexity score для ModelRouter
_TASK_COMPLEXITY: dict[str, float] = {
    "collaboration.analysis": 0.7,
    "collaboration.review": 0.6,
    "collaboration.negotiation": 0.7,
    "collaboration.generation": 0.5,
    "collaboration.approval": 0.4,
    "collaboration.intake": 0.3,
    "collaboration.classification": 0.3,
    "collaboration.export": 0.2,
}


def _provider_for_model(model: str) -> str:
    """Определить провайдера по имени модели."""
    provider = _MODEL_TO_PROVIDER.get(model)
    if provider:
        return provider
    # Эвристика по имени
    lower = model.lower()
    if "claude" in lower:
        return "claude"
    if "gpt" in lower:
        return "openai"
    if "deepseek" in lower:
        return "deepseek"
    return "openai"


class LLMRouterAdapter:
    """
    Adapter: оборачивает существующие ModelRouter + LLMGateway как ILLMRouter.

    Реализует async-интерфейс ILLMRouter, используя:
    - ModelRouter.select_model() для выбора модели
    - LLMGateway.call() (sync) для вызова LLM через run_in_executor
    """

    def __init__(self, model_router: ModelRouter | None = None) -> None:
        self._model_router = model_router or ModelRouter()

    async def route(
        self,
        task_type: str,
        sensitivity: str = "normal",
        cost_budget: float | None = None,
        tenant_policy: dict[str, Any] | None = None,
    ) -> LLMProfile:
        """
        Выбрать LLM-модель для задачи.

        Args:
            task_type: Тип задачи (collaboration.analysis, collaboration.review, ...).
            sensitivity: Чувствительность данных (normal, high, restricted).
            cost_budget: Максимальный бюджет на запрос (USD) — пока не используется.
            tenant_policy: Политика tenant — пока не используется.

        Returns:
            LLMProfile с выбранной моделью и параметрами.
        """
        # sensitivity → user_mode
        user_mode = "expert" if sensitivity == "high" else "optimal"

        # task_type → doc_complexity_score
        complexity = _TASK_COMPLEXITY.get(task_type, 0.5)

        model = self._model_router.select_model(
            doc_complexity_score=complexity,
            user_mode=user_mode,
        )

        provider = _provider_for_model(model)

        # Получить cost из config
        config = self._model_router.config
        input_cost, output_cost = config.get_model_costs(model)

        profile = LLMProfile(
            provider=provider,
            model=model,
            temperature=0.3,
            max_tokens=4096,
            cost_per_1k_input=input_cost / 1000.0,
            cost_per_1k_output=output_cost / 1000.0,
            reason=f"task={task_type}, sensitivity={sensitivity}, complexity={complexity:.1f}",
        )

        logger.debug(f"LLMRouterAdapter.route → {model} ({provider}), reason={profile.reason}")
        return profile

    async def call(
        self,
        messages: list[dict[str, str]],
        llm_profile: LLMProfile,
        system_prompt: str | None = None,
    ) -> dict[str, Any]:
        """
        Вызвать LLM через LLMGateway.

        Args:
            messages: Список сообщений [{"role": "user"|"assistant"|"system", "content": "..."}].
            llm_profile: Профиль модели (provider, model, temperature, max_tokens).
            system_prompt: Системный промпт (опционально).

        Returns:
            {"content": str, "tokens_input": int, "tokens_output": int}
        """
        gateway = LLMGateway(provider=llm_profile.provider, model=llm_profile.model)

        # Собрать prompt из messages (LLMGateway принимает единый prompt string)
        prompt = self._build_prompt_from_messages(messages)

        loop = asyncio.get_event_loop()

        # Запуск sync-метода в executor
        try:
            tokens_before_in = gateway.total_input_tokens
            tokens_before_out = gateway.total_output_tokens

            response = await loop.run_in_executor(
                None,
                lambda: gateway.call(
                    prompt=prompt,
                    system_prompt=system_prompt,
                    response_format="text",
                    temperature=llm_profile.temperature,
                    max_tokens=llm_profile.max_tokens,
                ),
            )

            tokens_input = gateway.total_input_tokens - tokens_before_in
            tokens_output = gateway.total_output_tokens - tokens_before_out

            # Если content — dict (json format), привести к строке
            content = response if isinstance(response, str) else str(response)

            logger.info(
                f"LLMRouterAdapter.call → {llm_profile.model}: "
                f"tokens_in={tokens_input}, tokens_out={tokens_output}"
            )

            return {
                "content": content,
                "tokens_input": tokens_input,
                "tokens_output": tokens_output,
            }

        except Exception as exc:
            logger.error(f"LLMRouterAdapter.call failed ({llm_profile.model}): {exc}")
            raise

    @staticmethod
    def _build_prompt_from_messages(messages: list[dict[str, str]]) -> str:
        """
        Склеить список messages в единый prompt для LLMGateway.

        System-сообщения пропускаются (передаются отдельно через system_prompt).
        """
        parts: list[str] = []
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role == "system":
                # System messages передаются отдельным параметром
                continue
            elif role == "assistant":
                parts.append(f"Assistant: {content}")
            else:
                parts.append(f"User: {content}")

        return "\n\n".join(parts)
