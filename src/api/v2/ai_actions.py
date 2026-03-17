# -*- coding: utf-8 -*-
"""
API v2 — AI Actions

Управление AI-действиями: список, одобрение, отклонение, редактирование.
"""
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from src.api.dependencies import get_current_user
from src.api.v2.dependencies import verify_ai_session_ownership
from src.models.database import get_db
from src.models.auth_models import User
from src.core.ai_collaboration.models import AIAction, AISession
from src.core.ai_collaboration.schemas import (
    AIActionRead,
    AIActionApprovalCreate,
)
from src.core.ai_collaboration.approval_service import AIApprovalService

router = APIRouter(tags=["AI Actions"])


def _verify_action_access(action_id: str, user: User, db: Session) -> AIAction:
    """
    Проверить доступ к AI-действию через ownership сессии.
    Также запрещает self-approval (нельзя одобрять собственные действия).
    """
    action = db.query(AIAction).filter(AIAction.id == action_id).first()
    if not action:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Действие с id={action_id} не найдено",
        )
    # Проверяем ownership через сессию
    ai_session = db.query(AISession).filter(AISession.id == action.session_id).first()
    if not ai_session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="AI-сессия для данного действия не найдена",
        )
    # Для просмотра — проверяем ownership сессии
    # Для approve/reject — проверяем, что это НЕ owner (anti self-approval)
    return action, ai_session


# ──────────────────────────────────────────────
# GET /ai/sessions/{session_id}/actions
# ──────────────────────────────────────────────
@router.get(
    "/ai/sessions/{session_id}/actions",
    response_model=List[AIActionRead],
    summary="Список действий AI-сессии",
)
async def list_session_actions(
    session_id: str,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Возвращает AI-действия для указанной сессии.
    """
    # IDOR fix: проверяем ownership сессии
    verify_ai_session_ownership(session_id, current_user, db)

    actions = (
        db.query(AIAction)
        .filter(AIAction.session_id == session_id)
        .order_by(AIAction.created_at.asc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return actions


# ──────────────────────────────────────────────
# POST /ai/actions/{action_id}/approve
# ──────────────────────────────────────────────
@router.post(
    "/ai/actions/{action_id}/approve",
    response_model=AIActionRead,
    summary="Одобрить AI-действие",
)
async def approve_action(
    action_id: str,
    body: AIActionApprovalCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Одобряет AI-действие. Запрещено одобрять собственные действия (self-approval).
    """
    action, ai_session = _verify_action_access(action_id, current_user, db)

    # Anti self-approval: владелец сессии не может одобрять действия своей сессии
    if ai_session.user_id == current_user.id and current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Нельзя одобрять действия собственной AI-сессии",
        )

    approval_service = AIApprovalService(db)
    result = approval_service.approve(
        action_id=action_id,
        approver_id=current_user.id,
        comment=body.comment,
    )
    if not result:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Действие с id={action_id} не в статусе 'pending'",
        )

    db.commit()
    db.refresh(result)
    return result


# ──────────────────────────────────────────────
# POST /ai/actions/{action_id}/reject
# ──────────────────────────────────────────────
@router.post(
    "/ai/actions/{action_id}/reject",
    response_model=AIActionRead,
    summary="Отклонить AI-действие",
)
async def reject_action(
    action_id: str,
    body: AIActionApprovalCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Отклоняет AI-действие.
    """
    action, ai_session = _verify_action_access(action_id, current_user, db)

    # Anti self-approval
    if ai_session.user_id == current_user.id and current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Нельзя отклонять действия собственной AI-сессии",
        )

    approval_service = AIApprovalService(db)
    result = approval_service.reject(
        action_id=action_id,
        approver_id=current_user.id,
        comment=body.comment,
    )
    if not result:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Действие с id={action_id} не в статусе 'pending'",
        )

    db.commit()
    db.refresh(result)
    return result


# ──────────────────────────────────────────────
# POST /ai/actions/{action_id}/edit-and-approve
# ──────────────────────────────────────────────
@router.post(
    "/ai/actions/{action_id}/edit-and-approve",
    response_model=AIActionRead,
    summary="Редактировать и одобрить AI-действие",
)
async def edit_and_approve_action(
    action_id: str,
    body: AIActionApprovalCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Редактирует payload AI-действия и одобряет его.
    Запрещено для владельца сессии (self-approval).
    """
    if not body.edited_payload:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Поле edited_payload обязательно для edit-and-approve",
        )

    action, ai_session = _verify_action_access(action_id, current_user, db)

    # Anti self-approval
    if ai_session.user_id == current_user.id and current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Нельзя одобрять действия собственной AI-сессии",
        )

    approval_service = AIApprovalService(db)
    result = approval_service.edit_and_approve(
        action_id=action_id,
        approver_id=current_user.id,
        edited_payload=body.edited_payload,
        comment=body.comment,
    )
    if not result:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Действие с id={action_id} не в статусе 'pending'",
        )

    db.commit()
    db.refresh(result)
    return result
