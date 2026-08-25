#!/usr/bin/env python3
"""Validate the DeepSeek routing policy without credentials or network calls."""

import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.core.llm_models import (  # noqa: E402
    DEEPSEEK_FLASH_MODEL,
    DEEPSEEK_PRO_MODEL,
    normalize_reasoning_model_name,
    normalize_standard_model_name,
    openai_compatible_model_options,
)


def main() -> int:
    flash = openai_compatible_model_options(DEEPSEEK_FLASH_MODEL)
    pro = openai_compatible_model_options(DEEPSEEK_PRO_MODEL)
    checks = {
        "standard route uses Flash": (
            normalize_standard_model_name("deepseek-reasoner") == DEEPSEEK_FLASH_MODEL
        ),
        "reasoning route uses Pro": (
            normalize_reasoning_model_name("deepseek-chat") == DEEPSEEK_PRO_MODEL
        ),
        "Flash disables thinking": (
            flash.get("extra_body") == {"thinking": {"type": "disabled"}}
        ),
        "Pro enables high-effort thinking": (
            pro.get("extra_body")
            == {"thinking": {"type": "enabled"}, "reasoning_effort": "high"}
        ),
    }

    failed = [name for name, passed in checks.items() if not passed]
    for name, passed in checks.items():
        print(f"{'OK' if passed else 'FAIL'}: {name}")

    if failed:
        print(f"Routing policy check failed: {', '.join(failed)}")
        return 1

    print("Routing policy is valid. No credentials or network calls were used.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
