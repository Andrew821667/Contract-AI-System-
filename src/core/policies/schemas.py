"""Policy Engine — Pydantic schemas для API."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class PolicyCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = Field(None, max_length=2000)
    level: str = Field(..., max_length=50)  # platform|tenant|organization|branch|document|user
    scope_id: str | None = Field(None, max_length=50)
    policy_type: str = Field(..., max_length=50)  # ai_autonomy|tool_access|action_approval|data_sensitivity|llm_routing
    rules: dict[str, Any]
    priority: int = 0


class PolicyRead(BaseModel):
    id: str
    name: str
    description: str | None
    level: str
    scope_id: str | None
    policy_type: str
    rules: dict[str, Any]
    priority: int
    active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class ApprovalRuleCreate(BaseModel):
    policy_id: str = Field(..., max_length=50)
    action_pattern: str = Field(..., min_length=1, max_length=255)
    required_approvers: int = 1
    escalation_timeout: int = 0
    escalation_target: str | None = Field(None, max_length=255)


class ApprovalRuleRead(BaseModel):
    id: str
    policy_id: str
    action_pattern: str
    required_approvers: int
    escalation_timeout: int
    escalation_target: str | None
    active: bool
    created_at: datetime

    model_config = {"from_attributes": True}
