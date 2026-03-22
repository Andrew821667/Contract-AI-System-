"""Template Governance — Pydantic schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class TemplateVersionRead(BaseModel):
    id: str
    template_id: str
    version: int
    content: dict[str, Any]
    variables: list[dict[str, Any]] | None
    validation_rules: dict[str, Any] | None
    status: str
    created_by: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class TemplateVersionCreate(BaseModel):
    template_id: str = Field(..., max_length=36)
    content: dict[str, Any]
    variables: list[dict[str, Any]] | None = None
    validation_rules: dict[str, Any] | None = None


class ClausePolicyRead(BaseModel):
    id: str
    org_id: str | None
    clause_type: str
    status: str
    alternative_clause_id: str | None
    risk_explanation: str | None
    created_at: datetime
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


class ClausePolicyCreate(BaseModel):
    org_id: str | None = None
    clause_type: str = Field(..., max_length=50)
    status: str = Field(..., pattern=r"^(approved|fallback|prohibited|risky)$")
    alternative_clause_id: str | None = None
    risk_explanation: str | None = None
