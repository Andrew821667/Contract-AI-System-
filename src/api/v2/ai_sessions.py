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
    OrganizationContext,
    get_org_context,
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
from src.core.ai_collaboration.session_service import render_document_context
from src.core.base import AIContext

logger = logging.getLogger(__name__)

router = APIRouter(tags=["AI Sessions"])


def _create_session(
    document_id: str | None,
    stage: str,
    user: User,
    db: Session,
    ctx: OrganizationContext | None = None,
) -> AISession:
    """Shared logic: create an AI session, optionally bound to a document."""
    if document_id:
        verify_document_access(document_id, user, db, ctx)
    session = AISession(
        id=generate_uuid(),
        document_id=document_id,
        user_id=user.id,
        organization_id=ctx.org.id if ctx else None,
        stage=stage,
        status="active",
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


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
    ctx: OrganizationContext | None = Depends(get_org_context),
):
    """Создаёт AI-сессию. Если document_id указан — привязывает к документу."""
    return _create_session(body.document_id, body.stage, current_user, db, ctx)


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
    ctx: OrganizationContext | None = Depends(get_org_context),
):
    """Создаёт новую AI-сессию для указанного документа."""
    return _create_session(document_id, body.stage, current_user, db, ctx)


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
    ctx: OrganizationContext | None = Depends(get_org_context),
):
    """
    Возвращает AI-сессии текущего пользователя для указанного документа.
    """
    # IDOR fix: проверяем доступ к документу
    verify_document_access(document_id, current_user, db, ctx)

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
    ctx: OrganizationContext | None = Depends(get_org_context),
):
    """
    Добавляет сообщение пользователя в AI-сессию и генерирует ответ AI.
    """
    # IDOR fix: проверяем ownership AI-сессии
    ai_session = verify_ai_session_ownership(session_id, current_user, db, ctx)

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
    """Генерирует ответ AI через LLMGateway с RAG-обогащением."""
    from src.services.llm_gateway import LLMGateway
    from src.services.admin_rag_retriever import get_legal_context, has_legal_docs
    from src.core.llm_models import DEEPSEEK_FLASH_MODEL

    # Собираем историю диалога
    history = (
        db.query(AIConversationTurn)
        .filter(AIConversationTurn.session_id == session_id)
        .order_by(AIConversationTurn.created_at)
        .all()
    )

    # Последнее сообщение пользователя — основа RAG-запроса
    user_query = ""
    for turn in reversed(history):
        if turn.role == "user":
            user_query = turn.content
            break

    # Контекст документа — тем же сборщиком, что и GET /context: текст
    # договора и результаты анализа. Раньше маршрут искал текст в
    # meta_info.full_text, которого никто не пишет, и помощник честно
    # отвечал «текста договора в контексте нет».
    doc_context, doc_hint = await _build_document_context(db, ai_session, user_id)

    # RAG-обогащение: законы, судебная практика, база знаний системы
    rag_context = ""
    if user_query:
        try:
            rag_query = f"{doc_hint}. {user_query}" if doc_hint else user_query
            rag_context = get_legal_context(
                query=rag_query,
                collections=["laws", "case_law", "knowledge"],
                n_results=3,
                max_chars=2000,
            )
            if rag_context:
                logger.debug(f"RAG context retrieved for session {session_id}: {len(rag_context)} chars")
        except Exception as e:
            logger.warning(f"RAG retrieval failed (non-fatal): {e}")

    system_prompt = _compose_system_prompt(doc_context, rag_context)

    # Формируем промпт из истории
    messages_text = []
    for turn in history:
        prefix = "Пользователь" if turn.role == "user" else "Ассистент"
        messages_text.append(f"{prefix}: {turn.content}")

    prompt = "\n\n".join(messages_text)

    # Вызываем LLM
    gateway = LLMGateway(provider="deepseek", model=DEEPSEEK_FLASH_MODEL)
    response = await gateway.acall(
        prompt=prompt,
        system_prompt=system_prompt,
        temperature=0.3,
        max_tokens=2048,
    )

    return response if isinstance(response, str) else str(response)


async def _build_document_context(db: Session, ai_session: AISession, user_id: str) -> tuple[str, str]:
    """Блок контекста документа для промпта и короткая подсказка для RAG-запроса.

    Без документа (общая сессия) возвращает пустые строки; ошибка сборки не
    роняет ответ — помощник отвечает без контекста, как раньше.
    """
    if not ai_session.document_id:
        return "", ""
    try:
        context = await AIContextBuilderService(db).build(
            document_id=ai_session.document_id,
            user_id=user_id,
            stage=ai_session.stage or "general",
            include_comments=False,
            include_workflow=False,
            include_prior_actions=False,
        )
    except Exception as e:
        logger.warning(f"Failed to load document context: {e}")
        return "", ""
    file_name = (context.document_metadata or {}).get("file_name") or ai_session.document_id
    return render_document_context(context), f"Документ: {file_name}"


AI_PANEL_RULES = (
    "Ты — AI-ассистент юридической системы Contract AI System. "
    "Ты помогаешь юристам анализировать договоры, выявлять риски, "
    "предлагать формулировки и отвечать на вопросы о работе системы.\n\n"
    "Правила:\n"
    "- Отвечай на русском языке\n"
    "- Будь конкретным и полезным\n"
    "- Если в контексте есть текст договора и результаты анализа — отвечай по ним: "
    "цитируй нужные пункты дословно и ссылайся на выявленные риски и рекомендации\n"
    "- Ссылайся на закон/норму из правовой базы; номер статьи или закона указывай ТОЛЬКО если он есть в контексте — "
    "если номера в контексте нет, не придумывай его, опиши норму своими словами\n"
    "- Если не знаешь ответ, честно скажи об этом\n"
)


def _compose_system_prompt(doc_context: str, rag_context: str) -> str:
    """Системный промпт AI-панели: правила, затем документ, затем правовая база."""
    prompt = AI_PANEL_RULES
    if doc_context:
        prompt += "\n\n" + doc_context
    if rag_context:
        prompt += f"\n\n# Правовая база и база знаний\n{rag_context}"
    return prompt


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
    ctx: OrganizationContext | None = Depends(get_org_context),
):
    """
    Возвращает сообщения для указанной сессии.
    """
    # IDOR fix: проверяем ownership
    verify_ai_session_ownership(session_id, current_user, db, ctx)

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
    ctx: OrganizationContext | None = Depends(get_org_context),
):
    """
    Собирает и возвращает полный контекст AI-сессии.
    """
    # IDOR fix: проверяем ownership
    ai_session = verify_ai_session_ownership(session_id, current_user, db, ctx)

    builder = AIContextBuilderService(db)
    context = await builder.build(
        document_id=ai_session.document_id,
        user_id=current_user.id,
        stage=ai_session.stage,
    )
    return context
