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


class TestDeleteContract:
    """DELETE /api/v1/contracts/{contract_id}"""

    def test_delete_contract(self, client, auth_headers):
        # Upload first
        content = "Договор для удаления."
        file = io.BytesIO(content.encode("utf-8"))
        upload_resp = client.post(
            "/api/v1/contracts/upload",
            headers=auth_headers,
            files={"file": ("delete_me.txt", file, "text/plain")},
            data={"document_type": "contract"},
        )
        assert upload_resp.status_code == 200
        contract_id = upload_resp.json()["contract_id"]

        # Delete
        resp = client.delete(f"/api/v1/contracts/{contract_id}", headers=auth_headers)
        assert resp.status_code == 200

        # Verify gone or marked deleted
        get_resp = client.get(f"/api/v1/contracts/{contract_id}", headers=auth_headers)
        # Either 404 (hard delete) or status == 'deleted' (soft delete)
        if get_resp.status_code == 200:
            assert get_resp.json()["contract"]["status"] == "deleted"
        else:
            assert get_resp.status_code == 404

    def test_delete_nonexistent(self, client, auth_headers):
        resp = client.delete("/api/v1/contracts/nonexistent-id", headers=auth_headers)
        assert resp.status_code == 404

    def test_delete_no_auth(self, client):
        resp = client.delete("/api/v1/contracts/some-id")
        assert resp.status_code in (401, 422)


class TestDownloadContract:
    """GET /api/v1/contracts/{contract_id}/download"""

    def test_download_after_upload(self, client, auth_headers):
        content = "Договор для скачивания."
        file = io.BytesIO(content.encode("utf-8"))
        upload_resp = client.post(
            "/api/v1/contracts/upload",
            headers=auth_headers,
            files={"file": ("download_me.txt", file, "text/plain")},
            data={"document_type": "contract"},
        )
        assert upload_resp.status_code == 200
        contract_id = upload_resp.json()["contract_id"]

        resp = client.get(f"/api/v1/contracts/{contract_id}/download", headers=auth_headers)
        assert resp.status_code == 200
        assert b"\xd0\x94\xd0\xbe\xd0\xb3\xd0\xbe\xd0\xb2\xd0\xbe\xd1\x80" in resp.content  # "Договор" in UTF-8

    def test_download_nonexistent(self, client, auth_headers):
        resp = client.get("/api/v1/contracts/nonexistent-id/download", headers=auth_headers)
        assert resp.status_code == 404

    def test_download_no_auth(self, client):
        resp = client.get("/api/v1/contracts/some-id/download")
        assert resp.status_code in (401, 422)


class TestContractPagination:
    """Pagination and filtering for contract list"""

    def test_pagination_params(self, client, auth_headers):
        resp = client.get("/api/v1/contracts?page=1&page_size=5", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["page"] == 1
        assert data["page_size"] == 5

    def test_page_size_capped(self, client, auth_headers):
        resp = client.get("/api/v1/contracts?page_size=999", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["page_size"] <= 100

    def test_search_filter(self, client, auth_headers):
        resp = client.get("/api/v1/contracts?search=несуществующий", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["total"] == 0
