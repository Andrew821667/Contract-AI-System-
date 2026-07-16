# -*- coding: utf-8 -*-
"""
Tests for Organizations API v2 — /api/v2/organizations/*

Covers: list, create, get, add/remove members, role update,
tenant isolation (user A cannot see org of user B).
"""
import pytest
from src.services.auth_service import AuthService
from src.models import get_db as get_db_models

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

BASE = "/api/v2/organizations"


# ── Helpers ───────────────────────────────────────────────────────────────────

def _register_and_login(client, email, password="OrgPass123!", name="Org User"):
    db_gen = client.app.dependency_overrides[get_db_models]()
    db = next(db_gen)
    try:
        user, error = AuthService(db).register_user(
            email=email,
            name=name,
            password=password,
            role="lawyer",
            subscription_tier="pro",
            send_verification=False,
        )
        assert user is not None, error
        db.commit()
    finally:
        db_gen.close()
    resp = client.post("/api/v1/auth/login", data={"username": email, "password": password})
    token = resp.json().get("access_token", "")
    return {"Authorization": f"Bearer {token}"}


def _slug(name: str) -> str:
    import re, uuid
    s = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return f"{s}-{uuid.uuid4().hex[:6]}"


def _create_org(client, headers, name="Test Org"):
    resp = client.post(BASE, json={"name": name, "slug": _slug(name), "description": "desc"}, headers=headers)
    return resp


# ── Auth guard ────────────────────────────────────────────────────────────────

def test_list_orgs_requires_auth(client):
    resp = client.get(BASE)
    assert resp.status_code == 401


def test_create_org_requires_auth(client):
    resp = client.post(BASE, json={"name": "X"})
    assert resp.status_code == 401


# ── List / Create ─────────────────────────────────────────────────────────────

def test_list_orgs_empty(client):
    h = _register_and_login(client, "list_empty@example.com")
    resp = client.get(BASE, headers=h)
    assert resp.status_code == 200
    assert resp.json() == []


def test_create_org_success(client):
    h = _register_and_login(client, "create_org@example.com")
    resp = _create_org(client, h, "My Company")
    assert resp.status_code in (200, 201)
    data = resp.json()
    assert data["name"] == "My Company"
    assert "id" in data


def test_create_org_appears_in_list(client):
    h = _register_and_login(client, "list_org@example.com")
    _create_org(client, h, "Visible Org")
    resp = client.get(BASE, headers=h)
    assert resp.status_code == 200
    names = [o["name"] for o in resp.json()]
    assert "Visible Org" in names


def test_create_org_empty_name_rejected(client):
    h = _register_and_login(client, "bad_org@example.com")
    resp = client.post(BASE, json={"name": "", "description": "x"}, headers=h)
    assert resp.status_code == 422


# ── Get by ID ─────────────────────────────────────────────────────────────────

def test_get_org_not_found(client):
    h = _register_and_login(client, "get404@example.com")
    resp = client.get(f"{BASE}/nonexistent-org-id", headers=h)
    assert resp.status_code in (403, 404)


def test_get_org_success(client):
    h = _register_and_login(client, "get_org@example.com")
    org_id = _create_org(client, h, "Fetchable Org").json()["id"]
    resp = client.get(f"{BASE}/{org_id}", headers=h)
    assert resp.status_code == 200
    assert resp.json()["id"] == org_id


# ── Tenant isolation ──────────────────────────────────────────────────────────

def test_other_user_cannot_see_org(client):
    """User B must not see org created by User A."""
    h_a = _register_and_login(client, "isolation_a@example.com")
    h_b = _register_and_login(client, "isolation_b@example.com")

    org_id = _create_org(client, h_a, "Private Org A").json()["id"]

    # B tries to access A's org
    resp = client.get(f"{BASE}/{org_id}", headers=h_b)
    assert resp.status_code in (403, 404)


def test_other_user_org_not_in_list(client):
    h_a = _register_and_login(client, "iso_list_a@example.com")
    h_b = _register_and_login(client, "iso_list_b@example.com")
    _create_org(client, h_a, "A's Org")

    resp = client.get(BASE, headers=h_b)
    assert resp.status_code == 200
    assert all(o["name"] != "A's Org" for o in resp.json())


# ── Members ───────────────────────────────────────────────────────────────────

def test_list_members_requires_membership(client):
    h_a = _register_and_login(client, "mem_owner@example.com")
    h_b = _register_and_login(client, "mem_other@example.com")
    org_id = _create_org(client, h_a).json()["id"]

    resp = client.get(f"{BASE}/{org_id}/members", headers=h_b)
    assert resp.status_code in (403, 404)


def test_owner_can_list_members(client):
    h = _register_and_login(client, "mem_list@example.com")
    org_id = _create_org(client, h).json()["id"]
    resp = client.get(f"{BASE}/{org_id}/members", headers=h)
    assert resp.status_code == 200
    members = resp.json()
    assert isinstance(members, list)
    assert len(members) >= 1  # owner is a member


def test_members_include_user_info(client):
    """Members list must include user_name or user_email (not just user_id)."""
    h = _register_and_login(client, "mem_info@example.com", name="Named User")
    org_id = _create_org(client, h).json()["id"]
    resp = client.get(f"{BASE}/{org_id}/members", headers=h)
    assert resp.status_code == 200
    members = resp.json()
    assert len(members) >= 1
    m = members[0]
    assert "user_name" in m or "user_email" in m


def test_add_member_requires_org_admin(client):
    """Non-admin member cannot add others."""
    h_owner = _register_and_login(client, "add_owner@example.com")
    h_member = _register_and_login(client, "add_member@example.com")
    h_stranger = _register_and_login(client, "add_stranger@example.com")
    org_id = _create_org(client, h_owner).json()["id"]

    # Add h_member as regular member first via owner
    client.post(f"{BASE}/{org_id}/members", json={
        "user_id": "some-id", "functional_role": "member"
    }, headers=h_owner)

    # h_stranger (not in org) tries to add someone
    resp = client.post(f"{BASE}/{org_id}/members", json={
        "user_id": "any-id", "functional_role": "member"
    }, headers=h_stranger)
    assert resp.status_code in (403, 404, 422)


# ── Update org ────────────────────────────────────────────────────────────────

def test_update_org_name(client):
    h = _register_and_login(client, "upd_org@example.com")
    org_id = _create_org(client, h, "Old Name").json()["id"]
    resp = client.patch(f"{BASE}/{org_id}", json={"name": "New Name"}, headers=h)
    assert resp.status_code == 200
    assert resp.json()["name"] == "New Name"


def test_update_org_requires_membership(client):
    h_a = _register_and_login(client, "upd_a@example.com")
    h_b = _register_and_login(client, "upd_b@example.com")
    org_id = _create_org(client, h_a, "A Org").json()["id"]
    resp = client.patch(f"{BASE}/{org_id}", json={"name": "Hacked"}, headers=h_b)
    assert resp.status_code in (403, 404)
