# -*- coding: utf-8 -*-
"""
API v2 Dependencies — организационный контекст и проверки доступа.

Предоставляет:
- OrganizationContext — Pydantic-модель с полным контекстом пользователя/организации
- get_org_context — dependency для получения org context из заголовка X-Organization-Id
- require_org_admin — dependency для проверки org_admin / admin роли
"""

from __future__ import annotations

from typing import Any

from fastapi import Depends, Header, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.api.dependencies import get_current_user
from src.core.identity_org.schemas import (
    OrganizationMembershipRead,
    UserAgentPolicyProfileRead,
)
from src.core.identity_org.service import OrganizationContextService
from src.models.auth_models import User
from src.models.database import get_db


# ── Pydantic model ──────────────────────────────────────────────────────────

class OrganizationContext(BaseModel):
    """Полный контекст пользователя в рамках (опционально) организации."""

    user_id: str
    user_role: str  # system role (admin, lawyer, etc.)
    organization_id: str | None = None
    org_membership: OrganizationMembershipRead | None = None
    functional_role: str | None = None  # org role (org_admin, manager, member, viewer)
    tenant_mode: str | None = None  # standalone | branch
    agent_policy: UserAgentPolicyProfileRead | None = None


# ── Dependencies ─────────────────────────────────────────────────────────────

async def get_org_context(
    x_organization_id: str | None = Header(None, alias="X-Organization-Id"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> OrganizationContext:
    """
    Получить контекст пользователя с привязкой к организации.

    - Если X-Organization-Id передан — проверить membership, загрузить tenant context и agent policy.
    - Если не передан — вернуть context только с user info (без org).
    - Если пользователь не член организации — 403.
    """
    ctx = OrganizationContext(
        user_id=current_user.id,
        user_role=current_user.role,
    )

    if not x_organization_id:
        return ctx

    # Загрузить организационный контекст
    svc = OrganizationContextService(db)

    # Проверить membership
    membership = svc.get_membership(current_user.id, x_organization_id)
    if not membership:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Пользователь не является членом указанной организации",
        )

    ctx.organization_id = x_organization_id
    ctx.org_membership = OrganizationMembershipRead.model_validate(membership)
    ctx.functional_role = membership.functional_role

    # Tenant context
    tenant = svc.get_tenant_context(x_organization_id)
    if tenant:
        ctx.tenant_mode = tenant.mode

    # Agent policy profile
    profile = svc.get_agent_policy_profile(current_user.id, x_organization_id)
    if profile:
        ctx.agent_policy = UserAgentPolicyProfileRead.model_validate(profile)

    return ctx


async def require_org_admin(
    ctx: OrganizationContext = Depends(get_org_context),
) -> OrganizationContext:
    """
    Проверить, что пользователь — org_admin в текущей организации или system admin.

    Если ни то, ни другое — 403.
    """
    if ctx.functional_role == "org_admin" or ctx.user_role == "admin":
        return ctx

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Требуется роль администратора организации (org_admin) или системного администратора",
    )
