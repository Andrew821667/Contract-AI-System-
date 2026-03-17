"""
Negotiation & Version Intelligence — Pydantic v2 schemas.

Схемы запросов и ответов для сервисов переговоров и версионного анализа.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


# ──────────────────────────────────────────────
# Negotiation
# ──────────────────────────────────────────────


class NegotiationStartRequest(BaseModel):
    """Запрос на запуск процесса переговоров."""
    document_id: str
    analysis_id: str | None = None
    goal: str
    auto_prioritize: bool = True


class NegotiationStartResponse(BaseModel):
    """Результат запуска переговоров."""
    negotiation_id: str
    status: str
    objections_count: int
    by_priority: dict[str, int] = Field(default_factory=dict)


class ObjectionGenerateRequest(BaseModel):
    """Запрос на генерацию возражений."""
    negotiation_id: str
    risk_ids: list[str] | None = None
    custom_instructions: str | None = None


class ObjectionResponse(BaseModel):
    """Сгенерированное возражение."""
    objection_id: str
    issue_description: str
    legal_basis: str
    risk_explanation: str
    alternative_formulation: str
    alternative_reasoning: str
    priority: str
    auto_priority: int
    confidence: float


class ObjectionSelectionRequest(BaseModel):
    """Запрос на выбор возражений для включения в протокол."""
    negotiation_id: str
    selected_objection_ids: list[str]
    priority_order: list[str] | None = None


class ObjectionSelectionResponse(BaseModel):
    """Результат выбора возражений."""
    status: str
    selected_count: int


# ──────────────────────────────────────────────
# Negotiation Position
# ──────────────────────────────────────────────


class NegotiationPositionRequest(BaseModel):
    """Запрос на подготовку переговорной позиции."""
    negotiation_id: str
    strategy: str = "balanced"
    focus_areas: list[str] | None = None


class NegotiationPositionResponse(BaseModel):
    """Подготовленная переговорная позиция."""
    position_text: str
    key_arguments: list[str] = Field(default_factory=list)
    concession_candidates: list[str] = Field(default_factory=list)
    red_lines: list[str] = Field(default_factory=list)


# ──────────────────────────────────────────────
# Version Intelligence
# ──────────────────────────────────────────────


class VersionCompareRequest(BaseModel):
    """Запрос на сравнение версий документа."""
    document_id: str
    from_version_id: str
    to_version_id: str
    deep_analysis: bool = True


class MaterialChangeResponse(BaseModel):
    """Существенное изменение между версиями."""
    change_id: str
    change_type: str
    change_category: str
    section_name: str | None = None
    clause_number: str | None = None
    old_content: str | None = None
    new_content: str | None = None
    semantic_description: str | None = None
    impact_direction: str | None = None
    severity: str | None = None
    recommendation: str | None = None
    requires_review: bool = False


class VersionCompareResponse(BaseModel):
    """Результат сравнения версий."""
    comparison_id: str
    total_changes: int
    by_type: dict[str, int] = Field(default_factory=dict)
    by_category: dict[str, int] = Field(default_factory=dict)
    overall_assessment: str
    material_changes: list[MaterialChangeResponse] = Field(default_factory=list)
    executive_summary: str
