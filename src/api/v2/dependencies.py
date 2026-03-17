# -*- coding: utf-8 -*-
"""
API v2 Dependencies — организационный контекст, проверки доступа, CoreServices.

Предоставляет:
- OrganizationContext — dataclass с полным контекстом пользователя/организации
- get_org_context — dependency: возвращает OrganizationContext или None
- require_org_context — dependency: требует OrganizationContext, иначе 400
- require_org_admin — dependency: требует owner/admin роль в организации, иначе 403
- get_core_services — dependency: CoreServices из app.state
- Ownership helpers: verify_document_access, verify_session_ownership, etc.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from fastapi import Depends, Header, HTTPException, Request, status
from sqlalchemy.orm import Session

from src.api.dependencies import get_current_user
from src.core.identity_org.models import (
    Organization,
    OrganizationMembership,
    TenantContext,
    UserAgentPolicyProfile,
)
from src.core.identity_org.service import OrganizationContextService
from src.models.auth_models import User
from src.models.database import get_db


# ── Dataclass ────────────────────────────────────────────────────────────────

@dataclass
class OrganizationContext:
    """Полный контекст пользователя в рамках организации."""

    org: Organization
    membership: OrganizationMembership
    tenant_context: Optional[TenantContext]
    agent_policy_profile: Optional[UserAgentPolicyProfile]


# ── Dependencies ─────────────────────────────────────────────────────────────

async def get_org_context(
    x_organization_id: Optional[str] = Header(None, alias="X-Organization-Id"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Optional[OrganizationContext]:
    """
    Получить контекст пользователя с привязкой к организации.

    - Если X-Organization-Id передан — загрузить Organization, membership,
      TenantContext, UserAgentPolicyProfile и вернуть OrganizationContext.
    - Если не передан — вернуть None.
      (Endpoints, которым обязателен org context, должны использовать require_org_context.)
    - Если организация не найдена — 404.
    - Если пользователь не член организации — 403.
    """
    if not x_organization_id:
        return None

    svc = OrganizationContextService(db)

    # Загрузить организацию
    org = svc.get_organization(x_organization_id)
    if not org:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Организация не найдена",
        )

    # Проверить membership
    membership = svc.get_membership(current_user.id, x_organization_id)
    if not membership:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Пользователь не является членом указанной организации",
        )

    # Tenant context (может отсутствовать)
    tenant_context = svc.get_tenant_context(x_organization_id)

    # Agent policy profile (может отсутствовать)
    agent_policy_profile = svc.get_agent_policy_profile(
        current_user.id, x_organization_id
    )

    return OrganizationContext(
        org=org,
        membership=membership,
        tenant_context=tenant_context,
        agent_policy_profile=agent_policy_profile,
    )


async def require_org_context(
    ctx: Optional[OrganizationContext] = Depends(get_org_context),
) -> OrganizationContext:
    """
    Требует наличия организационного контекста.

    Если X-Organization-Id не передан (ctx is None) — 400.
    """
    if ctx is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Заголовок X-Organization-Id обязателен для этого endpoint",
        )
    return ctx


async def require_org_admin(
    ctx: OrganizationContext = Depends(require_org_context),
) -> OrganizationContext:
    """
    Требует роль owner или admin в организации.

    Если membership.role не owner и не admin — 403.
    """
    if ctx.membership.functional_role not in ("owner", "org_admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Требуется роль owner или admin в организации",
        )
    return ctx


# ── CoreServices dependency ─────────────────────────────────────────────────

def get_core_services(request: Request):
    """Получить CoreServices из app.state (bootstrapped в lifespan)."""
    core = getattr(request.app.state, "core_services", None)
    if core is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Core services не инициализированы",
        )
    return core


# ── Ownership verification helpers ──────────────────────────────────────────

def verify_document_access(
    document_id: str,
    user: User,
    db: Session,
) -> None:
    """
    Проверить, что пользователь имеет доступ к документу.

    Проверяет: assigned_to == user.id ИЛИ user.role == admin.
    """
    from src.models.database import Contract

    contract = db.query(Contract).filter(Contract.id == document_id).first()
    if not contract:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Документ с id={document_id} не найден",
        )
    # Admin видит всё; assigned_to — владелец документа
    if user.role != "admin" and contract.assigned_to != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Нет доступа к данному документу",
        )
    return contract


def verify_ai_session_ownership(
    session_id: str,
    user: User,
    db: Session,
):
    """Проверить, что AI-сессия принадлежит текущему пользователю."""
    from src.core.ai_collaboration.models import AISession

    ai_session = db.query(AISession).filter(AISession.id == session_id).first()
    if not ai_session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"AI-сессия с id={session_id} не найдена",
        )
    if user.role != "admin" and ai_session.user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Нет доступа к данной AI-сессии",
        )
    return ai_session


def verify_orchestrator_run_ownership(
    run_id: str,
    user: User,
    db: Session,
):
    """Проверить, что OrchestratorRun принадлежит текущему пользователю."""
    from src.core.orchestrator.models import OrchestratorRun

    run = db.query(OrchestratorRun).filter(OrchestratorRun.id == run_id).first()
    if not run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Оркестрация с id={run_id} не найдена",
        )
    if user.role != "admin" and run.initiated_by != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Нет доступа к данной оркестрации",
        )
    return run


def verify_negotiation_ownership(
    negotiation_id: str,
    user: User,
    db: Session,
):
    """Проверить, что Negotiation принадлежит текущему пользователю."""
    from src.core.negotiation.models import Negotiation

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
    if user.role != "admin" and negotiation.user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Нет доступа к данным переговорам",
        )
    return negotiation


def verify_workflow_task_ownership(
    task_id: str,
    user: User,
    db: Session,
):
    """Проверить, что WorkflowTask назначена текущему пользователю."""
    from src.core.workflow.models import WorkflowTask

    task = db.query(WorkflowTask).filter(WorkflowTask.id == task_id).first()
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Задача с id={task_id} не найдена",
        )
    if user.role != "admin" and task.assignee_id != str(user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Задача назначена другому пользователю",
        )
    return task


def verify_org_membership(
    org_id: str,
    user: User,
    db: Session,
) -> OrganizationMembership:
    """Проверить, что пользователь — участник организации."""
    if user.role == "admin":
        # Platform admin видит всё
        org = db.query(Organization).filter(Organization.id == org_id).first()
        if not org:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Организация с id={org_id} не найдена",
            )
        # Return a synthetic membership for admin
        return None  # type: ignore[return-value]

    membership = (
        db.query(OrganizationMembership)
        .filter(
            OrganizationMembership.org_id == org_id,
            OrganizationMembership.user_id == user.id,
            OrganizationMembership.active.is_(True),
        )
        .first()
    )
    if not membership:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Нет доступа к данной организации",
        )
    return membership
