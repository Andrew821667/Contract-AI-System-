"""Template Governance — Pydantic schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel


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


class ClausePolicyRead(BaseModel):
    id: str
    org_id: str | None
    clause_type: str
    status: str
    alternative_clause_id: str | None
    risk_explanation: str | None
    created_at: datetime

    model_config = {"from_attributes": True}
