# -*- coding: utf-8 -*-
"""Tests for WebSocket endpoints (/api/v1/ws)."""
import pytest
from src.services.auth_service import AuthService


class TestAnalysisWebSocket:
    """WS /api/v1/ws/analysis/{contract_id}"""

    def test_connect_invalid_token(self, client):
        with pytest.raises(Exception):
            with client.websocket_connect(
                "/api/v1/ws/analysis/fake-contract?token=invalid.token"
            ) as ws:
                ws.receive_json()

    def test_connect_valid_token_contract_not_found(self, client, test_user, test_db):
        """Valid token but contract doesn't exist → close 1008."""
        auth = AuthService(test_db)
        token = auth.create_access_token(test_user.id)

        with pytest.raises(Exception):
            with client.websocket_connect(
                f"/api/v1/ws/analysis/nonexistent-id?token={token}"
            ) as ws:
                ws.receive_json()


class TestNotificationsWebSocket:
    """WS /api/v1/ws/notifications"""

    def test_connect_invalid_token(self, client):
        with pytest.raises(Exception):
            with client.websocket_connect(
                "/api/v1/ws/notifications?token=bad-token"
            ) as ws:
                ws.receive_json()

    def test_connect_valid_token(self, client, test_user, test_db):
        """Valid token → receive 'connected' message."""
        auth = AuthService(test_db)
        token = auth.create_access_token(test_user.id)

        with client.websocket_connect(
            f"/api/v1/ws/notifications?token={token}"
        ) as ws:
            data = ws.receive_json()
            assert data["type"] == "connected"
            assert "user_id" in data
