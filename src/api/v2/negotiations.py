# -*- coding: utf-8 -*-
"""
API v2 — Negotiations

Управление переговорами: запуск, генерация возражений, выбор, позиция.
"""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from loguru import logger
from sqlalchemy.orm import Session

from src.api.dependencies import get_current_user
from src.models.database import get_db
from src.models.auth_models import User
from src.core.negotiation.models import Negotiation
from src.core.negotiation.schemas import (
    NegotiationStartRequest,
    NegotiationStartResponse,
    ObjectionGenerateRequest,
    ObjectionResponse,
    ObjectionSelectionRequest,
    ObjectionSelectionResponse,
    NegotiationPositionRequest,
    NegotiationPositionResponse,
)
from src.core.negotiation.service import NegotiationService

router = APIRouter(prefix="/negotiations", tags=["Negotiations"])


def _get_negotiation_service(db: Session) -> NegotiationService:
    """Создать NegotiationService с минимальными зависимостями.

    В production зависимости придут из CoreServices bootstrap.
    """
    return NegotiationService(
        db=db,
        tool_invoker=None,  # type: ignore[arg-type]
        audit_logger=None,  # type: ignore[arg-type]
    )


# ──────────────────────────────────────────────
# POST /negotiations/start
# ──────────────────────────────────────────────
@router.post(
    "/start",
    response_model=NegotiationStartResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Запустить процесс переговоров",
)
async def start_negotiation(
    body: NegotiationStartRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Создаёт новый процесс переговоров по документу.
    Привязывает к текущему пользователю и указанному документу.
    """
    # Проверяем существование документа
    from src.models.database import Contract

    contract = db.query(Contract).filter(Contract.id == body.document_id).first()
    if not contract:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Документ с id={body.document_id} не найден",
        )

    svc = _get_negotiation_service(db)

    try:
        result = await svc.start_negotiation(body, user_id=current_user.id)
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))

    return result


# ──────────────────────────────────────────────
# POST /negotiations/objections/generate
# ──────────────────────────────────────────────
@router.post(
    "/objections/generate",
    response_model=list[ObjectionResponse],
    summary="Сгенерировать возражения",
)
async def generate_objections(
    body: ObjectionGenerateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Генерирует AI-возражения для указанного процесса переговоров.
    Использует анализ рисков и LLM для формулировки возражений.
    """
    negotiation = (
        db.query(Negotiation)
        .filter(Negotiation.id == body.negotiation_id)
        .first()
    )
    if not negotiation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Переговоры с id={body.negotiation_id} не найдены",
        )

    svc = _get_negotiation_service(db)

    try:
        result = await svc.generate_objections(body, user_id=current_user.id)
    except (PermissionError, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    return result


# ──────────────────────────────────────────────
# POST /negotiations/objections/select
# ──────────────────────────────────────────────
@router.post(
    "/objections/select",
    response_model=ObjectionSelectionResponse,
    summary="Выбрать возражения для протокола",
)
async def select_objections(
    body: ObjectionSelectionRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Выбирает возражения для включения в протокол переговоров.
    Позволяет задать приоритетный порядок возражений.
    """
    negotiation = (
        db.query(Negotiation)
        .filter(Negotiation.id == body.negotiation_id)
        .first()
    )
    if not negotiation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Переговоры с id={body.negotiation_id} не найдены",
        )

    svc = _get_negotiation_service(db)
    result = await svc.select_objections(body, user_id=current_user.id)
    return result


# ──────────────────────────────────────────────
# POST /negotiations/position
# ──────────────────────────────────────────────
@router.post(
    "/position",
    response_model=NegotiationPositionResponse,
    summary="Подготовить переговорную позицию",
)
async def prepare_position(
    body: NegotiationPositionRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Подготавливает переговорную позицию на основе выбранных возражений,
    стратегии и фокус-областей. Использует LLM для генерации.
    """
    negotiation = (
        db.query(Negotiation)
        .filter(Negotiation.id == body.negotiation_id)
        .first()
    )
    if not negotiation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Переговоры с id={body.negotiation_id} не найдены",
        )

    svc = _get_negotiation_service(db)

    try:
        result = await svc.prepare_position(body, user_id=current_user.id)
    except (PermissionError, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    return result


# ──────────────────────────────────────────────
# GET /negotiations/{negotiation_id}
# ──────────────────────────────────────────────
@router.get(
    "/{negotiation_id}",
    summary="Получить детали переговоров",
)
async def get_negotiation(
    negotiation_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """
    Возвращает полную информацию о процессе переговоров,
    включая статус, количество возражений и приоритеты.
    """
    negotiation = (
        db.query(Negotiation)
        .filter(Negotiation.id == negotiation_id)
        .first()
    )
    if not negotiation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Переговоры с id={negotiation_id} не найдены",
        )

    return {
        "id": negotiation.id,
        "document_id": negotiation.document_id,
        "user_id": negotiation.user_id,
        "analysis_id": negotiation.analysis_id,
        "goal": negotiation.goal,
        "status": negotiation.status,
        "objections_count": negotiation.objections_count,
        "by_priority": negotiation.by_priority or {},
        "created_at": negotiation.created_at.isoformat() if negotiation.created_at else None,
        "updated_at": negotiation.updated_at.isoformat() if negotiation.updated_at else None,
    }
