# -*- coding: utf-8 -*-
"""
API v2 — AI Sessions

CRUD для AI-сессий: создание, список, отправка сообщений, история.
"""
from datetime import datetime
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from src.api.dependencies import get_current_user
from src.models.database import get_db, generate_uuid
from src.models.auth_models import User
from src.core.ai_collaboration.models import (
    AISession,
    AIConversationTurn,
)
from src.core.ai_collaboration.schemas import (
    AISessionCreate,
    AISessionRead,
    AIMessageCreate,
    AIConversationTurnRead,
)
from src.core.ai_collaboration.context_builder import AIContextBuilderService
from src.core.base import AIContext

router = APIRouter(tags=["AI Sessions"])


# ──────────────────────────────────────────────
# POST /documents/{document_id}/ai/sessions
# ──────────────────────────────────────────────
@router.post(
    "/documents/{document_id}/ai/sessions",
    response_model=AISessionRead,
    status_code=status.HTTP_201_CREATED,
    summary="Создать AI-сессию для документа",
)
async def create_ai_session(
    document_id: str,
    body: AISessionCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Создаёт новую AI-сессию для указанного документа.
    Привязывает сессию к текущему пользователю.
    """
    # Проверяем существование документа
    from src.models.database import Contract

    contract = db.query(Contract).filter(Contract.id == document_id).first()
    if not contract:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Документ с id={document_id} не найден",
        )

    session = AISession(
        id=generate_uuid(),
        document_id=document_id,
        user_id=current_user.id,
        stage=body.stage,
        status="active",
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


# ──────────────────────────────────────────────
# GET /documents/{document_id}/ai/sessions
# ──────────────────────────────────────────────
@router.get(
    "/documents/{document_id}/ai/sessions",
    response_model=List[AISessionRead],
    summary="Список AI-сессий документа",
)
async def list_ai_sessions(
    document_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Возвращает все AI-сессии для указанного документа,
    отсортированные по дате создания (новые первыми).
    """
    sessions = (
        db.query(AISession)
        .filter(AISession.document_id == document_id)
        .order_by(AISession.created_at.desc())
        .all()
    )
    return sessions


# ──────────────────────────────────────────────
# POST /ai/sessions/{session_id}/messages
# ──────────────────────────────────────────────
@router.post(
    "/ai/sessions/{session_id}/messages",
    response_model=AIConversationTurnRead,
    status_code=status.HTTP_201_CREATED,
    summary="Отправить сообщение в AI-сессию",
)
async def send_message(
    session_id: str,
    body: AIMessageCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Добавляет сообщение пользователя в AI-сессию.
    В будущем здесь будет вызов LLM и генерация ответа ассистента.
    Сейчас — только сохранение user-сообщения.
    """
    ai_session = db.query(AISession).filter(AISession.id == session_id).first()
    if not ai_session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"AI-сессия с id={session_id} не найдена",
        )

    if ai_session.status == "closed":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="AI-сессия закрыта, отправка сообщений невозможна",
        )

    turn = AIConversationTurn(
        id=generate_uuid(),
        session_id=session_id,
        role="user",
        content=body.content,
    )
    db.add(turn)

    # Обновляем счётчик сообщений
    ai_session.total_turns = (ai_session.total_turns or 0) + 1
    ai_session.updated_at = datetime.utcnow()

    db.commit()
    db.refresh(turn)
    return turn


# ──────────────────────────────────────────────
# GET /ai/sessions/{session_id}/messages
# ──────────────────────────────────────────────
@router.get(
    "/ai/sessions/{session_id}/messages",
    response_model=List[AIConversationTurnRead],
    summary="История сообщений AI-сессии",
)
async def list_messages(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Возвращает все сообщения (user + assistant + system) для указанной сессии,
    отсортированные по дате создания (хронологический порядок).
    """
    ai_session = db.query(AISession).filter(AISession.id == session_id).first()
    if not ai_session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"AI-сессия с id={session_id} не найдена",
        )

    turns = (
        db.query(AIConversationTurn)
        .filter(AIConversationTurn.session_id == session_id)
        .order_by(AIConversationTurn.created_at.asc())
        .all()
    )
    return turns


# ──────────────────────────────────────────────
# GET /ai/sessions/{session_id}/context
# ──────────────────────────────────────────────
@router.get(
    "/ai/sessions/{session_id}/context",
    response_model=AIContext,
    summary="Получить текущий контекст AI-сессии",
)
async def get_session_context(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Собирает и возвращает полный контекст AI-сессии:
    документ, findings, комментарии, workflow state, предыдущие действия.
    """
    ai_session = db.query(AISession).filter(AISession.id == session_id).first()
    if not ai_session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"AI-сессия с id={session_id} не найдена",
        )

    builder = AIContextBuilderService(db)
    context = await builder.build(
        document_id=ai_session.document_id,
        user_id=current_user.id,
        stage=ai_session.stage,
    )
    return context
