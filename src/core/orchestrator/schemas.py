"""Orchestrator — Pydantic schemas для API."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class OrchestratorRunCreate(BaseModel):
    goal: str = Field(..., min_length=1, max_length=2000)
    document_id: str | None = None


class OrchestratorRunRead(BaseModel):
    id: str
    goal: str
    initiated_by: str | None
    document_id: str | None
    session_id: str | None
    status: str
    total_steps: int
    completed_steps: int
    failed_steps: int
    created_at: datetime
    completed_at: datetime | None

    model_config = {"from_attributes": True}


class ExecutionPlanRead(BaseModel):
    id: str
    run_id: str
    plan_definition: dict[str, Any]
    version: int
    created_at: datetime
    steps: list["PlanStepRead"] = []

    model_config = {"from_attributes": True}


class PlanStepRead(BaseModel):
    id: str
    plan_id: str
    order: int
    name: str | None
    step_type: str
    tool_id: str | None
    agent_id: str | None
    input_data: dict[str, Any] | None
    output_data: dict[str, Any] | None
    status: str
    error: str | None
    started_at: datetime | None
    completed_at: datetime | None

    model_config = {"from_attributes": True}


# Rebuild для разрешения forward reference на PlanStepRead
ExecutionPlanRead.model_rebuild()
