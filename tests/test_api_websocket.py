# -*- coding: utf-8 -*-
"""Tests for WebSocket endpoints (/api/v1/ws)."""
import pytest
from src.services.auth_service import AuthService
from src.models.auth_models import UserSession
from datetime import datetime, timezone, timedelta


class TestAnalysisWebSocket:
    """WS /api/v1/ws/analysis/{contract_id}"""

    def test_connect_invalid_token(self, client):
        """No auth message within timeout → error."""
        with client.websocket_connect(
            "/api/v1/ws/analysis/fake-contract"
        ) as ws:
            # Send invalid auth message
            ws.send_text('{"type": "auth", "token": "invalid.token"}')
            data = ws.receive_json()
            assert data["type"] == "error"
            assert "Authentication failed" in data["message"]

    def test_connect_valid_token_contract_not_found(self, client, test_user, test_db):
        """Valid token but contract doesn't exist → close 1008."""
        auth = AuthService(test_db)
        token = auth.create_access_token(test_user.id)

        # Create UserSession record (required by _authenticate_ws)
        session = UserSession(
            user_id=test_user.id,
            access_token=token,
            refresh_token="dummy-refresh",
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
            revoked=False,
        )
        test_db.add(session)
        test_db.commit()

        with pytest.raises(Exception):
            with client.websocket_connect(
                "/api/v1/ws/analysis/nonexistent-id"
            ) as ws:
                ws.send_text(f'{{"type": "auth", "token": "{token}"}}')
                ws.receive_json()


class TestNotificationsWebSocket:
    """WS /api/v1/ws/notifications"""

    def test_connect_invalid_token(self, client):
        """Invalid auth message → error."""
        with client.websocket_connect(
            "/api/v1/ws/notifications"
        ) as ws:
            ws.send_text('{"type": "auth", "token": "bad-token"}')
            data = ws.receive_json()
            assert data["type"] == "error"
            assert "Authentication failed" in data["message"]

    def test_connect_valid_token(self, client, test_user, test_db):
        """Valid token → receive 'connected' message."""
        auth = AuthService(test_db)
        token = auth.create_access_token(test_user.id)

        # Create UserSession record (required by _authenticate_ws)
        session = UserSession(
            user_id=test_user.id,
            access_token=token,
            refresh_token="dummy-refresh",
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
            revoked=False,
        )
        test_db.add(session)
        test_db.commit()

        with client.websocket_connect(
            "/api/v1/ws/notifications"
        ) as ws:
            ws.send_text(f'{{"type": "auth", "token": "{token}"}}')
            data = ws.receive_json()
            assert data["type"] == "connected"
            assert "user_id" in data
