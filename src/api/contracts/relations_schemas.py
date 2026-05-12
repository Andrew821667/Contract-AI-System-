# -*- coding: utf-8 -*-
"""Schemas for contract parties and parent↔child relations."""
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# ── Parties ────────────────────────────────────────────────────────────────


class ContractPartyCreate(BaseModel):
    counterparty_id: str
    role: str = Field(default="counterparty")
    sequence_number: Optional[int] = None
    notes: Optional[str] = None


class ContractPartyUpdate(BaseModel):
    role: Optional[str] = None
    sequence_number: Optional[int] = None
    notes: Optional[str] = None


class ContractPartyResponse(BaseModel):
    id: str
    contract_id: str
    counterparty_id: str
    counterparty_name: Optional[str] = None
    counterparty_inn: Optional[str] = None
    role: str
    sequence_number: Optional[int] = None
    notes: Optional[str] = None
    created_at: Optional[str] = None

    model_config = {"from_attributes": True}


class ContractPartiesResponse(BaseModel):
    contract_id: str
    parties: List[ContractPartyResponse]


# ── Relations (parent ↔ child) ─────────────────────────────────────────────


class ContractRelationCreate(BaseModel):
    parent_contract_id: str = Field(..., description="ID основного договора")
    relation_type: str = Field(
        ..., description="supplementary_agreement | specification | annex | act | addendum | termination | custom"
    )
    custom_label: Optional[str] = Field(None, max_length=200, description="Метка для custom-типа")
    custom_prompt: Optional[str] = Field(None, description="Промпт пользователя для custom-типа")
    derived_from_text: Optional[str] = None
    confidence: Optional[float] = Field(None, ge=0.0, le=1.0)
    auto_detected: bool = False


class ContractRelationUpdate(BaseModel):
    relation_type: Optional[str] = None
    custom_label: Optional[str] = Field(None, max_length=200)
    custom_prompt: Optional[str] = None


class ContractBriefRef(BaseModel):
    """Краткий снимок договора для отображения в списке связей."""

    id: str
    file_name: str
    document_type: str
    contract_type: Optional[str] = None
    contract_number: Optional[str] = None
    contract_date: Optional[str] = None
    status: str
    primary_relation_type: Optional[str] = None
    parties_summary: Optional[List[Dict[str, Any]]] = None


class ContractRelationResponse(BaseModel):
    id: str
    parent_contract_id: str
    child_contract_id: str
    relation_type: str
    custom_label: Optional[str] = None
    custom_prompt: Optional[str] = None
    derived_from_text: Optional[str] = None
    confidence: Optional[float] = None
    auto_detected: bool
    created_by: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    parent: Optional[ContractBriefRef] = None
    child: Optional[ContractBriefRef] = None

    model_config = {"from_attributes": True}


class ContractRelationsListResponse(BaseModel):
    contract_id: str
    parents: List[ContractRelationResponse] = Field(default_factory=list)
    derivatives: List[ContractRelationResponse] = Field(default_factory=list)


class ContractRelatedBundle(BaseModel):
    """Combined вид: основные, производные и стороны."""

    contract_id: str
    parents: List[ContractRelationResponse] = Field(default_factory=list)
    derivatives: List[ContractRelationResponse] = Field(default_factory=list)
    parties: List[ContractPartyResponse] = Field(default_factory=list)


class RelationTypeOption(BaseModel):
    value: str
    label: str
    description: Optional[str] = None
