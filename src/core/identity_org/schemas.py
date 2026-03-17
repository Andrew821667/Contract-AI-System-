"""Identity & Organization — Pydantic schemas для API."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


# ── Organization ──

class OrganizationCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    slug: str = Field(..., min_length=1, max_length=100, pattern=r"^[a-z0-9\-]+$")
    description: str | None = Field(None, max_length=2000)
    settings: dict[str, Any] | None = None


class OrganizationRead(BaseModel):
    id: str
    name: str
    slug: str
    description: str | None
    settings: dict[str, Any] | None
    active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Membership ──

class OrganizationMembershipCreate(BaseModel):
    user_id: str = Field(..., max_length=50)
    org_id: str = Field(..., max_length=50)
    unit_id: str | None = Field(None, max_length=50)
    company_role: str | None = Field(None, max_length=100)
    functional_role: str = Field("member", max_length=50)


class OrganizationMembershipRead(BaseModel):
    id: str
    user_id: str
    org_id: str
    unit_id: str | None
    company_role: str | None
    functional_role: str
    active: bool
    joined_at: datetime

    model_config = {"from_attributes": True}


# ── Document Participation ──

class DocumentParticipationCreate(BaseModel):
    user_id: str = Field(..., max_length=50)
    document_id: str = Field(..., max_length=50)
    role: str = Field(..., max_length=50)  # owner | reviewer | approver | observer | negotiator | signer | ai_supervisor


class DocumentParticipationRead(BaseModel):
    id: str
    user_id: str
    document_id: str
    role: str
    assigned_at: datetime
    assigned_by: str | None

    model_config = {"from_attributes": True}


# ── Tenant Context ──

class TenantContextRead(BaseModel):
    id: str
    org_id: str
    mode: str
    parent_tenant_id: str | None
    config: dict[str, Any] | None
    created_at: datetime

    model_config = {"from_attributes": True}


# ── User Agent Policy Profile ──

class UserAgentPolicyProfileRead(BaseModel):
    id: str
    user_id: str
    org_id: str | None
    allowed_ai_modes: list[str] | None
    allowed_actions: list[str] | None
    allowed_agents: list[str] | None
    allowed_tools: list[str] | None
    approval_required_for: list[str] | None

    model_config = {"from_attributes": True}
