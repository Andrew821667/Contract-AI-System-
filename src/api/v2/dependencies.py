# -*- coding: utf-8 -*-
"""
API v2 Dependencies — организационный контекст и проверки доступа.

Предоставляет:
- OrganizationContext — dataclass с полным контекстом пользователя/организации
- get_org_context — dependency: возвращает OrganizationContext или None
- require_org_context — dependency: требует OrganizationContext, иначе 400
- require_org_admin — dependency: требует owner/admin роль в организации, иначе 403
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from fastapi import Depends, Header, HTTPException, status
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
