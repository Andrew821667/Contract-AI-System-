"""Regression tests for the default no-charge test environment."""

import os


LLM_CREDENTIALS = (
    "OPENAI_API_KEY",
    "ANTHROPIC_API_KEY",
    "DEEPSEEK_API_KEY",
    "GEMINI_API_KEY",
    "GOOGLE_API_KEY",
    "QWEN_API_KEY",
    "PERPLEXITY_API_KEY",
    "YANDEX_API_KEY",
    "DSKEY",
)


def test_llm_credentials_are_blank_without_explicit_charge_opt_in() -> None:
    if os.environ.get("RUN_LIVE_LLM_TESTS") == "I_ACCEPT_API_CHARGES":
        return

    assert all(os.environ.get(key) == "" for key in LLM_CREDENTIALS)

    from config.settings import settings

    assert not settings.openai_api_key
    assert not settings.anthropic_api_key
    assert not settings.deepseek_api_key
