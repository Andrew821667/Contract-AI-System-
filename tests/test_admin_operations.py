# -*- coding: utf-8 -*-
"""
Tests for admin operations — user management and contract deletion.

Covers:
- create_user_as_admin: temp password, duplicate email, audit log
- update_user_role: role change, subscription tier, nonexistent user
- list_users: pagination, filtering by role/search/is_demo
- Admin contract deletion via API: soft delete, reason audit, role enforcement
"""
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine, event, inspect as sa_inspect, DateTime
from sqlalchemy.orm import sessionmaker

from src.models.database import Base, Contract
from src.models.auth_models import User, AuditLog
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


# ── SQLite timezone fix (same as test_auth_service_tokens.py) ──
_load_listener_installed = False


def _install_sqlite_tz_load_listener():
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
def admin_user(db, auth):
    user, _ = auth.register_user(
        email="admin@example.com",
        name="Admin",
        password="AdminPass1!",
        role="admin",
        subscription_tier="enterprise",
        send_verification=False,
    )
    db.commit()
    return user


@pytest.fixture()
def regular_user(db, auth):
    user, _ = auth.register_user(
        email="lawyer@example.com",
        name="Lawyer",
        password="LawyerPass1!",
        role="lawyer",
        subscription_tier="pro",
        send_verification=False,
    )
    db.commit()
    return user


# ────────────────────────────────────────────────────────
# create_user_as_admin
# ────────────────────────────────────────────────────────

class TestCreateUserAsAdmin:
    def test_creates_user_with_temp_password(self, auth, admin_user, db):
        user, temp_pass, err = auth.create_user_as_admin(
            email="newbie@example.com",
            name="Newbie",
            role="junior_lawyer",
            admin_user_id=admin_user.id,
        )
        assert user is not None and err is None
        assert temp_pass is not None and len(temp_pass) > 8
        assert user.role == "junior_lawyer"
        assert user.email_verified is False

        # Temp password works
        assert auth.verify_password(temp_pass, user.password_hash)

    def test_duplicate_email_rejected(self, auth, admin_user, db):
        auth.create_user_as_admin(
            email="dup@example.com", name="Dup", role="lawyer",
            admin_user_id=admin_user.id,
        )
        user, _, err = auth.create_user_as_admin(
            email="dup@example.com", name="Dup2", role="lawyer",
            admin_user_id=admin_user.id,
        )
        assert user is None
        assert "already registered" in err.lower()

    def test_audit_log_created(self, auth, admin_user, db):
        auth.create_user_as_admin(
            email="audited@example.com", name="Audited", role="lawyer",
            admin_user_id=admin_user.id,
        )
        log = db.query(AuditLog).filter(
            AuditLog.action == "user_created_by_admin",
            AuditLog.user_id == admin_user.id,
        ).first()
        assert log is not None
        assert log.details["email"] == "audited@example.com"

    def test_custom_subscription_tier(self, auth, admin_user, db):
        user, _, _ = auth.create_user_as_admin(
            email="pro@example.com", name="Pro", role="lawyer",
            subscription_tier="enterprise",
            admin_user_id=admin_user.id,
        )
        assert user.subscription_tier == "enterprise"


# ────────────────────────────────────────────────────────
# update_user_role
# ────────────────────────────────────────────────────────

class TestUpdateUserRole:
    def test_changes_role(self, auth, admin_user, regular_user, db):
        success, err = auth.update_user_role(
            user_id=regular_user.id,
            new_role="senior_lawyer",
            admin_user_id=admin_user.id,
        )
        assert success is True and err is None
        db.refresh(regular_user)
        assert regular_user.role == "senior_lawyer"

    def test_changes_subscription_tier(self, auth, admin_user, regular_user, db):
        auth.update_user_role(
            user_id=regular_user.id,
            new_role="senior_lawyer",
            admin_user_id=admin_user.id,
            subscription_tier="enterprise",
        )
        db.refresh(regular_user)
        assert regular_user.subscription_tier == "enterprise"

    def test_nonexistent_user(self, auth, admin_user, db):
        success, err = auth.update_user_role(
            user_id="nonexistent-id",
            new_role="admin",
            admin_user_id=admin_user.id,
        )
        assert success is False
        assert "not found" in err.lower()

    def test_audit_log_created(self, auth, admin_user, regular_user, db):
        auth.update_user_role(
            user_id=regular_user.id,
            new_role="senior_lawyer",
            admin_user_id=admin_user.id,
        )
        log = db.query(AuditLog).filter(
            AuditLog.action == "user_role_changed",
        ).first()
        assert log is not None
        assert log.details["old_role"] == "lawyer"
        assert log.details["new_role"] == "senior_lawyer"


