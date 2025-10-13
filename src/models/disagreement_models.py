# -*- coding: utf-8 -*-
"""
SQLAlchemy Models for Disagreement Processor
Models for disagreements, objections, export logs, and feedback
"""
from datetime import datetime
from sqlalchemy import (
    Boolean, Column, String, Text, Integer, Float,
    DateTime, ForeignKey, CheckConstraint, JSON
)
from sqlalchemy.orm import relationship

from .database import Base


class Disagreement(Base):
    """Main disagreement document"""
    __tablename__ = "disagreements"

    id = Column(Integer, primary_key=True, autoincrement=True)
    contract_id = Column(String(36), ForeignKey('contracts.id', ondelete='CASCADE'), index=True)
    analysis_id = Column(String(36), ForeignKey('analysis_results.id', ondelete='CASCADE'), index=True)

    # Workflow status
    status = Column(String(20), default='draft', index=True)

    # Content
    generated_content = Column(JSON, default=dict)
    selected_objections = Column(JSON, default=list)
    priority_order = Column(JSON, default=list)

    # Export formats
    xml_content = Column(Text)
    docx_path = Column(String(500))
    pdf_path = Column(String(500))

    # Response tracking
    response_status = Column(String(20), index=True)
    response_notes = Column(Text)
    effectiveness_score = Column(Float)

    # Metadata
    tone = Column(String(20), default='neutral_business')
    created_by = Column(String(36), ForeignKey('users.id', ondelete='SET NULL'))
    reviewed_by = Column(String(36), ForeignKey('users.id', ondelete='SET NULL'))
    approved_by = Column(String(36), ForeignKey('users.id', ondelete='SET NULL'))

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    sent_at = Column(DateTime)
    responded_at = Column(DateTime)

    # Relationships
    contract = relationship("Contract")
    analysis = relationship("AnalysisResult")
    creator = relationship("User", foreign_keys=[created_by])
    reviewer = relationship("User", foreign_keys=[reviewed_by])
    approver = relationship("User", foreign_keys=[approved_by])
    objections = relationship("DisagreementObjection", back_populates="disagreement", cascade="all, delete-orphan")
    export_logs = relationship("DisagreementExportLog", back_populates="disagreement", cascade="all, delete-orphan")
    feedbacks = relationship("DisagreementFeedback", back_populates="disagreement", cascade="all, delete-orphan")

    __table_args__ = (
        CheckConstraint(
            "status IN ('draft', 'review', 'approved', 'sent', 'responded')",
            name='check_disagreement_status'
        ),
        CheckConstraint(
            "response_status IN ('pending', 'accepted', 'rejected', 'partial') OR response_status IS NULL",
            name='check_response_status'
        ),
        CheckConstraint(
            "effectiveness_score >= 0.0 AND effectiveness_score <= 1.0 OR effectiveness_score IS NULL",
            name='check_effectiveness_score'
        ),
    )

    def __repr__(self):
        return f"<Disagreement(id={self.id}, status={self.status}, objections={len(self.objections)})>"


class DisagreementObjection(Base):
    """Individual objection to contract clause"""
    __tablename__ = "disagreement_objections"

    id = Column(Integer, primary_key=True, autoincrement=True)
    disagreement_id = Column(Integer, ForeignKey('disagreements.id', ondelete='CASCADE'), index=True)

    # Contract linkage
    related_risk_ids = Column(JSON, default=list)
    contract_section_xpath = Column(Text)
    contract_section_text = Column(Text)

    # Objection structure
    issue_description = Column(Text, nullable=False)
    legal_basis = Column(Text)
    precedents = Column(JSON, default=list)
    risk_explanation = Column(Text)

    # Alternatives
    alternative_formulation = Column(Text)
    alternative_reasoning = Column(Text)
    alternative_variants = Column(JSON, default=list)

    # Prioritization
    priority = Column(String(20), default='medium', index=True)
    auto_priority = Column(Integer)
    user_priority = Column(Integer)

    # User selection
    user_selected = Column(Boolean, default=False, index=True)
    user_modified = Column(Boolean, default=False)
    original_content = Column(Text)

    # Response tracking
    counterparty_response = Column(String(20), index=True)
    effectiveness_feedback = Column(Text)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    disagreement = relationship("Disagreement", back_populates="objections")
    feedbacks = relationship("DisagreementFeedback", back_populates="objection", cascade="all, delete-orphan")

    __table_args__ = (
        CheckConstraint(
            "priority IN ('critical', 'high', 'medium', 'low')",
            name='check_objection_priority'
        ),
        CheckConstraint(
            "counterparty_response IN ('accepted', 'rejected', 'negotiated') OR counterparty_response IS NULL",
            name='check_counterparty_response'
        ),
    )

    def __repr__(self):
        return f"<DisagreementObjection(id={self.id}, priority={self.priority}, selected={self.user_selected})>"


