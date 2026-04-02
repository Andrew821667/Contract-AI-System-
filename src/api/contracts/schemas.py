# -*- coding: utf-8 -*-
"""
Pydantic schemas for Contract Operations API
"""
from typing import List, Optional, Dict, Any

from pydantic import BaseModel, Field


class ContractUploadResponse(BaseModel):
    contract_id: str
    file_name: str
    file_size: int
    status: str
    message: str


class AnalysisResultRequest(BaseModel):
    contract_id: str
    check_counterparty: bool = True
    counterparty_tin: Optional[str] = None
    analysis_perspective: Optional[str] = None


class AnalysisResultResponse(BaseModel):
    analysis_id: str
    contract_id: str
    status: str
    risks_count: int
    recommendations_count: int
    message: str


class ContractGenerateRequest(BaseModel):
    contract_type: str = Field(..., description="Type of contract (supply, service, lease, etc.)")
    template_id: Optional[str] = None
    params: Dict[str, Any] = Field(..., description="Contract parameters")


class ContractGenerateResponse(BaseModel):
    contract_id: str
    status: str
    message: str


class ContractTypeOption(BaseModel):
    code: str
    name: str
    source: str
    has_template: bool = False


class DisagreementGenerateRequest(BaseModel):
    contract_id: str
    analysis_id: str
    auto_prioritize: bool = True


class ExportRequest(BaseModel):
    contract_id: str
    export_format: str = Field(..., description="Format: docx, pdf, txt, json, xml, all")
    include_analysis: bool = False


class ContractListResponse(BaseModel):
    contracts: List[Dict[str, Any]]
    total: int
    page: int
    page_size: int
    next_cursor: Optional[str] = None  # Keyset cursor for efficient deep pagination


class ContractVersionResponse(BaseModel):
    id: int
    contract_id: str
    version_number: int
    file_hash: Optional[str] = None
    source: str
    description: Optional[str] = None
    is_current: bool
    uploaded_at: Optional[str] = None


class CompareRequest(BaseModel):
    from_version_id: int
    to_version_id: int


class CompareChangeItem(BaseModel):
    change_type: str
    change_category: str
    section_name: Optional[str] = None
    clause_number: Optional[str] = None
    old_content: Optional[str] = None
    new_content: Optional[str] = None
    xpath_location: Optional[str] = None


class CompareResultResponse(BaseModel):
    total_changes: int
    by_type: Dict[str, int]
    by_category: Dict[str, int]
    overall_assessment: Optional[str] = None
    changes: List[CompareChangeItem]
    executive_summary: Optional[str] = None


class BatchAnalysisRequest(BaseModel):
    contract_ids: List[str] = Field(..., description="List of contract IDs to analyze", min_length=1, max_length=20)
    check_counterparty: bool = True


class BatchAnalysisResponse(BaseModel):
    task_id: str
    total: int
    status: str
    message: str
