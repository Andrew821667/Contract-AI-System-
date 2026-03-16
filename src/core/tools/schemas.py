"""Tool Ecosystem — Pydantic schemas для API."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel


class ToolDefinitionRead(BaseModel):
    id: str
    tool_id: str
    name: str
    description: str | None
    tool_type: str
    input_schema: dict[str, Any] | None
    output_schema: dict[str, Any] | None
    permissions: list[str] | None
    policy_tags: list[str] | None
    risk_level: str
    sync_mode: str
    active: bool
    version: str
    created_at: datetime

    model_config = {"from_attributes": True}


class ToolInvocationRead(BaseModel):
    id: str
    tool_id: str
    invoked_by: str
    session_id: str | None
    run_id: str | None
    correlation_id: str | None
    input_data: dict[str, Any] | None
    output_data: dict[str, Any] | None
    status: str
    error: str | None
    duration_ms: int
    created_at: datetime

    model_config = {"from_attributes": True}
