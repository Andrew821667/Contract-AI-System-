# -*- coding: utf-8 -*-
"""
API v2 — Version Intelligence

Сравнение версий документов: анализ изменений, рекомендации, история.
"""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from loguru import logger
from sqlalchemy.orm import Session

from src.api.dependencies import get_current_user
from src.models.database import get_db
from src.models.auth_models import User
from src.models.changes_models import ContractVersion
from src.core.negotiation.schemas import (
    VersionCompareRequest,
    VersionCompareResponse,
    MaterialChangeResponse,
)
from src.core.negotiation.version_service import VersionIntelligenceService

router = APIRouter(prefix="/versions", tags=["Version Intelligence"])


# ──────────────────────────────────────────────
# POST /versions/compare
# ──────────────────────────────────────────────
@router.post(
    "/compare",
    response_model=VersionCompareResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Сравнить две версии документа",
)
async def compare_versions(
    body: VersionCompareRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Запускает интеллектуальное сравнение двух версий документа.
    При deep_analysis=True выполняет семантический анализ изменений.
    """
    from src.models.database import Contract

    contract = db.query(Contract).filter(Contract.id == body.document_id).first()
    if not contract:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Документ с id={body.document_id} не найден",
        )

    # Lightweight instantiation — tool_invoker/audit/policy будут из bootstrap
    # когда lifespan подключит CoreServices. Пока создаём минимально.
    svc = VersionIntelligenceService(
        db=db,
        tool_invoker=None,  # type: ignore[arg-type]
        audit_logger=None,  # type: ignore[arg-type]
    )

    try:
        result = await svc.compare_versions(body, user_id=current_user.id)
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))

    return result


# ──────────────────────────────────────────────
# GET /versions/compare/{comparison_id}/material-changes
# ──────────────────────────────────────────────
@router.get(
    "/compare/{comparison_id}/material-changes",
    response_model=list[MaterialChangeResponse],
    summary="Существенные изменения между версиями",
)
async def get_material_changes(
    comparison_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Возвращает список существенных изменений для указанного сравнения.
    """
    svc = VersionIntelligenceService(
        db=db,
        tool_invoker=None,  # type: ignore[arg-type]
        audit_logger=None,  # type: ignore[arg-type]
    )

    try:
        return await svc.detect_material_changes(comparison_id, user_id=current_user.id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


# ──────────────────────────────────────────────
# GET /versions/compare/{comparison_id}/recommendations
# ──────────────────────────────────────────────
@router.get(
    "/compare/{comparison_id}/recommendations",
    summary="Рекомендации по изменениям между версиями",
)
async def get_recommendations(
    comparison_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """
    Возвращает рекомендации: принять / отклонить / обсудить каждое изменение.
    """
    svc = VersionIntelligenceService(
        db=db,
        tool_invoker=None,  # type: ignore[arg-type]
        audit_logger=None,  # type: ignore[arg-type]
    )

    try:
        return await svc.get_change_recommendations(comparison_id, user_id=current_user.id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


# ──────────────────────────────────────────────
# GET /versions/{document_id}/history
# ──────────────────────────────────────────────
@router.get(
    "/{document_id}/history",
    summary="История версий документа",
)
async def get_version_history(
    document_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    """
    Возвращает историю версий документа (из существующей таблицы contract_versions).
    """
    from src.models.database import Contract

    contract = db.query(Contract).filter(Contract.id == document_id).first()
    if not contract:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Документ с id={document_id} не найден",
        )

    versions = (
        db.query(ContractVersion)
        .filter(ContractVersion.contract_id == document_id)
        .order_by(ContractVersion.version_number.desc())
        .all()
    )

    return [
        {
            "id": v.id,
            "version_number": v.version_number,
            "source": v.source,
            "file_hash": v.file_hash,
            "is_current": v.is_current,
            "description": v.description,
            "uploaded_at": v.uploaded_at.isoformat() if v.uploaded_at else None,
        }
        for v in versions
    ]
