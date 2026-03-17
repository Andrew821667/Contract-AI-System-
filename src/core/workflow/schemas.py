"""Workflow Engine — Pydantic schemas для API."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class WorkflowDefinitionCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = Field(None, max_length=2000)
    document_type: str | None = Field(None, max_length=100)
    jurisdiction: str | None = Field(None, max_length=100)
    org_id: str | None = Field(None, max_length=50)
    conditions: dict[str, Any] | None = None
    steps: list[dict[str, Any]] = Field(..., max_length=50)


class WorkflowDefinitionRead(BaseModel):
    id: str
    name: str
    description: str | None
    document_type: str | None
    jurisdiction: str | None
    org_id: str | None
    conditions: dict[str, Any] | None
    steps: list[dict[str, Any]]
    active: bool
    version: int
    created_at: datetime

    model_config = {"from_attributes": True}


class WorkflowTaskRead(BaseModel):
    id: str
    execution_id: str
    step_name: str
    step_order: int
    assignee_id: str | None
    task_type: str
    status: str
    decision: str | None
    comment: str | None
    sla_deadline: datetime | None
    sla_breached: bool
    created_at: datetime
    completed_at: datetime | None

    model_config = {"from_attributes": True}
