# -*- coding: utf-8 -*-
"""
Shared pytest fixtures for API tests.

Each test gets a fresh tmp-file SQLite database for speed and isolation.
The application itself uses PostgreSQL only — SQLite is only for tests.
Both get_db functions (from src.models and src.models.database) are overridden.
"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

try:
    from fastapi.testclient import TestClient
    from src.models.database import get_db as get_db_database
    from src.models.database import get_async_db
    from src.models import get_db as get_db_models
    from src.models.auth_models import User
    from src.main import app
    from src.services.auth_service import AuthService
    _FULL_APP_AVAILABLE = True
except ImportError:
    _FULL_APP_AVAILABLE = False

from src.models.database import Base

# Import core models so Base.metadata sees them
import src.core.identity_org.models
import src.core.policies.models
import src.core.tools.models
import src.core.agents.models
import src.core.ai_collaboration.models
import src.core.orchestrator.models
import src.core.workflow.models
import src.core.collaboration.models
import src.core.templates.models
import src.core.integrations.models
import src.core.graph_rag.models

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


if _FULL_APP_AVAILABLE:
    @pytest.fixture()
    def client(test_db):
        """FastAPI TestClient with overridden DB dependency."""
        app.dependency_overrides[get_db_database] = _get_test_db
        app.dependency_overrides[get_db_models] = _get_test_db
        app.dependency_overrides[get_async_db] = _get_test_db
        _clear_rate_limit_buckets(app)
        with TestClient(app) as c:
            yield c
        app.dependency_overrides.clear()

    def _clear_rate_limit_buckets(application):
        """Walk the entire ASGI middleware stack and clear any rate limiter buckets."""
        visited = set()
        stack = [application]
        while stack:
            obj = stack.pop()
            obj_id = id(obj)
            if obj_id in visited:
                continue
            visited.add(obj_id)
            if hasattr(obj, 'buckets') and isinstance(getattr(obj, 'buckets', None), dict):
                obj.buckets.clear()
            if hasattr(obj, 'app'):
                stack.append(obj.app)
            if hasattr(obj, 'middleware_stack') and obj.middleware_stack:
                stack.append(obj.middleware_stack)

    @pytest.fixture()
    def test_user(test_db) -> "User":
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
