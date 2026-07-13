"""Versioned legal-consent helpers shared by auth and document routes."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any


LEGAL_CONSENT_VERSION = "contract_ai_terms_privacy_v1"


def user_has_legal_consent(user: Any) -> bool:
    preferences = user.preferences or {}
    consent = preferences.get("legal_consent") if isinstance(preferences, dict) else None
    return bool(
        isinstance(consent, dict)
        and consent.get("accepted") is True
        and consent.get("version") == LEGAL_CONSENT_VERSION
    )


def record_user_legal_consent(
    user: Any,
    *,
    ip_address: str | None,
    user_agent: str | None,
) -> None:
    preferences = dict(user.preferences or {})
    preferences["legal_consent"] = {
        "accepted": True,
        "version": LEGAL_CONSENT_VERSION,
        "accepted_at": datetime.now(UTC).isoformat(),
        "ip_address": ip_address,
        "user_agent": user_agent,
    }
    user.preferences = preferences
