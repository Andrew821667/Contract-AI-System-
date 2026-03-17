# -*- coding: utf-8 -*-
"""
Negotiation — SQLAlchemy модели.

Negotiation — процесс переговоров по документу.
NegotiationObjection — сгенерированное возражение.
"""

from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from src.models.database import Base, generate_uuid


class Negotiation(Base):
    """Процесс переговоров по документу."""

    __tablename__ = "negotiations"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    document_id = Column(
        String(36),
        ForeignKey("contracts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id = Column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    analysis_id = Column(String(36), nullable=True)
    goal = Column(Text, nullable=False)
    status = Column(String(32), nullable=False, default="active")
    objections_count = Column(Integer, nullable=False, default=0)
    by_priority = Column(JSON, nullable=False, default=dict)
    position_text = Column(Text, nullable=True)
    position_metadata = Column(JSON, nullable=True)

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    objections = relationship(
        "NegotiationObjection",
        back_populates="negotiation",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        Index("ix_negotiations_document_user", "document_id", "user_id"),
    )


class NegotiationObjection(Base):
    """Сгенерированное возражение в рамках переговоров."""

    __tablename__ = "negotiation_objections"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    negotiation_id = Column(
        String(36),
        ForeignKey("negotiations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    issue_description = Column(Text, nullable=False)
    legal_basis = Column(Text, nullable=False, default="")
    risk_explanation = Column(Text, nullable=False, default="")
    alternative_formulation = Column(Text, nullable=False, default="")
    alternative_reasoning = Column(Text, nullable=False, default="")
    priority = Column(String(32), nullable=False, default="medium")
    auto_priority = Column(Integer, nullable=False, default=50)
    confidence = Column(Float, nullable=False, default=0.0)
    selected = Column(Boolean, nullable=False, default=False)
    selection_order = Column(Integer, nullable=True)
    risk_id = Column(String(36), nullable=True)

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    # Relationships
    negotiation = relationship("Negotiation", back_populates="objections")
