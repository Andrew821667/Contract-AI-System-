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
    OrganizationRead,
    OrganizationMembershipCreate,
    OrganizationMembershipRead,
)

router = APIRouter(tags=["Organizations"])


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

    members = (
        db.query(OrganizationMembership)
        .filter(
            OrganizationMembership.org_id == org_id,
            OrganizationMembership.active == True,  # noqa: E712
        )
        .order_by(OrganizationMembership.joined_at.asc())
        .limit(500)
        .all()
    )
    return members


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
            detail=f"Организация с id={org_id} не найдена",
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
            detail=f"Пользователь с id={body.user_id} не найден",
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
