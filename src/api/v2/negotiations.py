# -*- coding: utf-8 -*-
"""
API v2 — Negotiations

Управление переговорами: запуск, генерация возражений, выбор, позиция.
"""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from loguru import logger
from sqlalchemy.orm import Session

from src.api.dependencies import get_current_user
from src.api.v2.dependencies import (
    get_core_services,
    verify_document_access,
    verify_negotiation_ownership,
)
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


def _get_negotiation_service(db: Session, request: Request) -> NegotiationService:
    """Создать NegotiationService с реальными зависимостями из CoreServices."""
    core = getattr(request.app.state, "core_services", None)
    if core:
        return NegotiationService(
            db=db,
            tool_invoker=core.tool_invoker,
            audit_logger=core.audit_service,
            policy_resolver=core.policy_resolver,
        )
    # Graceful fallback для dev-среды без bootstrap
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
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Создаёт новый процесс переговоров по документу.
    """
    # IDOR fix: проверяем доступ к документу
    verify_document_access(body.document_id, current_user, db)

    svc = _get_negotiation_service(db, request)

    try:
        result = await svc.start_negotiation(body, user_id=current_user.id)
    except PermissionError:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Нет доступа")

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
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Генерирует AI-возражения для указанного процесса переговоров.
    """
    # IDOR fix: проверяем ownership переговоров
    verify_negotiation_ownership(body.negotiation_id, current_user, db)

    svc = _get_negotiation_service(db, request)

    try:
        result = await svc.generate_objections(body, user_id=current_user.id)
    except PermissionError:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Нет доступа")
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Некорректные параметры запроса")

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
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Выбирает возражения для включения в протокол переговоров.
    """
    # IDOR fix: проверяем ownership
    verify_negotiation_ownership(body.negotiation_id, current_user, db)

    svc = _get_negotiation_service(db, request)
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
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Подготавливает переговорную позицию на основе выбранных возражений.
    """
    # IDOR fix: проверяем ownership
    verify_negotiation_ownership(body.negotiation_id, current_user, db)

    svc = _get_negotiation_service(db, request)

    try:
        result = await svc.prepare_position(body, user_id=current_user.id)
    except PermissionError:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Нет доступа")
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Некорректные параметры запроса")

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
    Возвращает полную информацию о процессе переговоров.
    """
    # IDOR fix: проверяем ownership
    negotiation = verify_negotiation_ownership(negotiation_id, current_user, db)

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
