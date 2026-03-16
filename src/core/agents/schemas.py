"""Agent Ecosystem — Pydantic schemas для API."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel


class AgentDefinitionRead(BaseModel):
    id: str
    agent_id: str
    name: str
    description: str | None
    specialization: str
    allowed_tools: list[str] | None
    task_types: list[str] | None
    autonomy_level: str
    confidence_threshold: float
    model_profile: dict[str, Any] | None
    active: bool
    version: str
    created_at: datetime

    model_config = {"from_attributes": True, "protected_namespaces": ()}


class AgentInvocationRead(BaseModel):
    id: str
    agent_id: str
    task_type: str | None
    session_id: str | None
    run_id: str | None
    status: str
    confidence: float | None
    duration_ms: int
    error: str | None
    created_at: datetime

    model_config = {"from_attributes": True}
