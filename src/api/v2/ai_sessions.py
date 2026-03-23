# -*- coding: utf-8 -*-
"""
API v2 — AI Sessions

CRUD для AI-сессий: создание, список, отправка сообщений, история.
"""
import asyncio
import logging
from datetime import datetime, timezone
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from src.api.dependencies import get_current_user
from src.api.v2.dependencies import (
    verify_ai_session_ownership,
    verify_document_access,
)
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

logger = logging.getLogger(__name__)

router = APIRouter(tags=["AI Sessions"])


# ──────────────────────────────────────────────
# POST /ai/sessions  (general — without document)
# ──────────────────────────────────────────────
@router.post(
    "/ai/sessions",
    response_model=AISessionRead,
    status_code=status.HTTP_201_CREATED,
    summary="Создать AI-сессию (общую или для документа)",
)
async def create_ai_session_general(
    body: AISessionCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Создаёт AI-сессию. Если document_id указан — привязывает к документу.
    Иначе создаёт общую сессию (агент-помощник).
    """
    document_id = body.document_id

    if document_id:
        verify_document_access(document_id, current_user, db)

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
    # IDOR fix: проверяем доступ к документу
    verify_document_access(document_id, current_user, db)

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
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Возвращает AI-сессии текущего пользователя для указанного документа.
    """
    # IDOR fix: проверяем доступ к документу
    verify_document_access(document_id, current_user, db)

    # Пользователь видит только свои сессии (admin видит все)
    query = db.query(AISession).filter(AISession.document_id == document_id)
    if current_user.role != "admin":
        query = query.filter(AISession.user_id == current_user.id)

    sessions = query.order_by(AISession.created_at.desc()).offset(offset).limit(limit).all()
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
    Добавляет сообщение пользователя в AI-сессию и генерирует ответ AI.
    """
    # IDOR fix: проверяем ownership AI-сессии
    ai_session = verify_ai_session_ownership(session_id, current_user, db)

    if ai_session.status == "closed":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="AI-сессия закрыта, отправка сообщений невозможна",
        )

    # 1. Сохраняем сообщение пользователя
    user_turn = AIConversationTurn(
        id=generate_uuid(),
        session_id=session_id,
        role="user",
        content=body.content,
    )
    db.add(user_turn)
    db.flush()

    # 2. Генерируем ответ AI в фоне
    try:
        assistant_content = await _generate_ai_response(
            session_id=session_id,
            ai_session=ai_session,
            user_id=current_user.id,
            db=db,
        )

        # 3. Сохраняем ответ AI
        assistant_turn = AIConversationTurn(
            id=generate_uuid(),
            session_id=session_id,
            role="assistant",
            content=assistant_content,
        )
        db.add(assistant_turn)

        ai_session.total_turns = (ai_session.total_turns or 0) + 2
    except Exception as e:
        logger.error(f"AI response generation failed: {e}")
        # Сохраняем ошибку как ответ, чтобы фронтенд не висел вечно
        error_turn = AIConversationTurn(
            id=generate_uuid(),
            session_id=session_id,
            role="assistant",
            content=f"Извините, произошла ошибка при генерации ответа. Попробуйте ещё раз.\n\nДетали: {str(e)[:200]}",
        )
        db.add(error_turn)
        ai_session.total_turns = (ai_session.total_turns or 0) + 2

    ai_session.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(user_turn)
    return user_turn


async def _generate_ai_response(
    session_id: str,
    ai_session: AISession,
    user_id: str,
    db: Session,
) -> str:
    """Генерирует ответ AI через LLMGateway."""
    from src.services.llm_gateway import LLMGateway

    # Собираем историю диалога
    history = (
        db.query(AIConversationTurn)
        .filter(AIConversationTurn.session_id == session_id)
        .order_by(AIConversationTurn.created_at)
        .all()
    )

    # Собираем контекст документа
    context_parts = []
    if ai_session.document_id:
        try:
            from src.models.database import Contract
            contract = db.query(Contract).filter(Contract.id == ai_session.document_id).first()
            if contract:
                context_parts.append(f"Документ: {contract.file_name}")
                if contract.contract_type and contract.contract_type != "unknown":
                    context_parts.append(f"Тип: {contract.contract_type}")
                if contract.meta_info:
                    import json
                    meta = contract.meta_info if isinstance(contract.meta_info, dict) else json.loads(contract.meta_info)
                    if meta.get("parties"):
                        context_parts.append(f"Стороны: {meta['parties']}")
                    # Добавляем текст документа для контекста (первые 3000 символов)
                    text = meta.get("full_text", meta.get("text", ""))
                    if text:
                        context_parts.append(f"\nТекст документа (фрагмент):\n{text[:3000]}")
        except Exception as e:
            logger.warning(f"Failed to load document context: {e}")

    # Системный промпт
    system_prompt = (
        "Ты — AI-ассистент юридической системы Contract AI System. "
        "Ты помогаешь юристам анализировать договоры, выявлять риски, "
        "предлагать формулировки и отвечать на вопросы о работе системы.\n\n"
        "Правила:\n"
        "- Отвечай на русском языке\n"
        "- Будь конкретным и полезным\n"
        "- Ссылайся на конкретные пункты документа, если они есть в контексте\n"
        "- Если не знаешь ответ, честно скажи об этом\n"
    )
    if context_parts:
        system_prompt += "\n# Контекст\n" + "\n".join(context_parts)

    # Формируем промпт из истории
    messages_text = []
    for turn in history:
        prefix = "Пользователь" if turn.role == "user" else "Ассистент"
        messages_text.append(f"{prefix}: {turn.content}")

    prompt = "\n\n".join(messages_text)

    # Вызываем LLM
    gateway = LLMGateway(provider="deepseek", model="deepseek-chat")
    response = await gateway.acall(
        prompt=prompt,
        system_prompt=system_prompt,
        temperature=0.3,
        max_tokens=2048,
    )

    return response if isinstance(response, str) else str(response)


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
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Возвращает сообщения для указанной сессии.
    """
    # IDOR fix: проверяем ownership
    verify_ai_session_ownership(session_id, current_user, db)

    turns = (
        db.query(AIConversationTurn)
        .filter(AIConversationTurn.session_id == session_id)
        .order_by(AIConversationTurn.created_at.asc())
        .offset(offset)
        .limit(limit)
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
    Собирает и возвращает полный контекст AI-сессии.
    """
    # IDOR fix: проверяем ownership
    ai_session = verify_ai_session_ownership(session_id, current_user, db)

    builder = AIContextBuilderService(db)
    context = await builder.build(
        document_id=ai_session.document_id,
        user_id=current_user.id,
        stage=ai_session.stage,
    )
    return context
