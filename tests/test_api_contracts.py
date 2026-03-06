# -*- coding: utf-8 -*-
"""Tests for Contracts API endpoints (/api/v1/contracts)."""
import io
import pytest


class TestListContracts:
    """GET /api/v1/contracts"""

    def test_list_contracts_authenticated(self, client, auth_headers):
        resp = client.get("/api/v1/contracts", headers=auth_headers)
        assert resp.status_code == 200, f"Failed: {resp.status_code} {resp.json()}"
        data = resp.json()
        assert "contracts" in data
        assert "total" in data
        assert isinstance(data["contracts"], list)

    def test_list_contracts_no_auth(self, client):
        resp = client.get("/api/v1/contracts")
        assert resp.status_code in (401, 422)  # 422 when auth header missing entirely


class TestUploadContract:
    """POST /api/v1/contracts/upload"""

    def test_upload_txt_file(self, client, auth_headers):
        import os
        os.makedirs("data/contracts", exist_ok=True)

        content = "Договор поставки\n1. Предмет договора\nПоставщик обязуется поставить товар."
        file = io.BytesIO(content.encode("utf-8"))
        resp = client.post(
            "/api/v1/contracts/upload",
            headers=auth_headers,
            files={"file": ("test_contract.txt", file, "text/plain")},
            data={"document_type": "contract"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "contract_id" in data

    def test_upload_no_auth(self, client):
        file = io.BytesIO(b"test content")
        resp = client.post(
            "/api/v1/contracts/upload",
            files={"file": ("test.txt", file, "text/plain")},
        )
        assert resp.status_code in (401, 422)

    def test_upload_no_file(self, client, auth_headers):
        resp = client.post("/api/v1/contracts/upload", headers=auth_headers)
        assert resp.status_code == 422  # Missing required file


class TestGetContract:
    """GET /api/v1/contracts/{contract_id}"""

    def test_get_contract_not_found(self, client, auth_headers):
        resp = client.get("/api/v1/contracts/nonexistent-id", headers=auth_headers)
        assert resp.status_code == 404

    def test_get_contract_after_upload(self, client, auth_headers):
        # Upload first
        content = "Договор аренды помещения."
        file = io.BytesIO(content.encode("utf-8"))
        upload_resp = client.post(
            "/api/v1/contracts/upload",
            headers=auth_headers,
            files={"file": ("rent.txt", file, "text/plain")},
            data={"document_type": "contract"},
        )
        assert upload_resp.status_code == 200
        contract_id = upload_resp.json()["contract_id"]

        # Get contract
        resp = client.get(f"/api/v1/contracts/{contract_id}", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["contract"]["status"] == "uploaded"

    def test_get_contract_no_auth(self, client):
        resp = client.get("/api/v1/contracts/some-id")
        assert resp.status_code in (401, 422)
