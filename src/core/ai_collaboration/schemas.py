"""AI Collaboration — Pydantic schemas для API."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class AISessionCreate(BaseModel):
    document_id: str = Field(..., max_length=50)
    stage: str = Field("intake", max_length=50)


class AISessionRead(BaseModel):
    id: str
    document_id: str
    user_id: str
    organization_id: str | None
    stage: str
    status: str
    total_turns: int
    total_actions: int
    total_tokens_used: int
    created_at: datetime
    closed_at: datetime | None

    model_config = {"from_attributes": True}


class AIMessageCreate(BaseModel):
    content: str = Field(..., min_length=1, max_length=10000)


class AIConversationTurnRead(BaseModel):
    id: str
    session_id: str
    role: str
    content: str
    model_used: str | None
    tokens_input: int
    tokens_output: int
    created_at: datetime

    model_config = {"from_attributes": True, "protected_namespaces": ()}


class AIActionRead(BaseModel):
    id: str
    session_id: str
    action_type: str
    target_entity_type: str | None
    target_entity_id: str | None
    payload: dict[str, Any] | None
    rationale: str | None
    confidence: float
    approval_required: bool
    execution_status: str
    created_at: datetime
    executed_at: datetime | None

    model_config = {"from_attributes": True}


class AIActionApprovalCreate(BaseModel):
    decision: Literal["approve", "reject", "edit_and_approve"] = Field(...)
    comment: str | None = Field(None, max_length=5000)
    edited_payload: dict[str, Any] | None = None
