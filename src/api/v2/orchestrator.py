# -*- coding: utf-8 -*-
"""
API v2 — Orchestrator

Управление OrchestratorRun: запуск, статус, продолжение, отмена.
"""
from datetime import datetime, timezone
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from src.api.dependencies import get_current_user
from src.api.v2.dependencies import (
    verify_document_access,
    verify_orchestrator_run_ownership,
)
from src.models.database import get_db, generate_uuid
from src.models.auth_models import User
from src.core.orchestrator.models import (
    OrchestratorRun,
    OrchestratorCheckpoint,
    ExecutionPlan,
    PlanStep,
)
from src.core.orchestrator.schemas import (
    OrchestratorRunCreate,
    OrchestratorRunRead,
    ExecutionPlanRead,
    PlanStepRead,
)

router = APIRouter(tags=["Orchestrator"])


# ──────────────────────────────────────────────
# POST /orchestrator/runs
# ──────────────────────────────────────────────
@router.post(
    "/orchestrator/runs",
    response_model=OrchestratorRunRead,
    status_code=status.HTTP_201_CREATED,
    summary="Запустить оркестрацию по цели",
)
async def create_run(
    body: OrchestratorRunCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Создаёт OrchestratorRun с указанной целью.
    """
    # IDOR fix: проверяем доступ к документу (если указан)
    if body.document_id:
        verify_document_access(body.document_id, current_user, db)

    run = OrchestratorRun(
        id=generate_uuid(),
        goal=body.goal,
        initiated_by=current_user.id,
        document_id=body.document_id,
        status="planning",
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    return run


# ──────────────────────────────────────────────
# GET /orchestrator/runs/{run_id}
# ──────────────────────────────────────────────
@router.get(
    "/orchestrator/runs/{run_id}",
    response_model=OrchestratorRunRead,
    summary="Статус оркестрации",
)
async def get_run(
    run_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Возвращает текущий статус OrchestratorRun."""
    # IDOR fix: проверяем ownership
    run = verify_orchestrator_run_ownership(run_id, current_user, db)
    return run


# ──────────────────────────────────────────────
# POST /orchestrator/runs/{run_id}/continue
# ──────────────────────────────────────────────
@router.post(
    "/orchestrator/runs/{run_id}/continue",
    response_model=OrchestratorRunRead,
    summary="Продолжить оркестрацию после approval",
)
async def continue_run(
    run_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Продолжает выполнение оркестрации после одобрения checkpoint.
    """
    # IDOR fix: проверяем ownership
    run = verify_orchestrator_run_ownership(run_id, current_user, db)

    if run.status != "paused":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Нельзя продолжить оркестрацию в статусе '{run.status}'. "
                   f"Допустимый статус: 'paused'",
        )

    # Одобряем все pending checkpoints
    pending_checkpoints = (
        db.query(OrchestratorCheckpoint)
        .filter(
            OrchestratorCheckpoint.run_id == run_id,
            OrchestratorCheckpoint.status == "pending",
        )
        .all()
    )
    for cp in pending_checkpoints:
        cp.status = "approved"
        cp.resolved_by = current_user.id
        cp.resolved_at = datetime.now(timezone.utc)

    run.status = "executing"
    run.updated_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(run)
    return run


# ──────────────────────────────────────────────
# POST /orchestrator/runs/{run_id}/cancel
# ──────────────────────────────────────────────
@router.post(
    "/orchestrator/runs/{run_id}/cancel",
    response_model=OrchestratorRunRead,
    summary="Отменить оркестрацию",
)
async def cancel_run(
    run_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Отменяет выполнение оркестрации.
    """
    # IDOR fix: проверяем ownership
    run = verify_orchestrator_run_ownership(run_id, current_user, db)

    terminal_statuses = {"completed", "failed", "cancelled"}
    if run.status in terminal_statuses:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Оркестрация уже в терминальном статусе '{run.status}'",
        )

    run.status = "cancelled"
    run.updated_at = datetime.now(timezone.utc)
    run.completed_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(run)
    return run


# ──────────────────────────────────────────────
# GET /orchestrator/runs/{run_id}/plan
# ──────────────────────────────────────────────
@router.get(
    "/orchestrator/runs/{run_id}/plan",
    response_model=ExecutionPlanRead,
    summary="Текущий план выполнения оркестрации",
)
async def get_run_plan(
    run_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Возвращает текущий (последний по версии) план выполнения.
    """
    # IDOR fix: проверяем ownership
    verify_orchestrator_run_ownership(run_id, current_user, db)

    plan = (
        db.query(ExecutionPlan)
        .filter(ExecutionPlan.run_id == run_id)
        .order_by(ExecutionPlan.version.desc())
        .first()
    )
    if not plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"План выполнения для оркестрации с id={run_id} не найден",
        )

    return plan


# ──────────────────────────────────────────────
# GET /orchestrator/runs/{run_id}/steps
# ──────────────────────────────────────────────
@router.get(
    "/orchestrator/runs/{run_id}/steps",
    summary="Список шагов оркестрации с статусами",
)
async def list_run_steps(
    run_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Возвращает все шаги текущего плана выполнения.
    """
    # IDOR fix: проверяем ownership
    verify_orchestrator_run_ownership(run_id, current_user, db)

    plan = (
        db.query(ExecutionPlan)
        .filter(ExecutionPlan.run_id == run_id)
        .order_by(ExecutionPlan.version.desc())
        .first()
    )
    if not plan:
        return {"steps": []}

    steps = (
        db.query(PlanStep)
        .filter(PlanStep.plan_id == plan.id)
        .order_by(PlanStep.order.asc())
        .all()
    )
    return {"steps": [PlanStepRead.model_validate(s) for s in steps]}
