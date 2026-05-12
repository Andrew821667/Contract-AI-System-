# -*- coding: utf-8 -*-
"""
Связи договоров: m2m с контрагентами и parent↔child для производных документов.

Таблицы:
- contract_parties — стороны договора (контрагент + роль).
- contract_relations — связь основного договора с производным
  (доп.соглашение, спецификация, приложение, акт, расторжение, custom).
- derivative_generation_history — история промптов LLM для регенерации
  custom-производных документов.

Источник истины для типа связи — ContractRelation.relation_type.
Contract.primary_relation_type — денормализованная копия для быстрой
фильтрации в листинге; синхронизация обеспечивается на API-слое.
"""
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from .database import Base, generate_uuid


PARTY_ROLES = ["counterparty", "guarantor", "third_party", "other"]

RELATION_TYPES = [
    "supplementary_agreement",  # доп. соглашение — изменяет/дополняет основной
    "specification",            # спецификация — расширение под отдельный продукт/партию
    "annex",                    # приложение
    "act",                      # акт (выполненных работ, приёма-передачи и т.п.)
    "addendum",                 # дополнение
    "termination",              # соглашение о расторжении
    "custom",                   # пользовательский тип со свободным промптом
]

GENERATION_STATUSES = ["completed", "failed", "in_progress"]

VERIFICATION_ASSESSMENTS = ["ok", "warnings", "critical", "error"]
VERIFICATION_STATUSES = ["completed", "partial", "failed", "in_progress"]


