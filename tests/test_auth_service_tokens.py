# -*- coding: utf-8 -*-
"""
Tests for AuthService — token management, session refresh, password reset,
demo token activation, and login edge cases.

Covers critical security flows:
- JWT creation/verification with iss/aud claims
- Refresh token rotation & token theft detection
- Password reset (hash-only storage, session revocation)
- Demo token single-use enforcement
- Account locking after failed login attempts
"""
import hashlib
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine, event, inspect as sa_inspect, DateTime
from sqlalchemy.orm import sessionmaker

from src.models.database import Base
from src.models.auth_models import (
    User,
    UserSession,
    DemoToken,
    PasswordResetRequest,
    AuditLog,
    LoginAttempt,
)
from src.services.auth_service import AuthService

# Import core models so metadata sees all tables
import src.core.identity_org.models  # noqa: F401
import src.core.policies.models  # noqa: F401
import src.core.tools.models  # noqa: F401
import src.core.agents.models  # noqa: F401
import src.core.ai_collaboration.models  # noqa: F401
import src.core.orchestrator.models  # noqa: F401
import src.core.workflow.models  # noqa: F401
import src.core.collaboration.models  # noqa: F401
import src.core.templates.models  # noqa: F401
import src.core.integrations.models  # noqa: F401
import src.core.graph_rag.models  # noqa: F401


# ── SQLite timezone fix ────────────────────────────────
# SQLite stores datetimes as naive (no timezone). Production uses PostgreSQL
# which preserves timezone. This listener adds UTC tzinfo after ORM load
# so that model methods comparing with datetime.now(timezone.utc) work.

_load_listener_installed = False


def _install_sqlite_tz_load_listener():
    """Add UTC tzinfo to naive datetimes after loading from SQLite."""
    global _load_listener_installed
    if _load_listener_installed:
        return
    _load_listener_installed = True

    @event.listens_for(Base, "load", propagate=True)
    def _add_utc_after_load(target, context):
        mapper = sa_inspect(type(target))
        for prop in mapper.column_attrs:
            for col in prop.columns:
                col_type = getattr(col.type, "impl", col.type)
                if isinstance(col_type, DateTime):
                    val = prop.class_attribute.__get__(target, type(target))
                    if isinstance(val, datetime) and val.tzinfo is None:
                        object.__setattr__(target, prop.key, val.replace(tzinfo=timezone.utc))

    @event.listens_for(Base, "refresh", propagate=True)
    def _add_utc_after_refresh(target, context, attrs):
        mapper = sa_inspect(type(target))
        for prop in mapper.column_attrs:
            for col in prop.columns:
                col_type = getattr(col.type, "impl", col.type)
                if isinstance(col_type, DateTime):
                    val = prop.class_attribute.__get__(target, type(target))
                    if isinstance(val, datetime) and val.tzinfo is None:
                        object.__setattr__(target, prop.key, val.replace(tzinfo=timezone.utc))


_install_sqlite_tz_load_listener()


