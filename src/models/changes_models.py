# -*- coding: utf-8 -*-
"""
SQLAlchemy Models for Changes Analyzer
Models for contract versioning, change tracking, and analysis
"""
from datetime import datetime
from sqlalchemy import (
    Boolean, Column, String, Text, Integer, Float,
    DateTime, ForeignKey, CheckConstraint, JSON, UniqueConstraint
)
from sqlalchemy.orm import relationship

from .database import Base


class ContractVersion(Base):
    """Model for contract versions"""
    __tablename__ = "contract_versions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    contract_id = Column(String(36), ForeignKey('contracts.id', ondelete='CASCADE'), nullable=False, index=True)
    version_number = Column(Integer, nullable=False)
    file_path = Column(Text, nullable=False)
    file_hash = Column(String(64))  # SHA256
    uploaded_by = Column(String(36), ForeignKey('users.id'))
    uploaded_at = Column(DateTime, default=datetime.utcnow)
    source = Column(String(50), default='unknown')
    description = Column(Text)
    parent_version_id = Column(Integer, ForeignKey('contract_versions.id'))
    is_current = Column(Boolean, default=True, index=True)
    version_metadata = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    contract = relationship("Contract", foreign_keys=[contract_id])
    uploader = relationship("User", foreign_keys=[uploaded_by])
    parent_version = relationship("ContractVersion", remote_side=[id], foreign_keys=[parent_version_id])

    # Changes from this version
    changes_from = relationship("ContractChange", foreign_keys="ContractChange.from_version_id", back_populates="from_version")
    # Changes to this version
    changes_to = relationship("ContractChange", foreign_keys="ContractChange.to_version_id", back_populates="to_version")

    # Analysis results
    analysis_from = relationship("ChangeAnalysisResult", foreign_keys="ChangeAnalysisResult.from_version_id", back_populates="from_version")
    analysis_to = relationship("ChangeAnalysisResult", foreign_keys="ChangeAnalysisResult.to_version_id", back_populates="to_version")

    __table_args__ = (
        UniqueConstraint('contract_id', 'version_number', name='uq_contract_version'),
        CheckConstraint(
            "version_number > 0",
            name='check_version_number'
        ),
        CheckConstraint(
            "source IN ('initial', 'counterparty_response', 'internal_revision', 'final', 'unknown')",
            name='check_source'
        ),
    )

    def __repr__(self):
        return f"<ContractVersion(id={self.id}, contract_id={self.contract_id}, version={self.version_number})>"


class ContractChange(Base):
    """Model for individual changes between versions"""
    __tablename__ = "contract_changes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    from_version_id = Column(Integer, ForeignKey('contract_versions.id', ondelete='CASCADE'), nullable=False, index=True)
    to_version_id = Column(Integer, ForeignKey('contract_versions.id', ondelete='CASCADE'), nullable=False, index=True)

    # Classification
    change_type = Column(String(50), nullable=False, index=True)
    change_category = Column(String(50), nullable=False, index=True)

    # Location
    xpath_location = Column(Text)
    section_name = Column(String(255))
    clause_number = Column(String(50))

    # Content
    old_content = Column(Text)
    new_content = Column(Text)

    # Semantic analysis
    semantic_description = Column(Text)
    is_substantive = Column(Boolean, default=True)
    legal_implications = Column(Text)

    # Impact assessment (JSON)
    impact_assessment = Column(JSON, default=dict)

    # Link to disagreements
    related_disagreement_objection_id = Column(Integer, ForeignKey('disagreement_objections.id'))
    objection_status = Column(String(20))

    # Review workflow
    requires_lawyer_review = Column(Boolean, default=False, index=True)
    reviewed_by = Column(String(36), ForeignKey('users.id'))
    reviewed_at = Column(DateTime)
    lawyer_decision = Column(String(20))
    lawyer_comments = Column(Text)

    # Metadata
    detected_by = Column(String(50), default='ChangesAnalyzerAgent')
    confidence_score = Column(Float)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    # Relationships
    from_version = relationship("ContractVersion", foreign_keys=[from_version_id], back_populates="changes_from")
    to_version = relationship("ContractVersion", foreign_keys=[to_version_id], back_populates="changes_to")
    related_objection = relationship("DisagreementObjection", foreign_keys=[related_disagreement_objection_id])
    reviewer = relationship("User", foreign_keys=[reviewed_by])
    feedbacks = relationship("ChangeReviewFeedback", back_populates="change", cascade="all, delete-orphan")

    __table_args__ = (
        CheckConstraint(
            "change_type IN ('addition', 'deletion', 'modification', 'relocation')",
            name='check_change_type'
        ),
        CheckConstraint(
            "change_category IN ('textual', 'structural', 'semantic', 'legal')",
            name='check_change_category'
        ),
        CheckConstraint(
            "objection_status IN ('accepted', 'rejected', 'partial', 'unrelated') OR objection_status IS NULL",
            name='check_objection_status'
        ),
        CheckConstraint(
            "lawyer_decision IN ('approve', 'reject', 'negotiate') OR lawyer_decision IS NULL",
            name='check_lawyer_decision'
        ),
        CheckConstraint(
            "confidence_score IS NULL OR (confidence_score >= 0.0 AND confidence_score <= 1.0)",
            name='check_confidence_score'
        ),
    )

    def __repr__(self):
        return f"<ContractChange(id={self.id}, type={self.change_type}, from_v={self.from_version_id}, to_v={self.to_version_id})>"