class ContractParty(Base):
    """Сторона договора: ссылка на контрагента и его роль."""

    __tablename__ = "contract_parties"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    contract_id = Column(
        String(36),
        ForeignKey("contracts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    counterparty_id = Column(
        String(36),
        ForeignKey("counterparties.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    role = Column(String(30), nullable=False, default="counterparty", index=True)
    sequence_number = Column(Integer, nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(
        DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )

    # Relationships
    contract = relationship("Contract", foreign_keys=[contract_id], back_populates="parties")
    counterparty = relationship("Counterparty", foreign_keys=[counterparty_id])

    __table_args__ = (
        UniqueConstraint(
            "contract_id", "counterparty_id", "role", name="uq_contract_party_role"
        ),
        CheckConstraint(
            f"role IN ({', '.join(repr(r) for r in PARTY_ROLES)})",
            name="check_contract_party_role",
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<ContractParty(contract={self.contract_id[:8]}, "
            f"cp={self.counterparty_id[:8]}, role={self.role})>"
        )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "contract_id": self.contract_id,
            "counterparty_id": self.counterparty_id,
            "role": self.role,
            "sequence_number": self.sequence_number,
            "notes": self.notes,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class ContractRelation(Base):
    """Связь parent↔child: один основной договор — много производных документов.

    Поддерживается множественность parent у одного child (например, акт
    выполнения работ может относиться сразу к нескольким договорам поставки).
    """

    __tablename__ = "contract_relations"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    parent_contract_id = Column(
        String(36),
        ForeignKey("contracts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    child_contract_id = Column(
        String(36),
        ForeignKey("contracts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    relation_type = Column(String(50), nullable=False, index=True)
    custom_label = Column(String(200), nullable=True)
    custom_prompt = Column(Text, nullable=True)

    derived_from_text = Column(Text, nullable=True)
    confidence = Column(Float, nullable=True)
    auto_detected = Column(Boolean, nullable=False, default=False)

    created_by = Column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at = Column(
        DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    parent_contract = relationship(
        "Contract",
        foreign_keys=[parent_contract_id],
        back_populates="derivative_relations",
    )
    child_contract = relationship(
        "Contract",
        foreign_keys=[child_contract_id],
        back_populates="parent_relations",
    )
    creator = relationship("User", foreign_keys=[created_by])

    __table_args__ = (
        UniqueConstraint(
            "parent_contract_id",
            "child_contract_id",
            "relation_type",
            name="uq_contract_relation",
        ),
        CheckConstraint(
            f"relation_type IN ({', '.join(repr(t) for t in RELATION_TYPES)})",
            name="check_contract_relation_type",
        ),
        CheckConstraint(
            "parent_contract_id != child_contract_id",
            name="check_no_self_reference",
        ),
        CheckConstraint(
            "confidence IS NULL OR (confidence >= 0.0 AND confidence <= 1.0)",
            name="check_relation_confidence",
        ),
        Index(
            "idx_contract_relations_parent_type",
            "parent_contract_id",
            "relation_type",
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<ContractRelation(parent={self.parent_contract_id[:8]}, "
            f"child={self.child_contract_id[:8]}, type={self.relation_type})>"
        )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "parent_contract_id": self.parent_contract_id,
            "child_contract_id": self.child_contract_id,
            "relation_type": self.relation_type,
            "custom_label": self.custom_label,
            "custom_prompt": self.custom_prompt,
            "derived_from_text": self.derived_from_text,
            "confidence": self.confidence,
            "auto_detected": self.auto_detected,
            "created_by": self.created_by,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class DerivativeGenerationHistory(Base):
    """История генерации производных документов: позволяет регенерировать
    по тому же промпту или сравнить версии."""

    __tablename__ = "derivative_generation_history"

    id = Column(String(36), primary_key=True, default=generate_uuid)

    relation_id = Column(
        String(36),
        ForeignKey("contract_relations.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    parent_contract_id = Column(
        String(36),
        ForeignKey("contracts.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    child_contract_id = Column(
        String(36),
        ForeignKey("contracts.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    relation_type = Column(String(50), nullable=False)
    custom_label = Column(String(200), nullable=True)
    prompt = Column(Text, nullable=False)
    parent_snapshot = Column(JSON, nullable=True)
    llm_model = Column(String(100), nullable=True)
    llm_metadata = Column(JSON, nullable=True)

    status = Column(String(30), nullable=False, default="completed")
    error = Column(Text, nullable=True)

    created_by = Column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at = Column(
        DateTime, default=lambda: datetime.now(timezone.utc), nullable=False, index=True
    )

    relation = relationship("ContractRelation", foreign_keys=[relation_id])
    parent_contract = relationship("Contract", foreign_keys=[parent_contract_id])
    child_contract = relationship("Contract", foreign_keys=[child_contract_id])
    creator = relationship("User", foreign_keys=[created_by])

    __table_args__ = (
        CheckConstraint(
            f"status IN ({', '.join(repr(s) for s in GENERATION_STATUSES)})",
            name="check_gen_history_status",
        ),
    )

    def __repr__(self) -> str:
        return f"<DerivativeGenerationHistory(id={self.id[:8]}, type={self.relation_type}, status={self.status})>"

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "relation_id": self.relation_id,
            "parent_contract_id": self.parent_contract_id,
            "child_contract_id": self.child_contract_id,
            "relation_type": self.relation_type,
            "custom_label": self.custom_label,
            "prompt": self.prompt,
            "parent_snapshot": self.parent_snapshot,
            "llm_model": self.llm_model,
            "llm_metadata": self.llm_metadata,
            "status": self.status,
            "error": self.error,
            "created_by": self.created_by,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class DerivativeVerification(Base):
    """Отчёт о сверке производного документа с основным."""

    __tablename__ = "derivative_verifications"

    id = Column(String(36), primary_key=True, default=generate_uuid)

    relation_id = Column(
        String(36),
        ForeignKey("contract_relations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    parent_contract_id = Column(
        String(36),
        ForeignKey("contracts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    child_contract_id = Column(
        String(36),
        ForeignKey("contracts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    overall_assessment = Column(String(20), nullable=False)
    requisites = Column(JSON, nullable=True)
    contradictions = Column(JSON, nullable=True)
    diff = Column(JSON, nullable=True)
    llm_model = Column(String(100), nullable=True)
    duration_ms = Column(Integer, nullable=True)
    status = Column(String(20), nullable=False, default="completed")
    error = Column(Text, nullable=True)

    created_by = Column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at = Column(
        DateTime, default=lambda: datetime.now(timezone.utc), nullable=False, index=True
    )

    relation = relationship("ContractRelation", foreign_keys=[relation_id])
    parent_contract = relationship("Contract", foreign_keys=[parent_contract_id])
    child_contract = relationship("Contract", foreign_keys=[child_contract_id])
    creator = relationship("User", foreign_keys=[created_by])

    __table_args__ = (
        CheckConstraint(
            f"overall_assessment IN ({', '.join(repr(s) for s in VERIFICATION_ASSESSMENTS)})",
            name="check_dv_overall_assessment",
        ),
        CheckConstraint(
            f"status IN ({', '.join(repr(s) for s in VERIFICATION_STATUSES)})",
            name="check_dv_status",
        ),
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "relation_id": self.relation_id,
            "parent_contract_id": self.parent_contract_id,
            "child_contract_id": self.child_contract_id,
            "overall_assessment": self.overall_assessment,
            "requisites": self.requisites,
            "contradictions": self.contradictions,
            "diff": self.diff,
            "llm_model": self.llm_model,
            "duration_ms": self.duration_ms,
            "status": self.status,
            "error": self.error,
            "created_by": self.created_by,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


__all__ = [
    "ContractParty",
    "ContractRelation",
    "DerivativeGenerationHistory",
    "DerivativeVerification",
    "PARTY_ROLES",
    "RELATION_TYPES",
    "GENERATION_STATUSES",
    "VERIFICATION_ASSESSMENTS",
    "VERIFICATION_STATUSES",
]
