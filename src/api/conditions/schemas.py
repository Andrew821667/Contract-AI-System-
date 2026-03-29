# -*- coding: utf-8 -*-
"""
Company Conditions — Pydantic schemas
"""
from typing import Optional, List
from pydantic import BaseModel, Field


class ConditionCreate(BaseModel):
    category: str = Field(default='other', description="Категория условия")
    title: str = Field(..., min_length=1, max_length=500, description="Название условия")
    description: Optional[str] = Field(None, description="Описание")
    condition_text: str = Field(..., min_length=1, description="Текст условия")
    priority: int = Field(default=1, ge=1, le=3, description="Приоритет: 1=низкий, 2=средний, 3=высокий")
    is_active: bool = Field(default=True)


class ConditionUpdate(BaseModel):
    category: Optional[str] = None
    title: Optional[str] = Field(None, min_length=1, max_length=500)
    description: Optional[str] = None
    condition_text: Optional[str] = Field(None, min_length=1)
    priority: Optional[int] = Field(None, ge=1, le=3)
    is_active: Optional[bool] = None


class ConditionResponse(BaseModel):
    id: str
    user_id: str
    category: str
    title: str
    description: Optional[str]
    condition_text: str
    priority: int
    is_active: bool
    created_at: Optional[str]
    updated_at: Optional[str]

    model_config = {"from_attributes": True}


class ConditionListResponse(BaseModel):
    conditions: List[ConditionResponse]
    total: int
    page: int
    page_size: int
