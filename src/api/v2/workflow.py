# -*- coding: utf-8 -*-
"""
API v2 — Workflow

Маршруты согласования: создание определений, задачи пользователя,
завершение и эскалация задач.
"""
from typing import List

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from src.api.dependencies import get_current_user
from src.api.v2.dependencies import (
    OrganizationContext,
    get_org_context,
    verify_workflow_task_ownership,
)
from src.models.database import get_db
from src.models.auth_models import User
from src.core.workflow.engine import WorkflowEngineService
from src.core.workflow.schemas import (
    WorkflowDefinitionCreate,
    WorkflowDefinitionRead,
    WorkflowTaskRead,
    WorkflowExecutionRead,
    WorkflowStartRequest,
)
from src.core.workflow.models import WorkflowDefinition, WorkflowExecution, WorkflowTask

router = APIRouter(tags=["Workflow"])


# ── Request bodies ──────────────────────────────


class TaskCompleteBody(BaseModel):
    decision: Literal["approve", "reject", "return_for_revision"] = Field(...)
    comment: str | None = Field(None, max_length=5000)


class TaskEscalateBody(BaseModel):
    reason: str | None = Field(None, max_length=2000)


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
    # Security: только admin может создавать workflow definitions
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Только администратор может создавать маршруты согласования",
        )
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
# GET /workflow/definitions
# ──────────────────────────────────────────────
@router.get(
    "/workflow/definitions",
    response_model=List[WorkflowDefinitionRead],
    summary="Список маршрутов согласования",
)
async def list_workflow_definitions(
    active_only: bool = Query(True),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> List[WorkflowDefinitionRead]:
    """Получить список маршрутов согласования."""
    query = db.query(WorkflowDefinition)
    if active_only:
        query = query.filter(WorkflowDefinition.active.is_(True))
    definitions = query.order_by(WorkflowDefinition.created_at.desc()).all()
    return [WorkflowDefinitionRead.model_validate(d) for d in definitions]


# ──────────────────────────────────────────────
# POST /workflow/executions
# ──────────────────────────────────────────────
@router.post(
    "/workflow/executions",
    response_model=WorkflowExecutionRead,
    status_code=status.HTTP_201_CREATED,
    summary="Запустить маршрут согласования для документа",
)
async def start_workflow_execution(
    body: WorkflowStartRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    ctx: OrganizationContext | None = Depends(get_org_context),
) -> WorkflowExecutionRead:
    """Запустить маршрут согласования для документа."""
    from src.api.v2.dependencies import verify_document_access
    verify_document_access(body.document_id, current_user, db, ctx)

    engine = WorkflowEngineService(db)
    try:
        execution = engine.start_workflow(
            definition_id=body.definition_id,
            document_id=body.document_id,
            initiated_by=str(current_user.id),
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    db.commit()
    db.refresh(execution)
    return WorkflowExecutionRead.model_validate(execution)


# ──────────────────────────────────────────────
# GET /workflow/executions/{document_id}
# ──────────────────────────────────────────────
@router.get(
    "/workflow/executions/{document_id}",
    response_model=List[WorkflowExecutionRead],
    summary="Workflow-процессы документа",
)
async def get_document_executions(
    document_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    ctx: OrganizationContext | None = Depends(get_org_context),
) -> List[WorkflowExecutionRead]:
    """Получить workflow-процессы для документа."""
    from src.api.v2.dependencies import verify_document_access
    verify_document_access(document_id, current_user, db, ctx)

    executions = (
        db.query(WorkflowExecution)
        .filter(WorkflowExecution.document_id == document_id)
        .order_by(WorkflowExecution.started_at.desc())
        .all()
    )
    return [WorkflowExecutionRead.model_validate(e) for e in executions]


# ──────────────────────────────────────────────
# GET /workflow/executions/{execution_id}/tasks
# ──────────────────────────────────────────────
@router.get(
    "/workflow/executions/{execution_id}/tasks",
    response_model=List[WorkflowTaskRead],
    summary="Задачи workflow-процесса",
)
async def get_execution_tasks(
    execution_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> List[WorkflowTaskRead]:
    """Получить все задачи конкретного workflow-процесса."""
    execution = db.query(WorkflowExecution).filter(WorkflowExecution.id == execution_id).first()
    if not execution:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workflow-процесс не найден")

    tasks = (
        db.query(WorkflowTask)
        .filter(WorkflowTask.execution_id == execution_id)
        .order_by(WorkflowTask.step_order.asc())
        .all()
    )
    return [WorkflowTaskRead.model_validate(t) for t in tasks]


# ──────────────────────────────────────────────
# GET /workflow/tasks
# ──────────────────────────────────────────────
@router.get(
    "/workflow/tasks",
    response_model=List[WorkflowTaskRead],
    summary="Мои задачи",
)
async def get_my_tasks(
    status_filter: Literal["pending", "in_progress", "completed", "cancelled"] = Query("pending"),
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
    ctx: OrganizationContext | None = Depends(get_org_context),
) -> WorkflowTaskRead:
    """Завершить задачу с решением (approve/reject/return_for_revision)."""
    # IDOR fix: проверяем, что задача назначена текущему пользователю
    verify_workflow_task_ownership(task_id, current_user, db, ctx)

    engine = WorkflowEngineService(db)
    try:
        task = engine.complete_task(
            task_id=task_id,
            user_id=str(current_user.id),
            decision=body.decision,
            comment=body.comment,
        )
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Задача не найдена",
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
    ctx: OrganizationContext | None = Depends(get_org_context),
) -> WorkflowTaskRead:
    """Эскалировать задачу на следующий уровень."""
    # IDOR fix: проверяем, что задача назначена текущему пользователю
    task = verify_workflow_task_ownership(task_id, current_user, db, ctx)

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
