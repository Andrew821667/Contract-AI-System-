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

@pytest.fixture(autouse=True)
def test_db(tmp_path):
    """Create a fresh SQLite DB file per test. No module-level globals — fully isolated."""
    db_path = str(tmp_path / "test.db")
    engine = create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    db = session_factory()
    try:
        yield db
    finally:
        db.close()
        engine.dispose()


if _FULL_APP_AVAILABLE:
    @pytest.fixture()
    def client(test_db):
        """FastAPI TestClient with overridden DB dependency (closure — no globals)."""
        # Capture the session factory bound to THIS test's engine via closure.
        # Safe for parallel test runs (pytest-xdist) since there are no module globals.
        bound_engine = test_db.bind

        def _get_test_db():
            _session_factory = sessionmaker(autocommit=False, autoflush=False, bind=bound_engine)
            db = _session_factory()
            try:
                yield db
            finally:
                db.close()

        app.dependency_overrides[get_db_database] = _get_test_db
        app.dependency_overrides[get_db_models] = _get_test_db
        app.dependency_overrides[get_async_db] = _get_test_db
        _clear_rate_limit_buckets(app)
        _flush_redis_rate_limits()
        with TestClient(app) as c:
            yield c
        app.dependency_overrides.clear()

    def _flush_redis_rate_limits():
        """Flush Redis rate-limit and auth-cache keys so tests don't bleed into each other."""
        try:
            import redis as _redis
            from config.settings import settings as _s
            r = _redis.Redis.from_url(getattr(_s, "redis_url", "redis://localhost:6379"))
            patterns = ["ratelimit:*", "rate_limit:*", "rl:*", "auth:*"]
            for pat in patterns:
                keys = r.keys(pat)
                if keys:
                    r.delete(*keys)
        except Exception:
            pass  # Redis not available — in-memory buckets already cleared above

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
