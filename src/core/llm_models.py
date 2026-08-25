"""Central LLM model policy and legacy-name compatibility."""

from __future__ import annotations

from typing import Any


DEEPSEEK_FLASH_MODEL = "deepseek-v4-flash"
DEEPSEEK_PRO_MODEL = "deepseek-v4-pro"

DEEPSEEK_FLASH_INPUT_COST = 0.14
DEEPSEEK_FLASH_OUTPUT_COST = 0.28
DEEPSEEK_PRO_INPUT_COST = 0.435
DEEPSEEK_PRO_OUTPUT_COST = 0.87

_LEGACY_MODEL_ALIASES = {
    "deepseek": DEEPSEEK_FLASH_MODEL,
    "deepseek-chat": DEEPSEEK_FLASH_MODEL,
    "deepseek-v3": DEEPSEEK_FLASH_MODEL,
    "deepseek-v3.2": DEEPSEEK_FLASH_MODEL,
    "deepseek-reasoner": DEEPSEEK_PRO_MODEL,
}


def normalize_model_name(model: str | None, default: str = DEEPSEEK_FLASH_MODEL) -> str:
    """Return a current model id while accepting persisted legacy aliases."""
    if not model:
        return default
    return _LEGACY_MODEL_ALIASES.get(model.strip().lower(), model.strip())


def normalize_standard_model_name(model: str | None) -> str:
    """Keep standard DeepSeek configuration on non-thinking Flash."""
    normalized = normalize_model_name(model)
    if normalized in (DEEPSEEK_FLASH_MODEL, DEEPSEEK_PRO_MODEL):
        return DEEPSEEK_FLASH_MODEL
    return normalized


def normalize_reasoning_model_name(model: str | None) -> str:
    """Keep deep/expert DeepSeek configuration on thinking-enabled Pro."""
    normalized = normalize_model_name(model, DEEPSEEK_PRO_MODEL)
    if normalized in (DEEPSEEK_FLASH_MODEL, DEEPSEEK_PRO_MODEL):
        return DEEPSEEK_PRO_MODEL
    return normalized


def ensure_deepseek_model(model: str | None) -> str:
    """Restrict a DeepSeek provider request to the supported Flash/Pro pair."""
    normalized = normalize_model_name(model)
    if normalized in (DEEPSEEK_FLASH_MODEL, DEEPSEEK_PRO_MODEL):
        return normalized
    return DEEPSEEK_FLASH_MODEL


def is_deepseek_model(model: str | None) -> bool:
    return normalize_model_name(model).startswith("deepseek-")


def is_reasoning_model(model: str | None) -> bool:
    return normalize_model_name(model) == DEEPSEEK_PRO_MODEL


def openai_compatible_model_options(model: str) -> dict[str, Any]:
    """Build OpenAI-client options with an explicit DeepSeek thinking mode."""
    normalized = normalize_model_name(model)
    options: dict[str, Any] = {"model": normalized}
    if normalized == DEEPSEEK_FLASH_MODEL:
        options["extra_body"] = {"thinking": {"type": "disabled"}}
    elif normalized == DEEPSEEK_PRO_MODEL:
        options["extra_body"] = {
            "thinking": {"type": "enabled"},
            "reasoning_effort": "high",
        }
    return options


def model_costs(model: str | None) -> tuple[float, float] | None:
    """Return current DeepSeek input/output prices per million tokens."""
    normalized = normalize_model_name(model)
    if normalized == DEEPSEEK_FLASH_MODEL:
        return DEEPSEEK_FLASH_INPUT_COST, DEEPSEEK_FLASH_OUTPUT_COST
    if normalized == DEEPSEEK_PRO_MODEL:
        return DEEPSEEK_PRO_INPUT_COST, DEEPSEEK_PRO_OUTPUT_COST
    return None


__all__ = [
    "DEEPSEEK_FLASH_MODEL",
    "DEEPSEEK_PRO_MODEL",
    "DEEPSEEK_FLASH_INPUT_COST",
    "DEEPSEEK_FLASH_OUTPUT_COST",
    "DEEPSEEK_PRO_INPUT_COST",
    "DEEPSEEK_PRO_OUTPUT_COST",
    "ensure_deepseek_model",
    "is_deepseek_model",
    "is_reasoning_model",
    "model_costs",
    "normalize_model_name",
    "normalize_reasoning_model_name",
    "normalize_standard_model_name",
    "openai_compatible_model_options",
]
