"""Explicit charge acknowledgement for live LLM evaluation scripts."""

import os


CONFIRMATION = "I_ACCEPT_API_CHARGES"


def require_live_llm_eval() -> None:
    if os.environ.get("RUN_LIVE_LLM_EVALS") != CONFIRMATION:
        raise SystemExit(
            "Live LLM evaluation is blocked. Set RUN_LIVE_LLM_EVALS="
            f"{CONFIRMATION} only after explicitly approving paid API usage."
        )