@pytest.fixture()
def db(tmp_path):
    """Fresh SQLite DB per test."""
    engine = create_engine(
        f"sqlite:///{tmp_path / 'test.db'}",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


@pytest.fixture()
def auth(db):
    return AuthService(db)


@pytest.fixture()
def active_user(db, auth):
    """Registered user with verified email, ready to login."""
    user, err = auth.register_user(
        email="alice@example.com",
        name="Alice",
        password="StrongPass1!",
        role="lawyer",
        subscription_tier="pro",
        send_verification=False,
    )
    assert user and not err
    user.email_verified = True
    db.commit()
    return user


# ────────────────────────────────────────────────────────
# JWT create / verify
# ────────────────────────────────────────────────────────

class TestJWTTokens:
    def test_access_token_roundtrip(self, auth, active_user):
        token = auth.create_access_token(active_user.id)
        payload = auth.verify_token(token, token_type="access")
        assert payload is not None
        assert payload["user_id"] == active_user.id
        assert payload["type"] == "access"
        assert payload["iss"] == "contract-ai-system"
        assert payload["aud"] == "contract-ai-system"

    def test_refresh_token_roundtrip(self, auth, active_user):
        token = auth.create_refresh_token(active_user.id)
        payload = auth.verify_token(token, token_type="refresh")
        assert payload is not None
        assert payload["type"] == "refresh"

    def test_wrong_type_rejected(self, auth, active_user):
        access = auth.create_access_token(active_user.id)
        assert auth.verify_token(access, token_type="refresh") is None

        refresh = auth.create_refresh_token(active_user.id)
        assert auth.verify_token(refresh, token_type="access") is None

    def test_tampered_token_rejected(self, auth, active_user):
        token = auth.create_access_token(active_user.id)
        tampered = token[:-4] + "XXXX"
        assert auth.verify_token(tampered) is None

    def test_reserved_claims_cannot_be_overridden(self, auth, active_user):
        token = auth.create_access_token(
            active_user.id,
            additional_claims={"user_id": "evil", "type": "refresh", "custom": "ok"},
        )
        payload = auth.verify_token(token, token_type="access")
        assert payload["user_id"] == active_user.id  # not "evil"
        assert payload["type"] == "access"  # not "refresh"
        assert payload["custom"] == "ok"  # safe claim passes


# ────────────────────────────────────────────────────────
# Refresh session — token rotation & theft detection
# ────────────────────────────────────────────────────────

class TestRefreshSession:
    def _login(self, auth, email="alice@example.com", password="StrongPass1!"):
        result, err = auth.login_user(email, password)
        assert result and not err, f"Login failed: {err}"
        return result

    def test_refresh_returns_new_tokens(self, auth, active_user, db):
        login = self._login(auth)
        old_access = login["access_token"]
        old_refresh = login["refresh_token"]

        result, err = auth.refresh_session(old_refresh)
        assert result is not None and err is None
        assert result["access_token"] != old_access
        assert result["refresh_token"] != old_refresh
        assert result["token_type"] == "Bearer"

    def test_old_session_revoked_after_refresh(self, auth, active_user, db):
        login = self._login(auth)
        old_refresh = login["refresh_token"]

        auth.refresh_session(old_refresh)

        old_session = db.query(UserSession).filter(
            UserSession.refresh_token == old_refresh,
        ).first()
        assert old_session.revoked is True
        assert old_session.revoke_reason == "refresh_token_rotation"

    def test_reuse_revoked_refresh_token_revokes_all_sessions(self, auth, active_user, db):
        """Token theft detection: reusing a rotated refresh token kills ALL sessions."""
        login = self._login(auth)
        old_refresh = login["refresh_token"]

        # First refresh — valid
        result, _ = auth.refresh_session(old_refresh)
        new_refresh = result["refresh_token"]

        # Second call with OLD refresh token — theft detected
        result2, err = auth.refresh_session(old_refresh)
        assert result2 is None
        assert "Все сессии отозваны" in err

        # Even the new session should be revoked
        new_session = db.query(UserSession).filter(
            UserSession.refresh_token == new_refresh,
        ).first()
        assert new_session.revoked is True
        assert new_session.revoke_reason == "refresh_token_reuse_detected"

        # Audit log for theft
        theft_log = db.query(AuditLog).filter(
            AuditLog.action == "refresh_token_reuse_detected",
        ).first()
        assert theft_log is not None
        assert theft_log.severity == "critical"

    def test_expired_session_rejected(self, auth, active_user, db):
        login = self._login(auth)
        refresh = login["refresh_token"]

        # Expire the session
        session = db.query(UserSession).filter(
            UserSession.refresh_token == refresh,
        ).first()
        session.expires_at = datetime.now(timezone.utc) - timedelta(days=1)
        db.commit()

        result, err = auth.refresh_session(refresh)
        assert result is None
        assert err is not None

    def test_refresh_with_invalid_token_string(self, auth, active_user):
        result, err = auth.refresh_session("completely-invalid-jwt")
        assert result is None
        assert err is not None

    def test_inactive_user_cannot_refresh(self, auth, active_user, db):
        login = self._login(auth)
        refresh = login["refresh_token"]

        active_user.active = False
        db.commit()

        result, err = auth.refresh_session(refresh)
        assert result is None


# ────────────────────────────────────────────────────────
# Password reset
# ────────────────────────────────────────────────────────

class TestPasswordReset:
    def test_request_returns_token_for_existing_user(self, auth, active_user):
        token, err = auth.request_password_reset("alice@example.com")
        assert token is not None
        assert err is None

    def test_request_for_unknown_email_returns_no_error(self, auth, db):
        """Anti-enumeration: unknown email returns None/None, not an error."""
        token, err = auth.request_password_reset("nobody@example.com")
        assert token is None
        assert err is None

    def test_token_stored_as_hash(self, auth, active_user, db):
        token, _ = auth.request_password_reset("alice@example.com")
        token_hash = hashlib.sha256(token.encode()).hexdigest()

        stored = db.query(PasswordResetRequest).filter(
            PasswordResetRequest.token == token_hash,
        ).first()
        assert stored is not None
        assert stored.token != token  # raw token not stored

    def test_reset_changes_password(self, auth, active_user, db):
        token, _ = auth.request_password_reset("alice@example.com")
        success, err = auth.reset_password(token, "NewStrong1!")
        assert success is True and err is None

        # Old password no longer works
        result, _ = auth.login_user("alice@example.com", "StrongPass1!")
        assert result is None

        # New password works
        result, _ = auth.login_user("alice@example.com", "NewStrong1!")
        assert result is not None

    def test_reset_revokes_all_sessions(self, auth, active_user, db):
        login, _ = auth.login_user("alice@example.com", "StrongPass1!")
        assert login is not None

        token, _ = auth.request_password_reset("alice@example.com")
        auth.reset_password(token, "NewStrong1!")

        active_sessions = db.query(UserSession).filter(
            UserSession.user_id == active_user.id,
            UserSession.revoked == False,
        ).count()
        assert active_sessions == 0

    def test_reset_unlocks_account(self, auth, active_user, db):
        active_user.failed_login_attempts = 5
        active_user.locked_until = datetime.now(timezone.utc) + timedelta(hours=1)
        db.commit()

        token, _ = auth.request_password_reset("alice@example.com")
        auth.reset_password(token, "NewStrong1!")

        db.refresh(active_user)
        assert active_user.failed_login_attempts == 0
        assert active_user.locked_until is None

    def test_reset_token_single_use(self, auth, active_user, db):
        token, _ = auth.request_password_reset("alice@example.com")
        auth.reset_password(token, "NewStrong1!")

        # Second use fails
        success, err = auth.reset_password(token, "AnotherPass1!")
        assert success is False

    def test_weak_password_rejected(self, auth, active_user, db):
        token, _ = auth.request_password_reset("alice@example.com")
        success, err = auth.reset_password(token, "weak")
        assert success is False
        assert err is not None

    def test_previous_reset_requests_invalidated(self, auth, active_user, db):
        token1, _ = auth.request_password_reset("alice@example.com")
        token2, _ = auth.request_password_reset("alice@example.com")

        # First token's record should be deleted
        hash1 = hashlib.sha256(token1.encode()).hexdigest()
        stored1 = db.query(PasswordResetRequest).filter(
            PasswordResetRequest.token == hash1,
        ).first()
        assert stored1 is None

        # Second still valid
        success, _ = auth.reset_password(token2, "NewStrong1!")
        assert success is True


# ────────────────────────────────────────────────────────
# Demo token activation
# ────────────────────────────────────────────────────────

class TestDemoTokenActivation:
    @pytest.fixture()
    def demo_token(self, db, active_user):
        token = DemoToken(
            id=str(uuid.uuid4()),
            token="demo-test-token-123",
            max_contracts=3,
            max_llm_requests=10,
            max_file_size_mb=5,
            expires_in_hours=24,
            created_by=active_user.id,
            expires_at=datetime.now(timezone.utc) + timedelta(hours=24),
        )
        db.add(token)
        db.commit()
        return token

    def test_activate_creates_demo_user(self, auth, demo_token, db):
        result, err = auth.activate_demo_token(
            token="demo-test-token-123",
            email="demo@example.com",
            name="Demo User",
        )
        assert result is not None and err is None
        assert result["user"]["role"] == "demo"

        user = db.query(User).filter(User.email == "demo@example.com").first()
        assert user is not None
        assert user.is_demo is True

    def test_activate_single_use(self, auth, demo_token, db):
        auth.activate_demo_token(
            token="demo-test-token-123",
            email="demo1@example.com",
            name="Demo 1",
        )
        result, err = auth.activate_demo_token(
            token="demo-test-token-123",
            email="demo2@example.com",
            name="Demo 2",
        )
        assert result is None
        assert "expired" in err.lower() or "used" in err.lower()

    def test_activate_expired_token(self, auth, db, active_user):
        token = DemoToken(
            id=str(uuid.uuid4()),
            token="expired-demo-token",
            created_by=active_user.id,
            expires_at=datetime.now(timezone.utc) - timedelta(hours=1),
        )
        db.add(token)
        db.commit()

        result, err = auth.activate_demo_token(
            token="expired-demo-token",
            email="demo@example.com",
            name="Demo",
        )
        assert result is None

    def test_activate_invalid_token(self, auth):
        result, err = auth.activate_demo_token(
            token="nonexistent-token",
            email="demo@example.com",
            name="Demo",
        )
        assert result is None
        assert "Invalid" in err

    def test_activate_duplicate_email(self, auth, demo_token, active_user):
        result, err = auth.activate_demo_token(
            token="demo-test-token-123",
            email="alice@example.com",  # already registered
            name="Alice Clone",
        )
        assert result is None
        assert "already registered" in err.lower()


# ────────────────────────────────────────────────────────
# Login edge cases — locking, verification, etc.
# ────────────────────────────────────────────────────────

class TestLoginEdgeCases:
    def test_wrong_password_increments_attempts(self, auth, active_user, db):
        auth.login_user("alice@example.com", "WrongPass1!")
        db.refresh(active_user)
        assert active_user.failed_login_attempts == 1

    def test_account_locks_after_max_attempts(self, auth, active_user, db):
        for _ in range(AuthService.MAX_LOGIN_ATTEMPTS):
            auth.login_user("alice@example.com", "WrongPass1!")

        db.refresh(active_user)
        assert active_user.locked_until is not None

    def test_locked_account_rejects_correct_password(self, auth, active_user, db):
        # Lock by exceeding attempts
        for _ in range(AuthService.MAX_LOGIN_ATTEMPTS):
            auth.login_user("alice@example.com", "WrongPass1!")

        result, err = auth.login_user("alice@example.com", "StrongPass1!")
        assert result is None
        assert "locked" in err.lower()

    def test_successful_login_resets_attempts(self, auth, active_user, db):
        auth.login_user("alice@example.com", "WrongPass1!")
        auth.login_user("alice@example.com", "WrongPass1!")
        db.refresh(active_user)
        assert active_user.failed_login_attempts == 2

        result, _ = auth.login_user("alice@example.com", "StrongPass1!")
        assert result is not None
        db.refresh(active_user)
        assert active_user.failed_login_attempts == 0

    def test_unverified_email_rejected(self, auth, db):
        user, _ = auth.register_user(
            email="unverified@example.com",
            name="Unverified",
            password="StrongPass1!",
            role="lawyer",
            send_verification=False,
        )
        # register_user with send_verification=False auto-verifies;
        # explicitly unset to test the guard
        user.email_verified = False
        db.commit()

        result, err = auth.login_user("unverified@example.com", "StrongPass1!")
        assert result is None
        assert "verify" in err.lower()

    def test_nonexistent_user_returns_generic_error(self, auth):
        result, err = auth.login_user("ghost@example.com", "AnyPass1!")
        assert result is None
        assert err == "Invalid email or password"

    def test_inactive_user_rejected(self, auth, active_user, db):
        active_user.active = False
        db.commit()

        result, err = auth.login_user("alice@example.com", "StrongPass1!")
        assert result is None
        assert "not active" in err.lower()

    def test_successful_login_returns_tokens(self, auth, active_user):
        result, err = auth.login_user("alice@example.com", "StrongPass1!")
        assert err is None
        assert "access_token" in result
        assert "refresh_token" in result
        assert result["token_type"] == "Bearer"

    def test_login_creates_session(self, auth, active_user, db):
        result, _ = auth.login_user("alice@example.com", "StrongPass1!")
        session = db.query(UserSession).filter(
            UserSession.user_id == active_user.id,
        ).first()
        assert session is not None
        assert session.access_token == result["access_token"]
        assert session.revoked is False


# ────────────────────────────────────────────────────────
# Logout
# ────────────────────────────────────────────────────────

class TestLogout:
    def test_logout_revokes_session(self, auth, active_user, db):
        login, _ = auth.login_user("alice@example.com", "StrongPass1!")
        assert auth.logout_user(login["access_token"]) is True

        session = db.query(UserSession).filter(
            UserSession.access_token == login["access_token"],
        ).first()
        assert session.revoked is True
        assert session.revoke_reason == "user_logout"

    def test_logout_unknown_token(self, auth):
        assert auth.logout_user("unknown-token") is False
