# -*- coding: utf-8 -*-
"""
API v2 — Tools & Agents

Просмотр зарегистрированных инструментов и агентов.
"""
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.api.dependencies import get_current_user
from src.models.database import get_db
from src.models.auth_models import User
from src.core.tools.models import ToolDefinition
from src.core.tools.schemas import ToolDefinitionRead
from src.core.agents.models import AgentDefinition
from src.core.agents.schemas import AgentDefinitionRead


class AgentDefinitionUpdate(BaseModel):
    """Поля, доступные для редактирования агента."""
    allowed_tools: Optional[List[str]] = None
    autonomy_level: Optional[str] = None
    confidence_threshold: Optional[float] = None
    model_profile: Optional[Dict[str, Any]] = None
    active: Optional[bool] = None
    description: Optional[str] = None

router = APIRouter(tags=["Tools & Agents"])


# ──────────────────────────────────────────────
# GET /tools
# ──────────────────────────────────────────────
@router.get(
    "/tools",
    response_model=List[ToolDefinitionRead],
    summary="Список инструментов",
)
async def list_tools(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Возвращает список всех зарегистрированных инструментов."""
    return db.query(ToolDefinition).order_by(ToolDefinition.created_at.desc()).offset(offset).limit(limit).all()


# ──────────────────────────────────────────────
# GET /tools/{tool_id}
# ──────────────────────────────────────────────
@router.get(
    "/tools/{tool_id}",
    response_model=ToolDefinitionRead,
    summary="Детали инструмента",
)
async def get_tool(
    tool_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Возвращает детали конкретного инструмента по ID."""
    tool = db.query(ToolDefinition).filter(ToolDefinition.id == tool_id).first()
    if not tool:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Инструмент не найден",
        )
    return tool


# ──────────────────────────────────────────────
# GET /agents
# ──────────────────────────────────────────────
@router.get(
    "/agents",
    response_model=List[AgentDefinitionRead],
    summary="Список агентов",
)
async def list_agents(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Возвращает список всех зарегистрированных агентов."""
    return db.query(AgentDefinition).order_by(AgentDefinition.created_at.desc()).offset(offset).limit(limit).all()


# ──────────────────────────────────────────────
# GET /agents/{agent_id}
# ──────────────────────────────────────────────
@router.get(
    "/agents/{agent_id}",
    response_model=AgentDefinitionRead,
    summary="Детали агента",
)
async def get_agent(
    agent_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Возвращает детали конкретного агента по ID."""
    agent = db.query(AgentDefinition).filter(AgentDefinition.id == agent_id).first()
    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Агент не найден",
        )
    return agent


# ──────────────────────────────────────────────
# PATCH /agents/{agent_id}
# ──────────────────────────────────────────────
@router.patch(
    "/agents/{agent_id}",
    response_model=AgentDefinitionRead,
    summary="Обновить конфигурацию агента",
)
async def update_agent(
    agent_id: str,
    body: AgentDefinitionUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Обновляет настройки агента. Только для admin."""
    if current_user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Только для администраторов")

    agent = db.query(AgentDefinition).filter(AgentDefinition.id == agent_id).first()
    if not agent:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Агент не найден")

    VALID_AUTONOMY = {"advisor", "copilot", "processor", "autonomous"}
    update_data = body.model_dump(exclude_unset=True)
    if "autonomy_level" in update_data and update_data["autonomy_level"] not in VALID_AUTONOMY:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                            detail=f"autonomy_level должен быть одним из: {sorted(VALID_AUTONOMY)}")

    for field, value in update_data.items():
        setattr(agent, field, value)
    agent.updated_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(agent)
    return agent
