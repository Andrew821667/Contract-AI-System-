# -*- coding: utf-8 -*-
"""
API v2 — Template Governance

Управление версиями шаблонов и политиками клауз.
"""
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from src.api.dependencies import get_current_user
from src.models.database import get_db
from src.models.auth_models import User
from src.core.templates.models import TemplateVersion, ClausePolicy
from src.core.templates.schemas import (
    TemplateVersionRead,
    TemplateVersionCreate,
    ClausePolicyRead,
    ClausePolicyCreate,
)
from src.core.templates.governance_service import TemplateGovernanceService
from src.core.templates.clause_policy_service import ClausePolicyService

router = APIRouter(tags=["Template Governance"])


# ────────────────────────────────────────────────
# Template Versions
# ────────────────────────────────────────────────

@router.get("/templates/{template_id}/versions", response_model=List[TemplateVersionRead])
async def list_template_versions(
    template_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Список всех версий шаблона."""
    versions = (
        db.query(TemplateVersion)
        .filter(TemplateVersion.template_id == template_id)
        .order_by(TemplateVersion.version.desc())
        .all()
    )
    return [TemplateVersionRead.model_validate(v) for v in versions]


@router.post("/templates/{template_id}/versions", response_model=TemplateVersionRead, status_code=status.HTTP_201_CREATED)
async def create_template_version(
    template_id: str,
    body: TemplateVersionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Создать новую версию шаблона (статус: draft)."""
    svc = TemplateGovernanceService(db)
    version = svc.create_version(
        template_id=template_id,
        content=body.content,
        variables=body.variables,
        validation_rules=body.validation_rules,
        created_by=current_user.id,
    )
    db.commit()
    db.refresh(version)
    return TemplateVersionRead.model_validate(version)


@router.post("/templates/versions/{version_id}/activate", response_model=TemplateVersionRead)
async def activate_template_version(
    version_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Активировать версию (деактивирует предыдущую активную)."""
    svc = TemplateGovernanceService(db)
    version = svc.activate_version(version_id)
    if not version:
        raise HTTPException(status_code=404, detail="Version not found")
    db.commit()
    db.refresh(version)
    return TemplateVersionRead.model_validate(version)


@router.get("/templates/{template_id}/versions/active", response_model=TemplateVersionRead)
async def get_active_version(
    template_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Получить текущую активную версию шаблона."""
    svc = TemplateGovernanceService(db)
    version = svc.get_active_version(template_id)
    if not version:
        raise HTTPException(status_code=404, detail="No active version found")
    return TemplateVersionRead.model_validate(version)


# ────────────────────────────────────────────────
# Clause Policies
# ────────────────────────────────────────────────

@router.get("/clause-policies", response_model=List[ClausePolicyRead])
async def list_clause_policies(
    org_id: str | None = None,
    status_filter: str | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Список политик клауз (опциональная фильтрация по org_id и статусу)."""
    query = db.query(ClausePolicy)
    if org_id:
        from sqlalchemy import or_
        query = query.filter(or_(
            ClausePolicy.org_id == org_id,
            ClausePolicy.org_id.is_(None),
        ))
    if status_filter:
        query = query.filter(ClausePolicy.status == status_filter)
    policies = query.order_by(ClausePolicy.clause_type).all()
    return [ClausePolicyRead.model_validate(p) for p in policies]


@router.post("/clause-policies", response_model=ClausePolicyRead, status_code=status.HTTP_201_CREATED)
async def create_clause_policy(
    body: ClausePolicyCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Создать политику клаузы."""
    policy = ClausePolicy(
        org_id=body.org_id,
        clause_type=body.clause_type,
        status=body.status,
        alternative_clause_id=body.alternative_clause_id,
        risk_explanation=body.risk_explanation,
    )
    db.add(policy)
    db.commit()
    db.refresh(policy)
    return ClausePolicyRead.model_validate(policy)


@router.get("/clause-policies/check")
async def check_clause_allowed(
    clause_type: str,
    org_id: str | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Проверить, разрешена ли клауза для организации."""
    svc = ClausePolicyService(db)
    allowed = svc.is_clause_allowed(org_id, clause_type)
    policy = svc.get_policy(org_id, clause_type)
    return {
        "clause_type": clause_type,
        "allowed": allowed,
        "policy": ClausePolicyRead.model_validate(policy) if policy else None,
    }


@router.get("/clause-policies/prohibited", response_model=List[ClausePolicyRead])
async def list_prohibited_clauses(
    org_id: str | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Список запрещённых клауз для организации."""
    svc = ClausePolicyService(db)
    prohibited = svc.get_prohibited_clauses(org_id)
    return [ClausePolicyRead.model_validate(p) for p in prohibited]
