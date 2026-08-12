# -*- coding: utf-8 -*-
"""
API v2 — Tools & Agents

Просмотр зарегистрированных инструментов и агентов.
"""
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.api.dependencies import get_current_user
from src.models.database import get_db
from src.models.auth_models import User
from src.core.tools.models import ToolDefinition
from src.core.tools.schemas import ToolDefinitionRead
from src.core.agents.models import AgentDefinition
from src.core.agents.schemas import AgentDefinitionRead


def _runtime_registries(request: Request):
    """Реестры, поднятые bootstrap-ом при старте (могут отсутствовать)."""
    svc = getattr(request.app.state, "core_services", None)
    if svc is None:
        return None, None
    return getattr(svc, "tool_registry", None), getattr(svc, "agent_registry", None)


def _tool_from_runtime(tool: Any) -> ToolDefinitionRead:
    """ITool → та же схема, что и для записи из таблицы."""
    g = lambda attr, default=None: getattr(tool, attr, default)  # noqa: E731
    return ToolDefinitionRead(
        id=str(g("tool_id", "")),
        tool_id=str(g("tool_id", "")),
        name=str(g("name", "") or g("tool_id", "")),
        description=g("description"),
        tool_type="runtime",
        input_schema=g("input_schema"),
        output_schema=g("output_schema"),
        permissions=g("permissions"),
        policy_tags=g("policy_tags"),
        risk_level=str(g("risk_level", "unknown")),
        sync_mode=str(g("sync_mode", "sync")),
        active=True,
        version="runtime",
        created_at=datetime.now(timezone.utc),
        source="runtime",
    )


def _agent_from_runtime(agent: Any) -> AgentDefinitionRead:
    """IAgent → та же схема, что и для записи из таблицы."""
    g = lambda attr, default=None: getattr(agent, attr, default)  # noqa: E731
    return AgentDefinitionRead(
        id=str(g("agent_id", "")),
        agent_id=str(g("agent_id", "")),
        name=str(g("name", "") or g("agent_id", "")),
        description=g("description"),
        specialization=str(g("specialization", "")),
        allowed_tools=g("allowed_tools"),
        task_types=g("task_types"),
        autonomy_level=str(g("autonomy_level", "")),
        confidence_threshold=float(g("confidence_threshold", 0.0) or 0.0),
        model_profile=g("model_profile"),
        active=True,
        version="runtime",
        created_at=datetime.now(timezone.utc),
        source="runtime",
    )


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
    request: Request,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Инструменты из таблицы плюс поднятые в рантайме.

    Таблица `tool_definitions` на проде пуста, а bootstrap регистрирует 17
    инструментов в памяти процесса — вкладка честно показывала «нет
    инструментов». Доливаем реестр, помечая источник, чтобы было видно, что
    эти записи не редактируются.
    """
    rows = db.query(ToolDefinition).order_by(ToolDefinition.created_at.desc()).all()
    items: List[ToolDefinitionRead] = [ToolDefinitionRead.model_validate(r, from_attributes=True) for r in rows]

    tool_registry, _ = _runtime_registries(request)
    if tool_registry is not None:
        known = {i.tool_id for i in items}
        for tool in tool_registry.list_all():
            mapped = _tool_from_runtime(tool)
            if mapped.tool_id and mapped.tool_id not in known:
                items.append(mapped)

    return items[offset: offset + limit]


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
    request: Request,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Агенты из таблицы плюс поднятые в рантайме — см. пояснение в list_tools."""
    rows = db.query(AgentDefinition).order_by(AgentDefinition.created_at.desc()).all()
    items: List[AgentDefinitionRead] = [AgentDefinitionRead.model_validate(r, from_attributes=True) for r in rows]

    _, agent_registry = _runtime_registries(request)
    if agent_registry is not None:
        known = {i.agent_id for i in items}
        for agent in agent_registry.list_all():
            mapped = _agent_from_runtime(agent)
            if mapped.agent_id and mapped.agent_id not in known:
                items.append(mapped)

    return items[offset: offset + limit]


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
