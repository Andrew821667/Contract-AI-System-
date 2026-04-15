# -*- coding: utf-8 -*-
"""
API v2 — Organizations

Управление организациями: создание, участники.
"""
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from src.api.dependencies import get_current_user
from src.api.v2.dependencies import verify_org_membership
from src.models.database import get_db, generate_uuid
from src.models.auth_models import User
from src.core.identity_org.models import (
    Organization,
    OrganizationMembership,
)
from src.core.identity_org.schemas import (
    OrganizationCreate,
    OrganizationUpdate,
    OrganizationRead,
    OrganizationMembershipCreate,
    OrganizationMembershipUpdate,
    OrganizationMembershipRead,
    OrganizationInvite,
)

router = APIRouter(tags=["Organizations"])


# ──────────────────────────────────────────────
# GET /organizations
# ──────────────────────────────────────────────
@router.get(
    "/organizations",
    response_model=List[OrganizationRead],
    summary="Мои организации",
)
async def list_my_organizations(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Организации, в которых состоит текущий пользователь."""
    memberships = (
        db.query(OrganizationMembership)
        .filter(
            OrganizationMembership.user_id == current_user.id,
            OrganizationMembership.active == True,  # noqa: E712
        )
        .all()
    )
    org_ids = [m.org_id for m in memberships]
    if not org_ids:
        return []
    orgs = db.query(Organization).filter(Organization.id.in_(org_ids)).all()
    return orgs


# ──────────────────────────────────────────────
# GET /organizations/{org_id}
# ──────────────────────────────────────────────
@router.get(
    "/organizations/{org_id}",
    response_model=OrganizationRead,
    summary="Информация об организации",
)
async def get_organization(
    org_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Получить информацию об организации (требуется членство)."""
    verify_org_membership(org_id, current_user, db)
    org = db.query(Organization).filter(Organization.id == org_id).first()
    if not org:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Организация не найдена")
    return org


# ──────────────────────────────────────────────
# POST /organizations
# ──────────────────────────────────────────────
@router.post(
    "/organizations",
    response_model=OrganizationRead,
    status_code=status.HTTP_201_CREATED,
    summary="Создать организацию",
)
async def create_organization(
    body: OrganizationCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Создаёт новую организацию. Текущий пользователь автоматически
    становится org_admin.
    """
    # Проверяем уникальность slug
    existing = (
        db.query(Organization)
        .filter(Organization.slug == body.slug)
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Организация со slug '{body.slug}' уже существует",
        )

    org = Organization(
        id=generate_uuid(),
        name=body.name,
        slug=body.slug,
        description=body.description,
        settings=body.settings,
    )
    db.add(org)
    db.flush()  # Получаем org.id для membership

    # Автоматически добавляем создателя как org_admin
    membership = OrganizationMembership(
        id=generate_uuid(),
        user_id=current_user.id,
        org_id=org.id,
        functional_role="org_admin",
    )
    db.add(membership)

    db.commit()
    db.refresh(org)
    return org


# ──────────────────────────────────────────────
# GET /organizations/{org_id}/members
# ──────────────────────────────────────────────
@router.get(
    "/organizations/{org_id}/members",
    response_model=List[OrganizationMembershipRead],
    summary="Участники организации",
)
async def list_members(
    org_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Возвращает список активных участников организации.
    """
    # IDOR fix: проверяем, что пользователь — участник организации
    verify_org_membership(org_id, current_user, db)

    rows = (
        db.query(OrganizationMembership, User)
        .join(User, OrganizationMembership.user_id == User.id, isouter=True)
        .filter(
            OrganizationMembership.org_id == org_id,
            OrganizationMembership.active == True,  # noqa: E712
        )
        .order_by(OrganizationMembership.joined_at.asc())
        .limit(500)
        .all()
    )
    return [
        OrganizationMembershipRead(
            id=m.id,
            user_id=m.user_id,
            org_id=m.org_id,
            unit_id=m.unit_id,
            company_role=m.company_role,
            functional_role=m.functional_role,
            active=m.active,
            joined_at=m.joined_at,
            user_name=u.name if u else None,
            user_email=u.email if u else None,
        )
        for m, u in rows
    ]


# ──────────────────────────────────────────────
# POST /organizations/{org_id}/members
# ──────────────────────────────────────────────
@router.post(
    "/organizations/{org_id}/members",
    response_model=OrganizationMembershipRead,
    status_code=status.HTTP_201_CREATED,
    summary="Добавить участника в организацию",
)
async def add_member(
    org_id: str,
    body: OrganizationMembershipCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Добавляет пользователя в организацию.
    Только org_admin может добавлять участников.
    """
    org = db.query(Organization).filter(Organization.id == org_id).first()
    if not org:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Запрашиваемая организация не найдена",
        )

    # Проверяем, что текущий пользователь — org_admin
    caller_membership = (
        db.query(OrganizationMembership)
        .filter(
            OrganizationMembership.org_id == org_id,
            OrganizationMembership.user_id == current_user.id,
            OrganizationMembership.active == True,  # noqa: E712
        )
        .first()
    )
    # Пропускаем проверку для admin платформы
    if current_user.role != "admin":
        if not caller_membership or caller_membership.functional_role != "org_admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Только администратор организации может добавлять участников",
            )

    # Проверяем, что пользователь не состоит уже в этой организации
    existing = (
        db.query(OrganizationMembership)
        .filter(
            OrganizationMembership.user_id == body.user_id,
            OrganizationMembership.org_id == org_id,
        )
        .first()
    )
    if existing:
        if existing.active:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Пользователь уже является участником организации",
            )
        # Реактивация
        existing.active = True
        existing.functional_role = body.functional_role
        existing.company_role = body.company_role
        existing.unit_id = body.unit_id
        db.commit()
        db.refresh(existing)
        return existing

    # Проверяем существование пользователя
    target_user = db.query(User).filter(User.id == body.user_id).first()
    if not target_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Указанный пользователь не найден",
        )

    membership = OrganizationMembership(
        id=generate_uuid(),
        user_id=body.user_id,
        org_id=org_id,
        unit_id=body.unit_id,
        company_role=body.company_role,
        functional_role=body.functional_role,
    )
    db.add(membership)
    db.commit()
    db.refresh(membership)
    return membership


# ──────────────────────────────────────────────
# PATCH /organizations/{org_id}
# ──────────────────────────────────────────────
@router.patch(
    "/organizations/{org_id}",
    response_model=OrganizationRead,
    summary="Обновить организацию",
)
async def update_organization(
    org_id: str,
    body: OrganizationUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Обновить данные организации. Только org_admin."""
    _require_org_admin(org_id, current_user, db)

    org = db.query(Organization).filter(Organization.id == org_id).first()
    if not org:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Организация не найдена")

    if body.name is not None:
        org.name = body.name
    if body.description is not None:
        org.description = body.description
    if body.settings is not None:
        org.settings = body.settings

    db.commit()
    db.refresh(org)
    return org


# ──────────────────────────────────────────────
# PATCH /organizations/{org_id}/members/{user_id}
# ──────────────────────────────────────────────
@router.patch(
    "/organizations/{org_id}/members/{user_id}",
    response_model=OrganizationMembershipRead,
    summary="Изменить роль участника",
)
async def update_member_role(
    org_id: str,
    user_id: str,
    body: OrganizationMembershipUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Изменить роль участника. Только org_admin."""
    _require_org_admin(org_id, current_user, db)

    membership = (
        db.query(OrganizationMembership)
        .filter(
            OrganizationMembership.org_id == org_id,
            OrganizationMembership.user_id == user_id,
            OrganizationMembership.active == True,
        )
        .first()
    )
    if not membership:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Участник не найден")

    membership.functional_role = body.functional_role
    if body.company_role is not None:
        membership.company_role = body.company_role

    db.commit()
    db.refresh(membership)
    return membership


# ──────────────────────────────────────────────
# DELETE /organizations/{org_id}/members/{user_id}
# ──────────────────────────────────────────────
@router.delete(
    "/organizations/{org_id}/members/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Удалить участника",
)
async def remove_member(
    org_id: str,
    user_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Удалить участника из организации. Только org_admin."""
    _require_org_admin(org_id, current_user, db)

    if str(user_id) == str(current_user.id):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Нельзя удалить самого себя")

    membership = (
        db.query(OrganizationMembership)
        .filter(
            OrganizationMembership.org_id == org_id,
            OrganizationMembership.user_id == user_id,
            OrganizationMembership.active == True,
        )
        .first()
    )
    if not membership:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Участник не найден")

    membership.active = False
    db.commit()


# ──────────────────────────────────────────────
# POST /organizations/{org_id}/invite
# ──────────────────────────────────────────────
@router.post(
    "/organizations/{org_id}/invite",
    response_model=OrganizationMembershipRead,
    status_code=status.HTTP_201_CREATED,
    summary="Пригласить по email",
)
async def invite_member_by_email(
    org_id: str,
    body: OrganizationInvite,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Пригласить пользователя по email. org_admin или manager."""
    caller = _get_membership(org_id, current_user, db)
    if not caller or caller.functional_role not in ("org_admin", "manager"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Недостаточно прав")

    target_user = db.query(User).filter(User.email == body.email).first()
    if not target_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Пользователь с таким email не зарегистрирован в системе",
        )

    existing = (
        db.query(OrganizationMembership)
        .filter(
            OrganizationMembership.user_id == target_user.id,
            OrganizationMembership.org_id == org_id,
        )
        .first()
    )
    if existing and existing.active:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Пользователь уже в организации")

    if existing:
        existing.active = True
        existing.functional_role = body.functional_role
        existing.company_role = body.company_role
        db.commit()
        db.refresh(existing)
        return existing

    membership = OrganizationMembership(
        id=generate_uuid(),
        user_id=target_user.id,
        org_id=org_id,
        functional_role=body.functional_role,
        company_role=body.company_role,
    )
    db.add(membership)
    db.commit()
    db.refresh(membership)
    return membership


# ── Helpers ──

def _get_membership(org_id: str, user: User, db: Session):
    """Get active membership for user in org."""
    return (
        db.query(OrganizationMembership)
        .filter(
            OrganizationMembership.org_id == org_id,
            OrganizationMembership.user_id == user.id,
            OrganizationMembership.active == True,
        )
        .first()
    )


def _require_org_admin(org_id: str, user: User, db: Session):
    """Require that user is org_admin (or platform admin)."""
    if user.role == "admin":
        return
    m = _get_membership(org_id, user, db)
    if not m or m.functional_role != "org_admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Только администратор организации может выполнить это действие",
        )
