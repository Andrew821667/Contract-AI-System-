# -*- coding: utf-8 -*-
"""
API v2 — AI Actions

Управление AI-действиями: список, одобрение, отклонение, редактирование.
"""
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from src.api.dependencies import get_current_user
from src.models.database import get_db
from src.models.auth_models import User
from src.core.ai_collaboration.models import AIAction, AISession
from src.core.ai_collaboration.schemas import (
    AIActionRead,
    AIActionApprovalCreate,
)
from src.core.ai_collaboration.approval_service import AIApprovalService

router = APIRouter(tags=["AI Actions"])


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
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Возвращает все AI-действия для указанной сессии,
    отсортированные по дате создания (хронологический порядок).
    """
    ai_session = db.query(AISession).filter(AISession.id == session_id).first()
    if not ai_session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"AI-сессия с id={session_id} не найдена",
        )

    actions = (
        db.query(AIAction)
        .filter(AIAction.session_id == session_id)
        .order_by(AIAction.created_at.asc())
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
    Одобряет AI-действие. После одобрения действие автоматически
    выполняется через AIActionExecutionService.
    """
    approval_service = AIApprovalService(db)
    action = approval_service.approve(
        action_id=action_id,
        approver_id=current_user.id,
        comment=body.comment,
    )
    if not action:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Действие с id={action_id} не найдено или не в статусе 'pending'",
        )

    db.commit()
    db.refresh(action)
    return action


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
    Отклоняет AI-действие. Действие переходит в статус 'rejected'.
    """
    approval_service = AIApprovalService(db)
    action = approval_service.reject(
        action_id=action_id,
        approver_id=current_user.id,
        comment=body.comment,
    )
    if not action:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Действие с id={action_id} не найдено или не в статусе 'pending'",
        )

    db.commit()
    db.refresh(action)
    return action


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
    Требуется передать edited_payload в теле запроса.
    После одобрения действие автоматически выполняется.
    """
    if not body.edited_payload:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Поле edited_payload обязательно для edit-and-approve",
        )

    approval_service = AIApprovalService(db)
    action = approval_service.edit_and_approve(
        action_id=action_id,
        approver_id=current_user.id,
        edited_payload=body.edited_payload,
        comment=body.comment,
    )
    if not action:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Действие с id={action_id} не найдено или не в статусе 'pending'",
        )

    db.commit()
    db.refresh(action)
    return action
