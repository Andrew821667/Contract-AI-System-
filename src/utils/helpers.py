"""
Utility helpers for Contract AI System
"""
import json
import re
from typing import Any, Optional
from loguru import logger


def safe_parse_json(response: Any, fallback: Any = None, context: str = "") -> Any:
    """
    Safely parse JSON from LLM response.

    Handles:
    - Already parsed dicts/lists (returned as-is)
    - JSON strings
    - Markdown code-fenced JSON (```json ... ```)
    - JSON embedded in text

    Args:
        response: Raw LLM response (str or dict/list)
        fallback: Value to return on failure (default None)
        context: Description for logging (e.g. "risk_analysis")

    Returns:
        Parsed object or fallback value
    """
    if response is None:
        return fallback

    # Already parsed
    if isinstance(response, (dict, list)):
        return response

    if not isinstance(response, str):
        logger.warning(f"[{context}] Unexpected response type: {type(response)}")
        return fallback

    text = response.strip()

    # Remove markdown code fences
    if text.startswith("```"):
        lines = text.split('\n')
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = '\n'.join(lines).strip()

    # Try direct parse
    try:
        return json.loads(text)
    except (json.JSONDecodeError, ValueError):
        pass

    # Try extracting JSON from text
    json_match = re.search(r'(\[.*\]|\{.*\})', text, re.DOTALL)
    if json_match:
        try:
            return json.loads(json_match.group(1))
        except (json.JSONDecodeError, ValueError):
            pass

    logger.warning(f"[{context}] Failed to parse JSON from LLM response: {text[:200]}...")
    return fallback