class ChangeAnalysisResult(Base):
    """Model for change analysis summary"""
    __tablename__ = "change_analysis_results"

    id = Column(Integer, primary_key=True, autoincrement=True)
    from_version_id = Column(Integer, ForeignKey('contract_versions.id', ondelete='CASCADE'), nullable=False, index=True)
    to_version_id = Column(Integer, ForeignKey('contract_versions.id', ondelete='CASCADE'), nullable=False, index=True)

    # Statistics
    total_changes = Column(Integer, default=0)
    by_type = Column(JSON, default=dict)
    by_category = Column(JSON, default=dict)
    by_impact = Column(JSON, default=dict)

    # Overall assessment
    overall_assessment = Column(String(20), index=True)
    overall_risk_change = Column(String(20))

    # Critical changes
    critical_changes = Column(JSON, default=list)

    # Disagreement tracking
    accepted_objections = Column(Integer, default=0)
    rejected_objections = Column(Integer, default=0)
    partial_objections = Column(Integer, default=0)

    # LLM recommendations
    recommendations = Column(Text)
    executive_summary = Column(Text)

    # Report
    report_pdf_path = Column(Text)
    report_generated_at = Column(DateTime)

    # Metadata
    analyzed_at = Column(DateTime, default=datetime.utcnow, index=True)
    analyzed_by = Column(String(50), default='ChangesAnalyzerAgent')
    analysis_duration_ms = Column(Integer)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    from_version = relationship("ContractVersion", foreign_keys=[from_version_id], back_populates="analysis_from")
    to_version = relationship("ContractVersion", foreign_keys=[to_version_id], back_populates="analysis_to")

    __table_args__ = (
        UniqueConstraint('from_version_id', 'to_version_id', name='uq_change_analysis'),
        CheckConstraint(
            "overall_assessment IN ('favorable', 'unfavorable', 'mixed', 'neutral') OR overall_assessment IS NULL",
            name='check_overall_assessment'
        ),
        CheckConstraint(
            "overall_risk_change IN ('increased', 'decreased', 'unchanged') OR overall_risk_change IS NULL",
            name='check_overall_risk_change'
        ),
    )

    def __repr__(self):
        return f"<ChangeAnalysisResult(id={self.id}, assessment={self.overall_assessment}, changes={self.total_changes})>"


class ChangeReviewFeedback(Base):
    """Model for lawyer feedback on changes (ML training data)"""
    __tablename__ = "change_review_feedback"

    id = Column(Integer, primary_key=True, autoincrement=True)
    change_id = Column(Integer, ForeignKey('contract_changes.id', ondelete='CASCADE'), nullable=False, index=True)
    user_id = Column(String(36), ForeignKey('users.id'), nullable=False, index=True)

    # Decision
    decision = Column(String(20), nullable=False, index=True)
    reasoning = Column(Text)

    # Quality ratings (1-5)
    analysis_accuracy = Column(Integer)
    impact_assessment_quality = Column(Integer)
    recommendation_usefulness = Column(Integer)

    # Outcome
    what_happened = Column(String(20))
    outcome_notes = Column(Text)

    # ML training
    was_correct_recommendation = Column(Boolean)

    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    # Relationships
    change = relationship("ContractChange", back_populates="feedbacks")
    user = relationship("User", foreign_keys=[user_id])

    __table_args__ = (
        CheckConstraint(
            "decision IN ('approve', 'reject', 'negotiate')",
            name='check_decision'
        ),
        CheckConstraint(
            "analysis_accuracy IS NULL OR (analysis_accuracy >= 1 AND analysis_accuracy <= 5)",
            name='check_analysis_accuracy'
        ),
        CheckConstraint(
            "impact_assessment_quality IS NULL OR (impact_assessment_quality >= 1 AND impact_assessment_quality <= 5)",
            name='check_impact_quality'
        ),
        CheckConstraint(
            "recommendation_usefulness IS NULL OR (recommendation_usefulness >= 1 AND recommendation_usefulness <= 5)",
            name='check_recommendation_usefulness'
        ),
        CheckConstraint(
            "what_happened IN ('accepted_by_counterparty', 'rejected_by_counterparty', 'negotiated', 'pending') OR what_happened IS NULL",
            name='check_what_happened'
        ),
    )

    def __repr__(self):
        return f"<ChangeReviewFeedback(id={self.id}, change_id={self.change_id}, decision={self.decision})>"


__all__ = [
    "ContractVersion",
    "ContractChange",
    "ChangeAnalysisResult",
    "ChangeReviewFeedback"
]
