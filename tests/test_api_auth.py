# -*- coding: utf-8 -*-
"""Tests for Auth API endpoints (/api/v1/auth)."""
import pytest


class TestRegister:
    """POST /api/v1/auth/register"""

    def test_register_success(self, client):
        resp = client.post("/api/v1/auth/register", json={
            "email": "new@example.com",
            "name": "New User",
            "password": "StrongPass1!",
        })
        assert resp.status_code == 201, f"Register failed: {resp.json()}"
        data = resp.json()
        assert "access_token" in data
        assert data["email"] == "new@example.com"

    def test_register_duplicate_email(self, client):
        payload = {
            "email": "dup@example.com",
            "name": "User One",
            "password": "StrongPass1!",
        }
        resp1 = client.post("/api/v1/auth/register", json=payload)
        assert resp1.status_code == 201

        resp2 = client.post("/api/v1/auth/register", json=payload)
        assert resp2.status_code == 400

    def test_register_short_password(self, client):
        resp = client.post("/api/v1/auth/register", json={
            "email": "short@example.com",
            "name": "User",
            "password": "123",
        })
        assert resp.status_code == 422  # Pydantic validation


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
        assert "refresh_token" in data
        assert data["user"]["email"] == "test@example.com"

    def test_login_wrong_password(self, client, test_user):
        resp = client.post("/api/v1/auth/login", data={
            "username": "test@example.com",
            "password": "WrongPassword1!",
        })
        assert resp.status_code == 401

    def test_login_nonexistent_user(self, client):
        resp = client.post("/api/v1/auth/login", data={
            "username": "ghost@example.com",
            "password": "SomePass1!",
        })
        assert resp.status_code == 401


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
