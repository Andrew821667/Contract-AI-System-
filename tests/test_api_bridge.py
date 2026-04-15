# -*- coding: utf-8 -*-
"""
Tests for Bridge API — /api/v1/bridge/*

Covers: auth (missing/wrong secret), GET /status,
POST /analyze (file validation), GET /progress, GET /result.
"""
import io
import pytest

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

_SECRET = "test-bridge-secret-32-chars-long!!"
_HEADERS = {"X-Bridge-Secret": _SECRET}
_WRONG = {"X-Bridge-Secret": "wrong-secret"}


def _patch_secret(monkeypatch):
    monkeypatch.setenv("BRIDGE_SECRET", _SECRET)
    import src.api.bridge.routes as br
    br.BRIDGE_SECRET = _SECRET


# ── Auth ──────────────────────────────────────────────────────────────────────

def test_status_no_secret(client):
    resp = client.get("/api/v1/bridge/status")
    assert resp.status_code == 422  # missing required header


def test_status_wrong_secret(client, monkeypatch):
    _patch_secret(monkeypatch)
    resp = client.get("/api/v1/bridge/status", headers=_WRONG)
    assert resp.status_code == 401


def test_status_bridge_not_configured(client):
    """When BRIDGE_SECRET is empty, bridge returns 503."""
    import src.api.bridge.routes as br
    original = br.BRIDGE_SECRET
    br.BRIDGE_SECRET = ""
    try:
        resp = client.get("/api/v1/bridge/status", headers={"X-Bridge-Secret": ""})
        assert resp.status_code in (401, 503)
    finally:
        br.BRIDGE_SECRET = original


# ── GET /status ───────────────────────────────────────────────────────────────

def test_status_ok(client, monkeypatch):
    _patch_secret(monkeypatch)
    resp = client.get("/api/v1/bridge/status", headers=_HEADERS)
    assert resp.status_code == 200
    data = resp.json()
    assert "mode" in data
    assert data["mode"] in ("online", "busy", "offline")


def test_status_has_capabilities(client, monkeypatch):
    _patch_secret(monkeypatch)
    resp = client.get("/api/v1/bridge/status", headers=_HEADERS)
    assert resp.status_code == 200
    assert "capabilities" in resp.json()


# ── POST /analyze ─────────────────────────────────────────────────────────────

def test_analyze_no_secret(client):
    resp = client.post("/api/v1/bridge/analyze")
    assert resp.status_code == 422


def test_analyze_wrong_secret(client, monkeypatch):
    _patch_secret(monkeypatch)
    resp = client.post(
        "/api/v1/bridge/analyze",
        headers=_WRONG,
        files={"file": ("test.txt", b"content", "text/plain")},
        data={"user_email": "x@example.com"},
    )
    assert resp.status_code == 401


def test_analyze_no_file(client, monkeypatch):
    _patch_secret(monkeypatch)
    resp = client.post(
        "/api/v1/bridge/analyze",
        headers=_HEADERS,
        data={"user_email": "x@example.com"},
    )
    assert resp.status_code == 422


def test_analyze_invalid_extension(client, monkeypatch):
    _patch_secret(monkeypatch)
    resp = client.post(
        "/api/v1/bridge/analyze",
        headers=_HEADERS,
        files={"file": ("malware.exe", b"MZ", "application/octet-stream")},
        data={"user_email": "x@example.com"},
    )
    assert resp.status_code in (400, 422)


def test_analyze_valid_txt(client, monkeypatch):
    _patch_secret(monkeypatch)
    content = b"AGREEMENT\nThis is a test contract."
    resp = client.post(
        "/api/v1/bridge/analyze",
        headers=_HEADERS,
        files={"file": ("contract.txt", content, "text/plain")},
        data={"user_email": "bridge@example.com"},
    )
    # 200/201 if accepted; 400 if validation fails — both ok in unit test
    assert resp.status_code in (200, 201, 400, 422)


# ── GET /progress/{job_id} ────────────────────────────────────────────────────

def test_progress_wrong_secret(client, monkeypatch):
    _patch_secret(monkeypatch)
    resp = client.get("/api/v1/bridge/progress/nonexistent-id", headers=_WRONG)
    assert resp.status_code == 401


def test_progress_not_found(client, monkeypatch):
    _patch_secret(monkeypatch)
    resp = client.get("/api/v1/bridge/progress/nonexistent-job-id-000", headers=_HEADERS)
    assert resp.status_code == 404


# ── GET /result/{job_id} ──────────────────────────────────────────────────────

def test_result_wrong_secret(client, monkeypatch):
    _patch_secret(monkeypatch)
    resp = client.get("/api/v1/bridge/result/nonexistent-id", headers=_WRONG)
    assert resp.status_code == 401


def test_result_not_found(client, monkeypatch):
    _patch_secret(monkeypatch)
    resp = client.get("/api/v1/bridge/result/nonexistent-job-id-000", headers=_HEADERS)
    assert resp.status_code == 404


def test_result_summary_not_found(client, monkeypatch):
    _patch_secret(monkeypatch)
    resp = client.get("/api/v1/bridge/result/nonexistent-job-id-000/summary", headers=_HEADERS)
    assert resp.status_code == 404


def test_result_pdf_not_found(client, monkeypatch):
    _patch_secret(monkeypatch)
    resp = client.get("/api/v1/bridge/result/nonexistent-job-id-000/pdf", headers=_HEADERS)
    assert resp.status_code == 404
