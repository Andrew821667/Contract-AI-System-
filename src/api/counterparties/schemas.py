# -*- coding: utf-8 -*-
"""Counterparties — Pydantic schemas."""
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, EmailStr, Field


class CounterpartyBase(BaseModel):
    type: str = Field(default="legal", description="legal | individual | individual_entrepreneur | foreign | other")
    name: str = Field(..., min_length=1, max_length=500)
    short_name: Optional[str] = Field(None, max_length=255)
    inn: Optional[str] = Field(None, max_length=20)
    kpp: Optional[str] = Field(None, max_length=20)
    ogrn: Optional[str] = Field(None, max_length=20)
    legal_address: Optional[str] = None
    postal_address: Optional[str] = None
    contact_person: Optional[str] = Field(None, max_length=255)
    contact_email: Optional[EmailStr] = None
    contact_phone: Optional[str] = Field(None, max_length=50)
    bank_details: Optional[Dict[str, Any]] = None
    notes: Optional[str] = None
    meta_info: Optional[Dict[str, Any]] = None


class CounterpartyCreate(CounterpartyBase):
    pass


class CounterpartyUpdate(BaseModel):
    type: Optional[str] = None
    status: Optional[str] = Field(None, description="active | archived")
    name: Optional[str] = Field(None, min_length=1, max_length=500)
    short_name: Optional[str] = Field(None, max_length=255)
    inn: Optional[str] = Field(None, max_length=20)
    kpp: Optional[str] = Field(None, max_length=20)
    ogrn: Optional[str] = Field(None, max_length=20)
    legal_address: Optional[str] = None
    postal_address: Optional[str] = None
    contact_person: Optional[str] = Field(None, max_length=255)
    contact_email: Optional[EmailStr] = None
    contact_phone: Optional[str] = Field(None, max_length=50)
    bank_details: Optional[Dict[str, Any]] = None
    notes: Optional[str] = None
    meta_info: Optional[Dict[str, Any]] = None


class CounterpartyResponse(BaseModel):
    id: str
    organization_id: Optional[str] = None
    created_by: Optional[str] = None
    type: str
    status: str
    name: str
    short_name: Optional[str] = None
    inn: Optional[str] = None
    kpp: Optional[str] = None
    ogrn: Optional[str] = None
    legal_address: Optional[str] = None
    postal_address: Optional[str] = None
    contact_person: Optional[str] = None
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None
    bank_details: Optional[Dict[str, Any]] = None
    fns_data: Optional[Dict[str, Any]] = None
    fns_checked_at: Optional[str] = None
    bankruptcy_data: Optional[Dict[str, Any]] = None
    bankruptcy_checked_at: Optional[str] = None
    notes: Optional[str] = None
    meta_info: Optional[Dict[str, Any]] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    contracts_count: Optional[int] = Field(
        default=None, description="Кол-во договоров с этим контрагентом (опционально)"
    )

    model_config = {"from_attributes": True}


class CounterpartyListResponse(BaseModel):
    counterparties: List[CounterpartyResponse]
    total: int
    page: int
    page_size: int


class CounterpartyLookupRequest(BaseModel):
    inn: str = Field(..., min_length=10, max_length=12)
    save: bool = Field(default=True, description="Сохранить контрагента в БД после lookup")
    check_bankruptcy: bool = Field(default=True)


class CounterpartyLookupResponse(BaseModel):
    counterparty: Optional[CounterpartyResponse] = None
    fns_data: Dict[str, Any]
    bankruptcy_data: Dict[str, Any]
    overall_status: str
    warnings: List[str] = Field(default_factory=list)
    errors: List[str] = Field(default_factory=list)
    saved: bool = False


class CounterpartyContractItem(BaseModel):
    id: str
    file_name: str
    contract_type: Optional[str] = None
    document_type: str
    status: str
    created_at: Optional[str] = None


class CounterpartyContractsResponse(BaseModel):
    counterparty_id: str
    total: int
    contracts: List[CounterpartyContractItem]
