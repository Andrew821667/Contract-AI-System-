# -*- coding: utf-8 -*-
"""
API v2 — Version Intelligence

Сравнение версий документов: анализ изменений, рекомендации, история.
"""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from loguru import logger
from sqlalchemy.orm import Session

from src.api.dependencies import get_current_user
from src.api.v2.dependencies import (
    OrganizationContext,
    get_core_services,
    get_org_context,
    verify_document_access,
)
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
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    ctx: OrganizationContext | None = Depends(get_org_context),
):
    """
    Запускает интеллектуальное сравнение двух версий документа.
    """
    # IDOR fix: проверяем доступ к документу
    verify_document_access(body.document_id, current_user, db, ctx)

    # CoreServices injection
    core = getattr(request.app.state, "core_services", None)
    if core:
        svc = VersionIntelligenceService(
            db=db,
            tool_invoker=core.tool_invoker,
            audit_logger=core.audit_service,
        )
    else:
        svc = VersionIntelligenceService(
            db=db,
            tool_invoker=None,  # type: ignore[arg-type]
            audit_logger=None,  # type: ignore[arg-type]
        )

    try:
        result = await svc.compare_versions(body, user_id=current_user.id)
    except PermissionError:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Нет доступа")
    except ValueError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Документ или версия не найдены")

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
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    ctx: OrganizationContext | None = Depends(get_org_context),
):
    """
    Возвращает список существенных изменений для указанного сравнения.
    """
    # IDOR fix: проверяем доступ к документу через кеш сравнения
    from src.core.negotiation.version_service import _comparison_cache
    cached = _comparison_cache.get(comparison_id)
    if cached and cached.get("document_id"):
        verify_document_access(cached["document_id"], current_user, db, ctx)

    core = getattr(request.app.state, "core_services", None)
    if core:
        svc = VersionIntelligenceService(
            db=db, tool_invoker=core.tool_invoker, audit_logger=core.audit_service,
        )
    else:
        svc = VersionIntelligenceService(
            db=db, tool_invoker=None, audit_logger=None,  # type: ignore[arg-type]
        )

    try:
        return await svc.detect_material_changes(comparison_id, user_id=current_user.id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Сравнение не найдено")


# ──────────────────────────────────────────────
# GET /versions/compare/{comparison_id}/recommendations
# ──────────────────────────────────────────────
@router.get(
    "/compare/{comparison_id}/recommendations",
    summary="Рекомендации по изменениям между версиями",
)
async def get_recommendations(
    comparison_id: str,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    ctx: OrganizationContext | None = Depends(get_org_context),
) -> dict[str, Any]:
    """
    Возвращает рекомендации: принять / отклонить / обсудить каждое изменение.
    """
    # IDOR fix: проверяем доступ к документу через кеш сравнения
    from src.core.negotiation.version_service import _comparison_cache
    cached = _comparison_cache.get(comparison_id)
    if cached and cached.get("document_id"):
        verify_document_access(cached["document_id"], current_user, db, ctx)

    core = getattr(request.app.state, "core_services", None)
    if core:
        svc = VersionIntelligenceService(
            db=db, tool_invoker=core.tool_invoker, audit_logger=core.audit_service,
        )
    else:
        svc = VersionIntelligenceService(
            db=db, tool_invoker=None, audit_logger=None,  # type: ignore[arg-type]
        )

    try:
        return await svc.get_change_recommendations(comparison_id, user_id=current_user.id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Сравнение не найдено")


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
    ctx: OrganizationContext | None = Depends(get_org_context),
) -> list[dict[str, Any]]:
    """
    Возвращает историю версий документа.
    """
    # IDOR fix: проверяем доступ к документу
    verify_document_access(document_id, current_user, db, ctx)

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
