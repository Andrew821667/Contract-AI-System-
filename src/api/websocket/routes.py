# -*- coding: utf-8 -*-
"""
WebSocket Routes for Real-Time Updates
Contract analysis progress, notifications, live updates

Performance: DB sessions are short-lived (opened per poll, not per connection).
This prevents connection pool exhaustion with many WebSocket clients.
"""
import json
import asyncio
from typing import Dict, Set
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, Query
from sqlalchemy.orm import Session
from loguru import logger

from src.models.database import get_db, SessionLocal
from src.models import Contract, AnalysisResult
from src.models.auth_models import User, UserSession
from src.services.auth_service import AuthService


router = APIRouter()


class ConnectionManager:
    """Manage WebSocket connections"""

    def __init__(self):
        # Maps: contract_id -> set of websockets
        self.active_connections: Dict[str, Set[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, contract_id: str):
        """Connect client to contract updates"""
        await websocket.accept()
        if contract_id not in self.active_connections:
            self.active_connections[contract_id] = set()
        self.active_connections[contract_id].add(websocket)
        logger.info(f"WebSocket connected for contract {contract_id}. Total: {len(self.active_connections[contract_id])}")

    def disconnect(self, websocket: WebSocket, contract_id: str):
        """Disconnect client"""
        if contract_id in self.active_connections:
            self.active_connections[contract_id].discard(websocket)
            if not self.active_connections[contract_id]:
                del self.active_connections[contract_id]
            logger.info(f"WebSocket disconnected for contract {contract_id}")

    async def send_personal_message(self, message: dict, websocket: WebSocket):
        """Send message to specific client. Returns False if send failed (client gone)."""
        try:
            await websocket.send_json(message)
            return True
        except Exception:
            return False

    async def broadcast_to_contract(self, message: dict, contract_id: str):
        """Broadcast message to all clients watching this contract"""
        if contract_id in self.active_connections:
            disconnected = set()
            for connection in self.active_connections[contract_id]:
                try:
                    await connection.send_json(message)
                except Exception as e:
                    logger.error(f"Error broadcasting to contract {contract_id}: {e}")
                    disconnected.add(connection)

            # Remove disconnected clients
            for conn in disconnected:
                self.active_connections[contract_id].discard(conn)


manager = ConnectionManager()


def _authenticate_ws(db: Session, ws_token: str):
    """Authenticate WebSocket connection. Returns (user_id, user_role, assigned_to_check) or None."""
    auth_service = AuthService(db)
    payload = auth_service.verify_token(ws_token, token_type="access")
    if not payload:
        return None

    user_id = payload.get("user_id")

    # Check session revocation
    session = db.query(UserSession).filter(
        UserSession.user_id == user_id,
        UserSession.access_token == ws_token,
        UserSession.revoked == False
    ).first()
    if not session:
        return None

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return None

    return {"user_id": user.id, "role": user.role}


@router.websocket("/analysis/{contract_id}")
async def websocket_analysis_updates(
    websocket: WebSocket,
    contract_id: str,
    db: Session = Depends(get_db)
):
    """
    WebSocket endpoint for real-time contract analysis updates.

    **Auth:** Send token as first message: {"type": "auth", "token": "ACCESS_TOKEN"}

    **Message types:** progress, status_change, clause_analyzed, risk_found, analysis_complete, error

    **Performance:** DB session is closed after authentication. Short-lived sessions
    are used for periodic status polling to avoid holding connection pool slots.
    """
    # Accept connection first, then authenticate via first message
    await websocket.accept()

    # Wait for auth message (timeout 10s)
    ws_token = None
    try:
        raw = await asyncio.wait_for(websocket.receive_text(), timeout=10.0)
        msg = json.loads(raw)
        if msg.get("type") == "auth" and msg.get("token"):
            ws_token = msg["token"]
    except (asyncio.TimeoutError, json.JSONDecodeError, Exception):
        pass

    if not ws_token:
        try:
            await websocket.send_json({"type": "error", "message": "Authentication failed"})
            await websocket.close(code=1008, reason="Invalid token")
        except Exception:
            pass
        return

    # Authenticate using the injected DB session, then close it
    auth_info = _authenticate_ws(db, ws_token)
    if not auth_info:
        try:
            await websocket.send_json({"type": "error", "message": "Authentication failed"})
            await websocket.close(code=1008, reason="Invalid token")
        except Exception:
            pass
        return

    # Check contract access
    contract = db.query(Contract).filter(Contract.id == contract_id).first()
    if not contract:
        await websocket.close(code=1008, reason="Contract not found")
        return

    if contract.assigned_to != auth_info["user_id"] and auth_info["role"] != "admin":
        await websocket.close(code=1008, reason="Permission denied")
        return

    initial_status = contract.status

    # Close the injected DB session — we'll use short-lived sessions for polling
    db.close()

    # Register connection
    if contract_id not in manager.active_connections:
        manager.active_connections[contract_id] = set()
    manager.active_connections[contract_id].add(websocket)
    logger.info(f"WebSocket connected for contract {contract_id}. Total: {len(manager.active_connections[contract_id])}")

    try:
        # Send initial status
        await manager.send_personal_message({
            "type": "connected",
            "contract_id": contract_id,
            "status": initial_status,
            "message": "Connected to analysis updates"
        }, websocket)

        # Keep connection alive and send updates
        poll_interval = 5  # seconds — increases after idle polls
        idle_polls = 0
        while True:
            await asyncio.sleep(poll_interval)

            # Short-lived DB session for each poll — does not hold pool slot between polls
            poll_db = SessionLocal()
            try:
                # Single query with joined load instead of two separate queries
                contract = poll_db.query(Contract).filter(Contract.id == contract_id).first()
                if not contract:
                    break

                analysis = poll_db.query(AnalysisResult).filter(
                    AnalysisResult.contract_id == contract_id
                ).first()

                current_status = contract.status
                risks_count = len(analysis.risks_by_category) if analysis and analysis.risks_by_category else 0
                recs_count = len(analysis.recommendations) if analysis and analysis.recommendations else 0

                # For final message
                final_analysis_id = analysis.id if analysis else None
                final_risks = len(analysis.risks) if analysis and hasattr(analysis, 'risks') and analysis.risks else 0
                final_recs = len(analysis.recommendations) if analysis and hasattr(analysis, 'recommendations') and analysis.recommendations else 0
            finally:
                poll_db.close()

            # Calculate progress — use granular progress from meta_info if available
            progress_map = {
                'uploaded': 0,
                'parsing': 10,
                'analyzing': 50,
                'completed': 100,
                'error': 0
            }
            progress = progress_map.get(current_status, 0)
            progress_msg = f"Статус: {current_status}"

            # Read granular progress from contract meta_info
            try:
                meta = contract.meta_info
                if meta and isinstance(meta, dict):
                    granular = meta.get("_progress")
                    if granular is not None and isinstance(granular, (int, float)):
                        progress = int(granular)
                    msg = meta.get("_progress_msg")
                    if msg:
                        progress_msg = msg
            except Exception:
                pass

            # Send status update
            update_message = {
                "type": "progress",
                "contract_id": contract_id,
                "status": current_status,
                "progress": progress,
                "message": progress_msg,
                "data": {
                    "risks_count": risks_count,
                    "recommendations_count": recs_count,
                }
            }

            sent_ok = await manager.send_personal_message(update_message, websocket)
            if not sent_ok:
                break  # Client disconnected — stop polling loop

            # If analysis is complete or failed, send final message
            if current_status in ['completed', 'error', 'uploaded']:
                if current_status != 'uploaded':
                    final_message = {
                        "type": "analysis_complete" if current_status == 'completed' else "error",
                        "contract_id": contract_id,
                        "status": current_status,
                        "progress": 100 if current_status == 'completed' else 0,
                        "message": "Анализ завершён" if current_status == 'completed' else "Ошибка анализа",
                        "data": {
                            "analysis_id": final_analysis_id,
                            "risks_count": final_risks,
                            "recommendations_count": final_recs,
                        } if current_status == 'completed' else {}
                    }
                    await manager.send_personal_message(final_message, websocket)
                break

    except WebSocketDisconnect:
        manager.disconnect(websocket, contract_id)
        logger.info(f"Client disconnected from contract {contract_id} analysis updates")
    except Exception as e:
        logger.error(f"WebSocket error for contract {contract_id}: {e}", exc_info=True)
        manager.disconnect(websocket, contract_id)


@router.websocket("/notifications")
async def websocket_notifications(
    websocket: WebSocket,
    db: Session = Depends(get_db)
):
    """
    WebSocket endpoint for user notifications.

    **Auth:** Send token as first message: {"type": "auth", "token": "ACCESS_TOKEN"}

    **Notification types:** analysis_complete, contract_uploaded, export_ready,
    subscription_expiring, limit_reached

    **Performance:** DB session closed after auth; short-lived sessions for polling.
    """
    # Accept connection first, then authenticate via first message
    await websocket.accept()

    ws_token = None
    try:
        raw = await asyncio.wait_for(websocket.receive_text(), timeout=10.0)
        msg = json.loads(raw)
        if msg.get("type") == "auth" and msg.get("token"):
            ws_token = msg["token"]
    except (asyncio.TimeoutError, json.JSONDecodeError, Exception):
        pass

    if not ws_token:
        await websocket.send_json({"type": "error", "message": "Authentication failed"})
        await websocket.close(code=1008, reason="Invalid token")
        return

    auth_info = _authenticate_ws(db, ws_token)
    if not auth_info:
        await websocket.send_json({"type": "error", "message": "Authentication failed"})
        await websocket.close(code=1008, reason="Session revoked")
        return

    user_id = auth_info["user_id"]

    # Close the injected DB session
    db.close()

    logger.info(f"User {user_id} connected to notifications")

    try:
        # Send welcome notification
        await websocket.send_json({
            "type": "connected",
            "message": "Connected to notification service",
            "user_id": user_id
        })

        # Keep connection alive — poll less frequently for notifications
        while True:
            await asyncio.sleep(15)

            # Short-lived DB session for each poll
            poll_db = SessionLocal()
            try:
                user = poll_db.query(User).filter(User.id == user_id).first()
                if not user:
                    break

                notifications = []

                # Check demo expiration
                if user.is_demo and user.demo_expires:
                    from datetime import datetime, timedelta, timezone
                    time_left = user.demo_expires - datetime.now(timezone.utc)
                    if timedelta(0) < time_left < timedelta(hours=1):
                        notifications.append({
                            "type": "demo_expiring",
                            "title": "Демо-доступ истекает",
                            "message": f"Ваш демо-доступ истекает через {int(time_left.total_seconds() / 60)} минут",
                            "severity": "warning"
                        })

                # Check daily limits
                if user.contracts_today >= user.max_contracts_per_day:
                    notifications.append({
                        "type": "limit_reached",
                        "title": "Лимит достигнут",
                        "message": "Вы достигли дневного лимита контрактов",
                        "severity": "warning"
                    })
            finally:
                poll_db.close()

            # Send collected notifications outside DB session
            for notif in notifications:
                await websocket.send_json(notif)

    except WebSocketDisconnect:
        logger.info(f"User {user_id} disconnected from notifications")
    except Exception as e:
        logger.error(f"WebSocket error for user {user_id}: {e}", exc_info=True)


# Helper function to broadcast updates (can be called from agents)
async def broadcast_analysis_update(contract_id: str, message: dict):
    """
    Broadcast analysis update to all connected clients for this contract

    Usage from agents:
    ```python
    from src.api.websocket.routes import broadcast_analysis_update
    await broadcast_analysis_update(contract_id, {
        "type": "progress",
        "progress": 30,
        "message": "Analyzing clause 3/10..."
    })
    ```
    """
    await manager.broadcast_to_contract(message, contract_id)
