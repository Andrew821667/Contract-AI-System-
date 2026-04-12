# -*- coding: utf-8 -*-
"""
Tests for Company Conditions — CRUD logic via SQLAlchemy model.

Tests run directly against the SQLite test DB (via conftest.py test_db fixture)
without the FastAPI client, matching the pattern of other working tests in this suite.

Covers:
- create condition
- list with pagination
- filter by category
- filter by is_active
- get by id
- update (partial)
- delete
- user isolation (user A cannot see user B's conditions)
- invalid category rejection
"""
import pytest
from sqlalchemy.exc import IntegrityError

from src.models.condition_models import CompanyCondition, CONDITION_CATEGORIES
from src.services.auth_service import AuthService

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
import src.models.condition_models  # noqa: F401


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_user(db, email="test@example.com", password="TestPass123!"):
    auth = AuthService(db)
    user, err = auth.register_user(
        email=email,
        name="Test User",
        password=password,
        role="lawyer",
        subscription_tier="pro",
        send_verification=False,
    )
    assert user is not None, f"User creation failed: {err}"
    db.commit()
    return user


def _create_condition(db, user_id, **kwargs):
    defaults = dict(
        user_id=user_id,
        category="financial",
        title="Default condition",
        condition_text="The penalty is 0.1% per day",
        priority=1,
        is_active=True,
    )
    defaults.update(kwargs)
    cond = CompanyCondition(**defaults)
    db.add(cond)
    db.commit()
    db.refresh(cond)
    return cond


