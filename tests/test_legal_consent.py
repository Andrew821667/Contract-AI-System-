from __future__ import annotations

from types import SimpleNamespace

from src.services.legal_consent import (
    LEGAL_CONSENT_VERSION,
    record_user_legal_consent,
    user_has_legal_consent,
)


def test_record_user_legal_consent_preserves_other_preferences() -> None:
    user = SimpleNamespace(preferences={"language": "ru"})

    record_user_legal_consent(
        user,
        ip_address="127.0.0.1",
        user_agent="pytest",
    )

    assert user.preferences["language"] == "ru"
    assert user.preferences["legal_consent"]["accepted"] is True
    assert user.preferences["legal_consent"]["version"] == LEGAL_CONSENT_VERSION
    assert user_has_legal_consent(user)


def test_user_has_legal_consent_rejects_old_version() -> None:
    user = SimpleNamespace(
        preferences={
            "legal_consent": {
                "accepted": True,
                "version": "old-version",
            }
        }
    )

    assert not user_has_legal_consent(user)