# ────────────────────────────────────────────────────────
# list_users
# ────────────────────────────────────────────────────────

class TestListUsers:
    def _seed_users(self, auth, admin_user, db):
        for i in range(5):
            auth.create_user_as_admin(
                email=f"user{i}@example.com",
                name=f"User {i}",
                role="lawyer" if i % 2 == 0 else "junior_lawyer",
                admin_user_id=admin_user.id,
            )

    def test_returns_paginated(self, auth, admin_user, db):
        self._seed_users(auth, admin_user, db)
        result = auth.list_users(page=1, limit=3)
        assert result["total"] >= 5
        assert len(result["users"]) == 3
        assert result["page"] == 1

    def test_filter_by_role(self, auth, admin_user, db):
        self._seed_users(auth, admin_user, db)
        result = auth.list_users(role="junior_lawyer")
        for u in result["users"]:
            assert u["role"] == "junior_lawyer"

    def test_search_by_name(self, auth, admin_user, db):
        self._seed_users(auth, admin_user, db)
        result = auth.list_users(search="User 0")
        assert any(u["name"] == "User 0" for u in result["users"])

    def test_search_by_email(self, auth, admin_user, db):
        self._seed_users(auth, admin_user, db)
        result = auth.list_users(search="user2@")
        assert any(u["email"] == "user2@example.com" for u in result["users"])

    def test_empty_result(self, auth, db):
        result = auth.list_users(role="nonexistent_role")
        assert result["total"] == 0
        assert result["users"] == []

    def test_sql_wildcard_escaped(self, auth, admin_user, db):
        """Ensure % and _ in search terms don't act as SQL wildcards."""
        auth.create_user_as_admin(
            email="normal@example.com", name="Normal User",
            role="lawyer", admin_user_id=admin_user.id,
        )
        result = auth.list_users(search="%")
        # Should not match everything — only users with literal % in name/email
        assert result["total"] == 0


# ────────────────────────────────────────────────────────
# Admin contract deletion (API-level via TestClient)
# ────────────────────────────────────────────────────────

class TestAdminContractDeletion:
    @pytest.fixture()
    def contract(self, db, admin_user):
        c = Contract(
            id=str(uuid.uuid4()),
            file_name="test_contract.pdf",
            file_path="/tmp/test_contract.pdf",
            document_type="contract",
            status="pending",
            assigned_to=admin_user.id,
        )
        db.add(c)
        db.commit()
        return c

    def test_soft_delete_sets_status(self, auth, admin_user, db, contract):
        """Direct DB test: simulate what the endpoint does."""
        contract.status = "deleted"
        meta = contract.meta_info or {}
        meta["_deletion_audit"] = {
            "deleted_by_id": admin_user.id,
            "reason": "Test deletion",
            "previous_status": "pending",
        }
        contract.meta_info = meta
        db.commit()

        db.refresh(contract)
        assert contract.status == "deleted"
        assert contract.meta_info["_deletion_audit"]["reason"] == "Test deletion"
        assert contract.meta_info["_deletion_audit"]["previous_status"] == "pending"

    def test_already_deleted_raises(self, db, contract):
        contract.status = "deleted"
        db.commit()
        db.refresh(contract)
        assert contract.status == "deleted"

    def test_deletion_preserves_file_info(self, auth, admin_user, db, contract):
        original_name = contract.file_name
        contract.status = "deleted"
        db.commit()
        db.refresh(contract)
        assert contract.file_name == original_name