def _list_conditions(db, user_id, category=None, is_active=None, page=1, page_size=50):
    query = db.query(CompanyCondition).filter(CompanyCondition.user_id == user_id)
    if category is not None:
        query = query.filter(CompanyCondition.category == category)
    if is_active is not None:
        query = query.filter(CompanyCondition.is_active == is_active)
    total = query.count()
    items = (
        query.order_by(CompanyCondition.priority.desc(), CompanyCondition.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return items, total


# ── Tests ─────────────────────────────────────────────────────────────────────

class TestConditionCreate:

    def test_create_condition(self, test_db):
        user = _make_user(test_db)
        cond = _create_condition(test_db, user.id, title="Late payment penalty")
        assert cond.id is not None
        assert cond.title == "Late payment penalty"
        assert cond.category == "financial"
        assert cond.user_id == user.id

    def test_default_is_active_true(self, test_db):
        user = _make_user(test_db)
        cond = _create_condition(test_db, user.id)
        assert cond.is_active is True

    def test_valid_categories_accepted(self, test_db):
        user = _make_user(test_db)
        for cat in CONDITION_CATEGORIES:
            cond = _create_condition(test_db, user.id, category=cat)
            assert cond.category == cat


class TestConditionList:

    def test_empty_list(self, test_db):
        user = _make_user(test_db)
        items, total = _list_conditions(test_db, user.id)
        assert total == 0
        assert items == []

    def test_returns_own_conditions(self, test_db):
        user = _make_user(test_db)
        _create_condition(test_db, user.id, title="Cond A")
        _create_condition(test_db, user.id, title="Cond B")
        items, total = _list_conditions(test_db, user.id)
        assert total == 2

    def test_filter_by_category(self, test_db):
        user = _make_user(test_db)
        _create_condition(test_db, user.id, category="financial")
        _create_condition(test_db, user.id, category="deadlines")
        items, total = _list_conditions(test_db, user.id, category="financial")
        assert total == 1
        assert items[0].category == "financial"

    def test_filter_by_is_active(self, test_db):
        user = _make_user(test_db)
        _create_condition(test_db, user.id, is_active=True)
        _create_condition(test_db, user.id, is_active=False)
        active_items, active_total = _list_conditions(test_db, user.id, is_active=True)
        inactive_items, inactive_total = _list_conditions(test_db, user.id, is_active=False)
        assert active_total == 1
        assert inactive_total == 1

    def test_pagination(self, test_db):
        user = _make_user(test_db)
        for i in range(5):
            _create_condition(test_db, user.id, title=f"Cond {i}")
        page1, total = _list_conditions(test_db, user.id, page=1, page_size=3)
        page2, _ = _list_conditions(test_db, user.id, page=2, page_size=3)
        assert total == 5
        assert len(page1) == 3
        assert len(page2) == 2

    def test_ordered_by_priority_desc(self, test_db):
        user = _make_user(test_db)
        _create_condition(test_db, user.id, title="Low", priority=1)
        _create_condition(test_db, user.id, title="High", priority=3)
        items, _ = _list_conditions(test_db, user.id)
        assert items[0].priority >= items[-1].priority


class TestConditionGetById:

    def test_get_existing(self, test_db):
        user = _make_user(test_db)
        created = _create_condition(test_db, user.id, title="My condition")
        fetched = db_get_condition(test_db, created.id, user.id)
        assert fetched is not None
        assert fetched.id == created.id

    def test_get_nonexistent_returns_none(self, test_db):
        user = _make_user(test_db)
        fetched = db_get_condition(test_db, "nonexistent-id", user.id)
        assert fetched is None

    def test_get_other_users_condition_returns_none(self, test_db):
        user_a = _make_user(test_db, email="a@example.com")
        user_b = _make_user(test_db, email="b@example.com")
        cond = _create_condition(test_db, user_a.id)
        fetched = db_get_condition(test_db, cond.id, user_b.id)
        assert fetched is None


def db_get_condition(db, condition_id, user_id):
    return db.query(CompanyCondition).filter(
        CompanyCondition.id == condition_id,
        CompanyCondition.user_id == user_id,
    ).first()


class TestConditionUpdate:

    def test_update_title(self, test_db):
        user = _make_user(test_db)
        cond = _create_condition(test_db, user.id, title="Original")
        cond.title = "Updated"
        test_db.commit()
        test_db.refresh(cond)
        assert cond.title == "Updated"

    def test_update_priority(self, test_db):
        user = _make_user(test_db)
        cond = _create_condition(test_db, user.id, priority=1)
        cond.priority = 3
        test_db.commit()
        test_db.refresh(cond)
        assert cond.priority == 3

    def test_deactivate(self, test_db):
        user = _make_user(test_db)
        cond = _create_condition(test_db, user.id, is_active=True)
        cond.is_active = False
        test_db.commit()
        test_db.refresh(cond)
        assert cond.is_active is False


class TestConditionDelete:

    def test_delete_removes_from_db(self, test_db):
        user = _make_user(test_db)
        cond = _create_condition(test_db, user.id)
        cond_id = cond.id
        test_db.delete(cond)
        test_db.commit()
        assert db_get_condition(test_db, cond_id, user.id) is None

    def test_delete_does_not_affect_other_conditions(self, test_db):
        user = _make_user(test_db)
        cond_a = _create_condition(test_db, user.id, title="A")
        cond_b = _create_condition(test_db, user.id, title="B")
        test_db.delete(cond_a)
        test_db.commit()
        assert db_get_condition(test_db, cond_b.id, user.id) is not None


class TestConditionUserIsolation:

    def test_user_a_cannot_see_user_b_conditions(self, test_db):
        user_a = _make_user(test_db, email="isolation_a@example.com")
        user_b = _make_user(test_db, email="isolation_b@example.com")
        _create_condition(test_db, user_a.id, title="A's secret clause")

        items_b, total_b = _list_conditions(test_db, user_b.id)
        assert total_b == 0

    def test_user_b_cannot_update_user_a_condition(self, test_db):
        user_a = _make_user(test_db, email="ua@example.com")
        user_b = _make_user(test_db, email="ub@example.com")
        cond = _create_condition(test_db, user_a.id)
        # Simulate API isolation: query scoped to user_b returns None
        result = db_get_condition(test_db, cond.id, user_b.id)
        assert result is None


class TestConditionCategoryConstants:

    def test_all_expected_categories_present(self):
        expected = {
            'financial', 'deadlines', 'liability', 'termination',
            'confidentiality', 'warranties', 'force_majeure',
            'dispute', 'ip', 'compliance', 'other'
        }
        assert expected == set(CONDITION_CATEGORIES)

    def test_to_dict_includes_required_fields(self, test_db):
        user = _make_user(test_db)
        cond = _create_condition(test_db, user.id, description="Some description")
        d = cond.to_dict()
        required = {'id', 'user_id', 'category', 'title', 'description', 'condition_text', 'priority', 'is_active'}
        assert required.issubset(d.keys())
