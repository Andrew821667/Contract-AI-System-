# -*- coding: utf-8 -*-
"""
Shared utilities for contract API routes.
"""
import json
from typing import Any, Dict


def load_json_dict(value: Any) -> Dict[str, Any]:
    """
    Parse a value as a JSON dict. Returns {} on failure.

    Handles: dict (passthrough), JSON string, None, and malformed data.
    Replaces _load_meta() / _json_field() duplicated across route files.
    """
    if isinstance(value, dict):
        return value
    if isinstance(value, str) and value:
        try:
            loaded = json.loads(value)
            return loaded if isinstance(loaded, dict) else {}
        except Exception:
            return {}
    return {}
