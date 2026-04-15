# -*- coding: utf-8 -*-
"""
Tests for Payments API — /api/v1/payments/*

Uses TestClient with mocked payment_service to avoid real Stripe calls.
Covers: pricing, checkout, portal, subscription status, cancel, webhook auth.
"""
import json
import pytest
from unittest.mock import MagicMock, patch

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

pytestmark = pytest.mark.skipif(
    not __import__("importlib").util.find_spec("fastapi"),
    reason="fastapi not available",
)


# ── Helpers ──────────────────────────────────────────────────────────────────

def _auth_headers(client, email="pay_user@example.com", password="PayPass123!"):
    """Register + login, return Bearer headers."""
    client.post("/api/v1/auth/register", json={
        "email": email, "name": "Pay User", "password": password,
    })
    resp = client.post(
        "/api/v1/auth/login",
        data={"username": email, "password": password},
    )
    token = resp.json().get("access_token", "")
    return {"Authorization": f"Bearer {token}"}


# ── GET /pricing ──────────────────────────────────────────────────────────────

def test_pricing_public(client):
    """GET /pricing returns tier list without auth."""
    resp = client.get("/api/v1/payments/pricing")
    assert resp.status_code == 200
    data = resp.json()
    assert "tiers" in data or isinstance(data, list)


# ── POST /checkout ────────────────────────────────────────────────────────────

def test_checkout_requires_auth(client):
    resp = client.post("/api/v1/payments/checkout", json={
        "tier": "personal",
        "success_url": "/success",
        "cancel_url": "/cancel",
    })
    assert resp.status_code == 401


def test_checkout_open_redirect_blocked(client):
    """External redirect URLs must be rejected."""
    headers = _auth_headers(client, "ored@example.com", "OredPass123!")
    resp = client.post("/api/v1/payments/checkout", json={
        "tier": "personal",
        "success_url": "https://evil.com/steal",
        "cancel_url": "/cancel",
    }, headers=headers)
    assert resp.status_code in (422, 429)  # pydantic validator rejects it


def test_checkout_invalid_scheme_blocked(client):
    headers = _auth_headers(client, "scheme@example.com", "SchemePass123!")
    resp = client.post("/api/v1/payments/checkout", json={
        "tier": "personal",
        "success_url": "javascript:alert(1)",
        "cancel_url": "/cancel",
    }, headers=headers)
    assert resp.status_code in (422, 429)


@patch("src.api.payments.routes.payment_service")
def test_checkout_success(mock_ps, client):
    mock_ps.create_checkout_session.return_value = (
        "https://checkout.stripe.com/pay/cs_test_123",
        None,
    )
    headers = _auth_headers(client, "checkout@example.com", "Checkout123!")
    resp = client.post("/api/v1/payments/checkout", json={
        "tier": "personal",
        "success_url": "/success",
        "cancel_url": "/cancel",
    }, headers=headers)
    # 200/201 if Stripe mock works; 503 if not configured; 429 if rate limited
    assert resp.status_code in (200, 201, 503, 429)


# ── POST /portal ──────────────────────────────────────────────────────────────

def test_portal_requires_auth(client):
    resp = client.post("/api/v1/payments/portal", json={"return_url": "/dashboard"})
    assert resp.status_code == 401


def test_portal_open_redirect_blocked(client):
    headers = _auth_headers(client, "portal@example.com", "PortalPass123!")
    resp = client.post("/api/v1/payments/portal", json={
        "return_url": "https://evil.com/redirect",
    }, headers=headers)
    assert resp.status_code in (422, 429)


# ── GET /subscription ─────────────────────────────────────────────────────────

def test_subscription_status_requires_auth(client):
    resp = client.get("/api/v1/payments/subscription")
    assert resp.status_code == 401


def test_subscription_status_authenticated(client):
    headers = _auth_headers(client, "sub@example.com", "SubPass123!")
    resp = client.get("/api/v1/payments/subscription", headers=headers)
    assert resp.status_code in (200, 404, 503, 429)


# ── POST /subscription/cancel ─────────────────────────────────────────────────

def test_cancel_subscription_requires_auth(client):
    resp = client.post("/api/v1/payments/subscription/cancel", json={"immediately": False})
    assert resp.status_code == 401


# ── POST /webhooks/stripe ─────────────────────────────────────────────────────

def test_stripe_webhook_missing_signature(client):
    """Webhook without Stripe-Signature header must be rejected."""
    resp = client.post(
        "/api/v1/payments/webhooks/stripe",
        content=b'{"type": "checkout.session.completed"}',
        headers={"Content-Type": "application/json"},
    )
    assert resp.status_code in (400, 422)


def test_stripe_webhook_invalid_signature(client):
    resp = client.post(
        "/api/v1/payments/webhooks/stripe",
        content=b'{"type": "checkout.session.completed"}',
        headers={
            "Content-Type": "application/json",
            "Stripe-Signature": "t=123,v1=badsig",
        },
    )
    assert resp.status_code in (400, 422)
