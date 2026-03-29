# -*- coding: utf-8 -*-
"""
Company Conditions CRUD API
Управление стандартными условиями компании пользователя
"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from loguru import logger

from src.models.database import get_db
from src.models.auth_models import User
from src.models.condition_models import CompanyCondition, CONDITION_CATEGORIES
from src.api.dependencies import get_current_user

from .schemas import (
    ConditionCreate,
    ConditionUpdate,
    ConditionResponse,
    ConditionListResponse,
)

router = APIRouter()


@router.get("", response_model=ConditionListResponse)
async def list_conditions(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    category: Optional[str] = None,
    is_active: Optional[bool] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Список условий компании текущего пользователя"""
    query = db.query(CompanyCondition).filter(
        CompanyCondition.user_id == current_user.id
    )
    if category:
        query = query.filter(CompanyCondition.category == category)
    if is_active is not None:
        query = query.filter(CompanyCondition.is_active == is_active)

    total = query.count()
    conditions = (
        query
        .order_by(CompanyCondition.priority.desc(), CompanyCondition.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    return ConditionListResponse(
        conditions=[ConditionResponse(**c.to_dict()) for c in conditions],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/categories")
async def get_categories(current_user: User = Depends(get_current_user)):
    """Список доступных категорий условий"""
    labels = {
        'financial': 'Финансовые',
        'deadlines': 'Сроки',
        'liability': 'Ответственность',
        'termination': 'Расторжение',
        'confidentiality': 'Конфиденциальность',
        'warranties': 'Гарантии',
        'force_majeure': 'Форс-мажор',
        'dispute': 'Разрешение споров',
        'ip': 'Интеллектуальная собственность',
        'compliance': 'Соответствие требованиям',
        'other': 'Прочие',
    }
    return [{'value': c, 'label': labels.get(c, c)} for c in CONDITION_CATEGORIES]


@router.post("", response_model=ConditionResponse, status_code=status.HTTP_201_CREATED)
async def create_condition(
    data: ConditionCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Создать новое условие компании"""
    if data.category not in CONDITION_CATEGORIES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Неизвестная категория: {data.category}"
        )

    condition = CompanyCondition(
        user_id=current_user.id,
        category=data.category,
        title=data.title,
        description=data.description,
        condition_text=data.condition_text,
        priority=data.priority,
        is_active=data.is_active,
    )
    db.add(condition)
    db.commit()
    db.refresh(condition)

    logger.info(f"Condition created: {condition.id} by user {current_user.id}")
    return ConditionResponse(**condition.to_dict())


@router.get("/{condition_id}", response_model=ConditionResponse)
async def get_condition(
    condition_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Получить условие по ID"""
    condition = db.query(CompanyCondition).filter(
        CompanyCondition.id == condition_id,
        CompanyCondition.user_id == current_user.id,
    ).first()
    if not condition:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Условие не найдено")
    return ConditionResponse(**condition.to_dict())


@router.put("/{condition_id}", response_model=ConditionResponse)
async def update_condition(
    condition_id: str,
    data: ConditionUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Обновить условие компании"""
    condition = db.query(CompanyCondition).filter(
        CompanyCondition.id == condition_id,
        CompanyCondition.user_id == current_user.id,
    ).first()
    if not condition:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Условие не найдено")

    update_data = data.model_dump(exclude_unset=True)
    if 'category' in update_data and update_data['category'] not in CONDITION_CATEGORIES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Неизвестная категория: {update_data['category']}"
        )

    for key, value in update_data.items():
        setattr(condition, key, value)

    db.commit()
    db.refresh(condition)

    logger.info(f"Condition updated: {condition.id}")
    return ConditionResponse(**condition.to_dict())


@router.delete("/{condition_id}")
async def delete_condition(
    condition_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Удалить условие компании"""
    condition = db.query(CompanyCondition).filter(
        CompanyCondition.id == condition_id,
        CompanyCondition.user_id == current_user.id,
    ).first()
    if not condition:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Условие не найдено")

    db.delete(condition)
    db.commit()

    logger.info(f"Condition deleted: {condition_id}")
    return {"ok": True, "message": "Условие удалено"}
