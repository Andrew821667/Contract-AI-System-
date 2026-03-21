"""Orchestrator — Pydantic schemas для API."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, computed_field, model_validator


class OrchestratorRunCreate(BaseModel):
    goal: str = Field(..., min_length=1, max_length=2000)
    document_id: str | None = None


class OrchestratorRunRead(BaseModel):
    id: str
    goal: str
    initiated_by: str | None
    document_id: str | None
    session_id: str | None
    status: str  # DB: planning|executing|paused|completed|failed|cancelled
    total_steps: int
    completed_steps: int
    failed_steps: int
    created_at: datetime
    updated_at: datetime | None = None
    completed_at: datetime | None = None
    error: str | None = None

    # Frontend-compatible aliases
    @computed_field  # type: ignore[prop-decorator]
    @property
    def steps_total(self) -> int:
        return self.total_steps

    @computed_field  # type: ignore[prop-decorator]
    @property
    def steps_completed(self) -> int:
        return self.completed_steps

    @computed_field  # type: ignore[prop-decorator]
    @property
    def progress(self) -> int:
        if self.total_steps == 0:
            return 0
        return round((self.completed_steps / self.total_steps) * 100)

    @model_validator(mode="after")
    def _normalize_status(self) -> "OrchestratorRunRead":
        """Map DB 'executing' → frontend 'running'."""
        if self.status == "executing":
            self.status = "running"
        return self

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

    # Frontend-compatible aliases
    @computed_field  # type: ignore[prop-decorator]
    @property
    def step_number(self) -> int:
        return self.order

    @computed_field  # type: ignore[prop-decorator]
    @property
    def tool_name(self) -> str | None:
        return self.tool_id

    @computed_field  # type: ignore[prop-decorator]
    @property
    def input(self) -> dict[str, Any] | None:
        return self.input_data

    @computed_field  # type: ignore[prop-decorator]
    @property
    def output(self) -> dict[str, Any] | None:
        return self.output_data

    model_config = {"from_attributes": True}


# Rebuild для разрешения forward reference на PlanStepRead
ExecutionPlanRead.model_rebuild()
