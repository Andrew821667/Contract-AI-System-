# -*- coding: utf-8 -*-
"""
Shared pytest fixtures for API tests.

Each test gets a fresh tmp-file SQLite database.
Both get_db functions (from src.models and src.models.database) are overridden.
"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from fastapi.testclient import TestClient

from src.models.database import Base
from src.models.database import get_db as get_db_database
from src.models import get_db as get_db_models
from src.models.auth_models import User
from src.main import app
from src.services.auth_service import AuthService

# Module-level state shared between fixtures within one test
_current_engine = None
_current_session_factory = None


@pytest.fixture(autouse=True)
def test_db(tmp_path):
    """Create a fresh SQLite DB file per test."""
    global _current_engine, _current_session_factory

    db_path = str(tmp_path / "test.db")
    _current_engine = create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(bind=_current_engine)
    _current_session_factory = sessionmaker(
        autocommit=False, autoflush=False, bind=_current_engine
    )

    db = _current_session_factory()
    try:
        yield db
    finally:
        db.close()
        _current_engine.dispose()
        _current_engine = None
        _current_session_factory = None


def _get_test_db():
    db = _current_session_factory()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture()
def client(test_db):
    """FastAPI TestClient with overridden DB dependency."""
    # Override BOTH get_db functions (models/__init__.py and models/database.py)
    app.dependency_overrides[get_db_database] = _get_test_db
    app.dependency_overrides[get_db_models] = _get_test_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture()
def test_user(test_db) -> User:
    """Create and return a test user."""
    auth = AuthService(test_db)
    user, error = auth.register_user(
        email="test@example.com",
        name="Test User",
        password="TestPass123!",
        role="lawyer",
        subscription_tier="pro",
        send_verification=False,
    )
    assert user is not None, f"Failed to create test user: {error}"
    test_db.commit()
    return user


@pytest.fixture()
def auth_headers(client, test_user) -> dict:
    """Login test_user and return Bearer auth headers."""
    resp = client.post(
        "/api/v1/auth/login",
        data={"username": "test@example.com", "password": "TestPass123!"},
    )
    assert resp.status_code == 200, f"Login failed: {resp.text}"
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
