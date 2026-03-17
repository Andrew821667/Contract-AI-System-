# -*- coding: utf-8 -*-
"""
API v2 — Workflow

Маршруты согласования: создание определений, задачи пользователя,
завершение и эскалация задач.
"""
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from src.api.dependencies import get_current_user
from src.api.v2.dependencies import verify_workflow_task_ownership
from src.models.database import get_db
from src.models.auth_models import User
from src.core.workflow.engine import WorkflowEngineService
from src.core.workflow.schemas import (
    WorkflowDefinitionCreate,
    WorkflowDefinitionRead,
    WorkflowTaskRead,
)
from src.core.workflow.models import WorkflowDefinition, WorkflowTask

router = APIRouter(tags=["Workflow"])


# ── Request bodies ──────────────────────────────


class TaskCompleteBody(BaseModel):
    decision: str = Field(..., description="approve / reject / return_for_revision")
    comment: str | None = None


class TaskEscalateBody(BaseModel):
    reason: str | None = None


# ──────────────────────────────────────────────
# POST /workflow/definitions
# ──────────────────────────────────────────────
@router.post(
    "/workflow/definitions",
    response_model=WorkflowDefinitionRead,
    status_code=status.HTTP_201_CREATED,
    summary="Создать маршрут согласования",
)
async def create_workflow_definition(
    body: WorkflowDefinitionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> WorkflowDefinitionRead:
    """Создать новый шаблон маршрута согласования."""
    definition = WorkflowDefinition(
        name=body.name,
        description=body.description,
        document_type=body.document_type,
        jurisdiction=body.jurisdiction,
        org_id=body.org_id,
        conditions=body.conditions,
        steps=body.steps,
        active=True,
        version=1,
    )
    db.add(definition)
    db.commit()
    db.refresh(definition)
    return WorkflowDefinitionRead.model_validate(definition)


# ──────────────────────────────────────────────
# GET /workflow/tasks
# ──────────────────────────────────────────────
@router.get(
    "/workflow/tasks",
    response_model=List[WorkflowTaskRead],
    summary="Мои задачи",
)
async def get_my_tasks(
    status_filter: str = "pending",
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> List[WorkflowTaskRead]:
    """Получить задачи текущего пользователя."""
    engine = WorkflowEngineService(db)
    tasks = engine.get_user_tasks(user_id=str(current_user.id), status=status_filter)
    return [WorkflowTaskRead.model_validate(t) for t in tasks]


# ──────────────────────────────────────────────
# POST /workflow/tasks/{task_id}/complete
# ──────────────────────────────────────────────
@router.post(
    "/workflow/tasks/{task_id}/complete",
    response_model=WorkflowTaskRead,
    summary="Завершить задачу",
)
async def complete_task(
    task_id: str,
    body: TaskCompleteBody,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> WorkflowTaskRead:
    """Завершить задачу с решением (approve/reject/return_for_revision)."""
    engine = WorkflowEngineService(db)
    try:
        task = engine.complete_task(
            task_id=task_id,
            user_id=str(current_user.id),
            decision=body.decision,
            comment=body.comment,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )
    db.commit()
    db.refresh(task)
    return WorkflowTaskRead.model_validate(task)


# ──────────────────────────────────────────────
# POST /workflow/tasks/{task_id}/escalate
# ──────────────────────────────────────────────
@router.post(
    "/workflow/tasks/{task_id}/escalate",
    response_model=WorkflowTaskRead,
    summary="Эскалировать задачу",
)
async def escalate_task(
    task_id: str,
    body: TaskEscalateBody | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> WorkflowTaskRead:
    """Эскалировать задачу на следующий уровень."""
    # IDOR fix: проверяем, что задача назначена текущему пользователю
    task = verify_workflow_task_ownership(task_id, current_user, db)

    if task.status in ("completed", "escalated"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Задача {task_id} уже завершена или эскалирована",
        )

    task.status = "escalated"

    # Записываем событие эскалации
    engine = WorkflowEngineService(db)
    engine._emit_event(
        execution_id=task.execution_id,
        event_type="task_escalated",
        payload={
            "task_id": task_id,
            "user_id": str(current_user.id),
            "reason": body.reason if body else None,
        },
    )

    db.commit()
    db.refresh(task)
    return WorkflowTaskRead.model_validate(task)
