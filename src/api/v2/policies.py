# -*- coding: utf-8 -*-
"""
API v2 — Policies

Управление политиками: список, создание, обновление.
"""
from typing import List, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from src.api.dependencies import get_current_user
from src.models.database import get_db
from src.models.auth_models import User
from src.core.policies.models import Policy
from src.core.policies.schemas import PolicyCreate, PolicyRead

router = APIRouter(tags=["Policies"])


# ──────────────────────────────────────────────
# GET /policies
# ──────────────────────────────────────────────
@router.get(
    "/policies",
    response_model=List[PolicyRead],
    summary="Список политик",
)
async def list_policies(
    level: Optional[Literal["platform", "tenant", "organization", "branch", "document", "user"]] = Query(None, description="Фильтр по уровню каскада"),
    policy_type: Optional[Literal["llm_routing", "tool_access", "approval_rule", "action_permission", "data_sensitivity"]] = Query(None, description="Фильтр по типу политики"),
    active: Optional[bool] = Query(None, description="Фильтр по активности"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Возвращает список политик с опциональной фильтрацией."""
    query = db.query(Policy)

    if level is not None:
        query = query.filter(Policy.level == level)
    if policy_type is not None:
        query = query.filter(Policy.policy_type == policy_type)
    if active is not None:
        query = query.filter(Policy.active == active)

    limit_val = 50  # Default limit for policies
    return query.order_by(Policy.priority.desc(), Policy.created_at.desc()).limit(limit_val).all()


# ──────────────────────────────────────────────
# POST /policies
# ──────────────────────────────────────────────
@router.post(
    "/policies",
    response_model=PolicyRead,
    status_code=status.HTTP_201_CREATED,
    summary="Создать политику",
)
async def create_policy(
    body: PolicyCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Создаёт новую политику. Доступно только администраторам."""
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Создание политик доступно только администраторам",
        )

    policy = Policy(
        name=body.name,
        description=body.description,
        level=body.level,
        scope_id=body.scope_id,
        policy_type=body.policy_type,
        rules=body.rules,
        priority=body.priority,
    )
    db.add(policy)
    db.commit()
    db.refresh(policy)
    return policy


# ──────────────────────────────────────────────
# PATCH /policies/{policy_id}
# ──────────────────────────────────────────────
@router.patch(
    "/policies/{policy_id}",
    response_model=PolicyRead,
    summary="Обновить политику",
)
async def update_policy(
    policy_id: str,
    body: PolicyCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Обновляет существующую политику. Доступно только администраторам."""
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Обновление политик доступно только администраторам",
        )

    policy = db.query(Policy).filter(Policy.id == policy_id).first()
    if not policy:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Политика не найдена",
        )

    policy.name = body.name
    policy.description = body.description
    policy.level = body.level
    policy.scope_id = body.scope_id
    policy.policy_type = body.policy_type
    policy.rules = body.rules
    policy.priority = body.priority

    db.commit()
    db.refresh(policy)
    return policy
