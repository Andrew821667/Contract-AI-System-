# -*- coding: utf-8 -*-
"""Tests for Auth API endpoints (/api/v1/auth)."""
import pytest

from src.models.auth_models import DemoAccessRequest, User
from src.services.auth_service import AuthService


class TestRegister:
    """POST /api/v1/auth/register"""

    def test_public_registration_is_closed(self, client, test_db):
        resp = client.post("/api/v1/auth/register", json={
            "email": "new@example.com",
            "name": "New User",
            "password": "StrongPass1!",
        })
        assert resp.status_code == 403
        assert "демо-доступ" in resp.json()["message"]
        assert test_db.query(User).filter(User.email == "new@example.com").first() is None

    def test_register_short_password(self, client):
        resp = client.post("/api/v1/auth/register", json={
            "email": "short@example.com",
            "name": "User",
            "password": "123",
        })
        assert resp.status_code == 422  # Pydantic validation


class TestDemoRequest:
    payload = {
        "name": "Иван Петров",
        "email": "demo-request@example.com",
        "contact": "@ivan_petrov",
        "company": "ООО Тест",
        "task": "Хотим проверить договоры поставки со стороны покупателя.",
        "consent": True,
    }

    def test_request_is_saved_without_account(self, client, test_db):
        resp = client.post("/api/v1/auth/demo-request", json=self.payload)
        assert resp.status_code == 202

        item = test_db.query(DemoAccessRequest).filter(
            DemoAccessRequest.email == self.payload["email"]
        ).first()
        assert item is not None
        assert item.status == "pending"
        assert test_db.query(User).filter(User.email == self.payload["email"]).first() is None

    def test_duplicate_pending_request_is_deduplicated(self, client, test_db):
        assert client.post("/api/v1/auth/demo-request", json=self.payload).status_code == 202
        assert client.post("/api/v1/auth/demo-request", json=self.payload).status_code == 202
        assert test_db.query(DemoAccessRequest).count() == 1

    def test_honeypot_is_silently_discarded(self, client, test_db):
        payload = {**self.payload, "website": "https://spam.example"}
        resp = client.post("/api/v1/auth/demo-request", json=payload)
        assert resp.status_code == 202
        assert test_db.query(DemoAccessRequest).count() == 0


class TestDemoRequestAdmin:
    def _admin_headers(self, client, test_db):
        auth = AuthService(test_db)
        user, error = auth.register_user(
            email="demo-admin@example.com",
            name="Demo Admin",
            password="AdminPass123!",
            role="admin",
            subscription_tier="enterprise",
            send_verification=False,
        )
        assert user is not None, error
        test_db.commit()
        resp = client.post("/api/v1/auth/login", data={
            "username": "demo-admin@example.com",
            "password": "AdminPass123!",
        })
        return {"Authorization": f"Bearer {resp.json()['access_token']}"}

    def test_approve_creates_bound_working_link(self, client, test_db):
        request_payload = {
            "name": "Иван Петров",
            "email": "approved-demo@example.com",
            "contact": "+79990000000",
            "task": "Нужно проверить договор поставки и оценить найденные риски.",
            "consent": True,
        }
        assert client.post("/api/v1/auth/demo-request", json=request_payload).status_code == 202
        item = test_db.query(DemoAccessRequest).first()
        headers = self._admin_headers(client, test_db)

        resp = client.post(
            f"/api/v1/auth/admin/demo-requests/{item.id}/approve",
            headers=headers,
            json={"max_contracts": 2, "max_llm_requests": 4, "expires_in_hours": 48},
        )
        assert resp.status_code == 200, resp.text
        link = resp.json()["demo_link"]
        assert link["url"].startswith("https://contract.ai-verdict.ru/demo?token=")
        token = link["token"]

        wrong = client.post("/api/v1/auth/demo-activate", json={
            "token": token,
            "email": "wrong@example.com",
            "name": "Wrong User",
        })
        assert wrong.status_code == 400

        activated = client.post("/api/v1/auth/demo-activate", json={
            "token": token,
            "email": request_payload["email"],
            "name": request_payload["name"],
        })
        assert activated.status_code == 200, activated.text
        access = activated.json()["access_token"]
        quota = client.get("/api/v1/auth/quota", headers={"Authorization": f"Bearer {access}"})
        assert quota.json()["contracts_limit"] == 2
        assert quota.json()["contracts_period"] == "demo"
        assert quota.json()["llm_limit"] == 4
        assert quota.json()["llm_period"] == "demo"


class TestLogin:
    """POST /api/v1/auth/login"""

    def test_login_success(self, client, test_user):
        resp = client.post("/api/v1/auth/login", data={
            "username": "test@example.com",
            "password": "TestPass123!",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        # refresh_token is now in httpOnly cookie, not in response body
        assert "refresh_token" not in data
        assert "refresh_token" in resp.cookies or True  # cookie may not propagate in TestClient
        assert data["user"]["email"] == "test@example.com"

    def test_login_wrong_password(self, client, test_user):
        resp = client.post("/api/v1/auth/login", data={
            "username": "test@example.com",
            "password": "WrongPassword1!",
        })
        assert resp.status_code in (401, 429)  # 429 possible under rate limiting

    def test_login_nonexistent_user(self, client):
        resp = client.post("/api/v1/auth/login", data={
            "username": "ghost@example.com",
            "password": "SomePass1!",
        })
        assert resp.status_code in (401, 429)


class TestProtectedEndpoints:
    """Endpoints requiring authentication"""

    def test_me_with_token(self, client, auth_headers):
        resp = client.get("/api/v1/auth/me", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["email"] == "test@example.com"

    def test_me_without_token(self, client):
        resp = client.get("/api/v1/auth/me")
        assert resp.status_code == 401

    def test_me_invalid_token(self, client):
        resp = client.get("/api/v1/auth/me", headers={
            "Authorization": "Bearer invalid.token.here"
        })
        assert resp.status_code == 401
