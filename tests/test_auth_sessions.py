"""Регрессии SEC-05 и SEC-07: отзыв токенов и сессии SSO."""
import hashlib
from unittest.mock import Mock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from src.api import dependencies
from src.api.auth import routes
from src.models.auth_models import UserSession
from src.services.auth_service import AuthService


@pytest.fixture(params=["memory", "redis"])
def auth_cache(request, monkeypatch):
    data = {}
    redis = None
    if request.param == "redis":
        redis = Mock()
        redis.get.side_effect = data.get
        redis.setex.side_effect = lambda key, ttl, value: data.__setitem__(key, value)
        redis.delete.side_effect = lambda key: data.pop(key, None)
    monkeypatch.setattr(dependencies, "_get_redis", lambda: redis)
    monkeypatch.setattr(dependencies, "_mem_cache", {})
    return data if redis else dependencies._mem_cache


@pytest.fixture
def api(test_db, auth_cache, monkeypatch):
    app = FastAPI()
    app.include_router(routes.router, prefix="/auth")
    app.dependency_overrides[routes.get_db] = lambda: test_db
    app.dependency_overrides[dependencies.get_db] = lambda: test_db
    monkeypatch.setattr(routes, "SessionLocal", sessionmaker(bind=test_db.bind))
    with TestClient(app) as client:
        yield client


@pytest.fixture
def test_user(test_db):
    user, error = AuthService(test_db).register_user(
        email="test@example.com", name="Test User", password="TestPass123!",
        role="lawyer", subscription_tier="pro", send_verification=False,
    )
    assert user is not None, error
    return user


def _assert_logout_revokes(api, test_db, token, auth_cache):
    headers = {"Authorization": f"Bearer {token}"}
    resp = api.get("/auth/me", headers=headers)
    assert resp.status_code == 200, resp.text
    assert auth_cache
    assert api.post("/auth/logout", headers=headers).status_code == 200
    session = test_db.query(UserSession).filter_by(
        access_token_hash=hashlib.sha256(token.encode()).hexdigest(),
    ).one()
    test_db.refresh(session)
    assert session.revoked
    assert api.get("/auth/me", headers=headers).status_code == 401
    assert not auth_cache


def test_logout_rejects_cached_token(api, test_db, test_user, auth_cache):
    resp = api.post("/auth/login", data={
        "username": test_user.email, "password": "TestPass123!",
    })
    assert resp.status_code == 200, resp.text
    _assert_logout_revokes(api, test_db, resp.json()["access_token"], auth_cache)


@pytest.mark.parametrize("existing_user", [False, True])
def test_sso_creates_revocable_session(
    api, test_db, test_user, auth_cache, monkeypatch, existing_user,
):
    monkeypatch.setattr(routes, "BRIDGE_SECRET", "test-bridge-secret")
    email = test_user.email if existing_user else "sso@example.com"
    resp = api.post("/auth/sso-token", json={
        "platform_token": "test-bridge-secret", "user_email": email,
        "user_name": "SSO User", "org_id": "test-org", "role": "lawyer",
    }, headers={"User-Agent": "sso-test"})
    assert resp.status_code == 200, resp.text
    token = resp.json()["access_token"]
    auth = AuthService(test_db)
    payload = auth.verify_token(token)
    assert payload["source"] == "sso_bridge"
    assert payload["org_id"] == "test-org"
    session = test_db.query(UserSession).filter_by(
        access_token_hash=hashlib.sha256(token.encode()).hexdigest(),
    ).one_or_none()
    assert session is not None
    assert session.user_id == resp.json()["user_id"] == payload["user_id"]
    assert auth.verify_token(session.refresh_token, token_type="refresh")
    assert session.is_valid()
    assert session.user_agent == "sso-test"
    _assert_logout_revokes(api, test_db, token, auth_cache)