class DisagreementExportLog(Base):
    """Export and delivery tracking"""
    __tablename__ = "disagreement_export_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    disagreement_id = Column(Integer, ForeignKey('disagreements.id', ondelete='CASCADE'), index=True)

    # Export details
    export_type = Column(String(50), nullable=False, index=True)
    export_format = Column(String(20))

    # File paths
    file_path = Column(String(500))
    file_size = Column(Integer)
    file_hash = Column(String(64))

    # Email details
    email_to = Column(String(255))
    email_subject = Column(String(500))
    email_sent_at = Column(DateTime)
    email_status = Column(String(20))

    # EDO details
    edo_system = Column(String(50))
    edo_document_id = Column(String(255))
    edo_status = Column(String(50))

    # Metadata
    exported_by = Column(String(36), ForeignKey('users.id', ondelete='SET NULL'))
    export_metadata = Column(JSON, default=dict)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    disagreement = relationship("Disagreement", back_populates="export_logs")
    exporter = relationship("User")

    __table_args__ = (
        CheckConstraint(
            "export_type IN ('docx', 'pdf', 'email', 'edo', 'api')",
            name='check_export_type'
        ),
    )

    def __repr__(self):
        return f"<DisagreementExportLog(id={self.id}, type={self.export_type})>"


class DisagreementFeedback(Base):
    """Feedback on disagreement quality"""
    __tablename__ = "disagreement_feedback"

    id = Column(Integer, primary_key=True, autoincrement=True)
    disagreement_id = Column(Integer, ForeignKey('disagreements.id', ondelete='CASCADE'), index=True)
    objection_id = Column(Integer, ForeignKey('disagreement_objections.id', ondelete='CASCADE'), index=True)
    user_id = Column(String(36), ForeignKey('users.id', ondelete='SET NULL'), index=True)

    # Overall feedback
    overall_quality = Column(Integer)
    usefulness_rating = Column(Integer)

    # Specific feedback
    tone_appropriateness = Column(Integer)
    legal_basis_quality = Column(Integer)
    alternative_quality = Column(Integer)

    # Outcome
    was_accepted = Column(Boolean)
    was_negotiated = Column(Boolean)
    led_to_contract_change = Column(Boolean)

    # Comments
    what_worked_well = Column(Text)
    what_needs_improvement = Column(Text)
    suggestions = Column(Text)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    disagreement = relationship("Disagreement", back_populates="feedbacks")
    objection = relationship("DisagreementObjection", back_populates="feedbacks")
    user = relationship("User")

    __table_args__ = (
        CheckConstraint(
            'overall_quality >= 1 AND overall_quality <= 5 OR overall_quality IS NULL',
            name='check_overall_quality'
        ),
        CheckConstraint(
            'usefulness_rating >= 1 AND usefulness_rating <= 5 OR usefulness_rating IS NULL',
            name='check_usefulness_rating'
        ),
        CheckConstraint(
            'tone_appropriateness >= 1 AND tone_appropriateness <= 5 OR tone_appropriateness IS NULL',
            name='check_tone_appropriateness'
        ),
        CheckConstraint(
            'legal_basis_quality >= 1 AND legal_basis_quality <= 5 OR legal_basis_quality IS NULL',
            name='check_legal_basis_quality'
        ),
        CheckConstraint(
            'alternative_quality >= 1 AND alternative_quality <= 5 OR alternative_quality IS NULL',
            name='check_alternative_quality'
        ),
    )

    def __repr__(self):
        return f"<DisagreementFeedback(id={self.id}, quality={self.overall_quality})>"


__all__ = [
    "Disagreement",
    "DisagreementObjection",
    "DisagreementExportLog",
    "DisagreementFeedback"
]
