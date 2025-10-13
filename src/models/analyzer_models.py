# -*- coding: utf-8 -*-
"""
SQLAlchemy Models for Contract Analyzer
Models for risks, recommendations, annotations, suggested changes, and feedback
"""
from datetime import datetime
from sqlalchemy import (
    Boolean, Column, String, Text, Integer, Float,
    DateTime, ForeignKey, CheckConstraint, JSON
)
from sqlalchemy.orm import relationship

from .database import Base


class ContractRisk(Base):
    """Model for contract risks"""
    __tablename__ = "contract_risks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    contract_id = Column(String(36), ForeignKey('contracts.id', ondelete='CASCADE'), index=True)
    analysis_id = Column(String(36), ForeignKey('analysis_results.id', ondelete='CASCADE'), index=True)

    # Classification
    risk_type = Column(String(50), nullable=False, index=True)
    severity = Column(String(20), nullable=False, index=True)
    probability = Column(String(20))

    # Details
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=False)
    consequences = Column(Text)

    # Location
    xpath_location = Column(Text)
    section_name = Column(String(255))

    # RAG sources
    rag_sources = Column(JSON, default=list)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    contract = relationship("Contract")
    analysis = relationship("AnalysisResult")

    __table_args__ = (
        CheckConstraint(
            "risk_type IN ('financial', 'legal', 'operational', 'reputational')",
            name='check_risk_type'
        ),
        CheckConstraint(
            "severity IN ('critical', 'significant', 'minor')",
            name='check_severity'
        ),
        CheckConstraint(
            "probability IN ('high', 'medium', 'low') OR probability IS NULL",
            name='check_probability'
        ),
    )

    def __repr__(self):
        return f"<ContractRisk(id={self.id}, type={self.risk_type}, severity={self.severity})>"


class ContractRecommendation(Base):
    """Model for contract recommendations"""
    __tablename__ = "contract_recommendations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    contract_id = Column(String(36), ForeignKey('contracts.id', ondelete='CASCADE'), index=True)
    analysis_id = Column(String(36), ForeignKey('analysis_results.id', ondelete='CASCADE'), index=True)

    # Classification
    category = Column(String(100), nullable=False, index=True)
    priority = Column(String(20), nullable=False, index=True)

    # Details
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=False)
    reasoning = Column(Text)
    expected_benefit = Column(Text)

    # Related risk
    related_risk_id = Column(Integer, ForeignKey('contract_risks.id', ondelete='SET NULL'))

    # Implementation
    implementation_complexity = Column(String(20))

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    contract = relationship("Contract")
    analysis = relationship("AnalysisResult")
    related_risk = relationship("ContractRisk")

    __table_args__ = (
        CheckConstraint(
            "priority IN ('critical', 'high', 'medium', 'low')",
            name='check_priority'
        ),
        CheckConstraint(
            "implementation_complexity IN ('easy', 'medium', 'hard') OR implementation_complexity IS NULL",
            name='check_complexity'
        ),
    )

    def __repr__(self):
        return f"<ContractRecommendation(id={self.id}, priority={self.priority})>"


class ContractAnnotation(Base):
    """Model for contract annotations"""
    __tablename__ = "contract_annotations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    contract_id = Column(String(36), ForeignKey('contracts.id', ondelete='CASCADE'), index=True)
    analysis_id = Column(String(36), ForeignKey('analysis_results.id', ondelete='CASCADE'), index=True)

    # Location
    xpath_location = Column(Text, nullable=False)
    section_name = Column(String(255))

    # Annotation
    annotation_type = Column(String(50), nullable=False, index=True)
    content = Column(Text, nullable=False)

    # Related entities
    related_risk_id = Column(Integer, ForeignKey('contract_risks.id', ondelete='SET NULL'))
    related_recommendation_id = Column(Integer, ForeignKey('contract_recommendations.id', ondelete='SET NULL'))

    # Visual
    highlight_color = Column(String(20))

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    contract = relationship("Contract")
    analysis = relationship("AnalysisResult")
    related_risk = relationship("ContractRisk")
    related_recommendation = relationship("ContractRecommendation")

    __table_args__ = (
        CheckConstraint(
            "annotation_type IN ('risk', 'warning', 'info', 'suggestion')",
            name='check_annotation_type'
        ),
        CheckConstraint(
            "highlight_color IN ('red', 'yellow', 'green') OR highlight_color IS NULL",
            name='check_highlight_color'
        ),
    )

    def __repr__(self):
        return f"<ContractAnnotation(id={self.id}, type={self.annotation_type})>"


class ContractSuggestedChange(Base):
    """Model for suggested contract changes"""
    __tablename__ = "contract_suggested_changes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    contract_id = Column(String(36), ForeignKey('contracts.id', ondelete='CASCADE'), index=True)
    analysis_id = Column(String(36), ForeignKey('analysis_results.id', ondelete='CASCADE'), index=True)

    # Location
    xpath_location = Column(Text, nullable=False)
    section_name = Column(String(255))

    # Change details
    original_text = Column(Text, nullable=False)
    suggested_text = Column(Text, nullable=False)
    change_type = Column(String(50))

    # Reasoning
    issue = Column(Text, nullable=False)
    reasoning = Column(Text, nullable=False)
    legal_basis = Column(Text)

    # Related entities
    related_risk_id = Column(Integer, ForeignKey('contract_risks.id', ondelete='SET NULL'))
    related_recommendation_id = Column(Integer, ForeignKey('contract_recommendations.id', ondelete='SET NULL'))

    # Approval workflow
    status = Column(String(20), default='pending', index=True)
    approved_by = Column(String(36), ForeignKey('users.id', ondelete='SET NULL'))
    approved_at = Column(DateTime)
    rejection_reason = Column(Text)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    contract = relationship("Contract")
    analysis = relationship("AnalysisResult")
    related_risk = relationship("ContractRisk")
    related_recommendation = relationship("ContractRecommendation")
    approver = relationship("User")

    __table_args__ = (
        CheckConstraint(
            "change_type IN ('addition', 'modification', 'deletion', 'clarification') OR change_type IS NULL",
            name='check_change_type'
        ),
        CheckConstraint(
            "status IN ('pending', 'approved', 'rejected', 'modified')",
            name='check_status'
        ),
    )

    def __repr__(self):
        return f"<ContractSuggestedChange(id={self.id}, status={self.status})>"


class AnalysisFeedback(Base):
    """Model for analysis feedback"""
    __tablename__ = "analysis_feedback"

    id = Column(Integer, primary_key=True, autoincrement=True)
    analysis_id = Column(String(36), ForeignKey('analysis_results.id', ondelete='CASCADE'), index=True)
    contract_id = Column(String(36), ForeignKey('contracts.id', ondelete='CASCADE'), index=True)
    user_id = Column(String(36), ForeignKey('users.id', ondelete='SET NULL'), index=True)

    # Overall feedback
    overall_rating = Column(Integer)

    # Specific feedback (using JSON for SQLite compatibility)
    missed_risks = Column(JSON, default=list)
    false_positives = Column(JSON, default=list)

    # Quality assessment
    recommendations_quality = Column(Integer)
    suggested_changes_quality = Column(Integer)

    # Comments
    positive_aspects = Column(Text)
    areas_for_improvement = Column(Text)
    additional_comments = Column(Text)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    analysis = relationship("AnalysisResult")
    contract = relationship("Contract")
    user = relationship("User")

    __table_args__ = (
        CheckConstraint(
            'overall_rating >= 1 AND overall_rating <= 5 OR overall_rating IS NULL',
            name='check_overall_rating'
        ),
        CheckConstraint(
            'recommendations_quality >= 1 AND recommendations_quality <= 5 OR recommendations_quality IS NULL',
            name='check_recommendations_quality'
        ),
        CheckConstraint(
            'suggested_changes_quality >= 1 AND suggested_changes_quality <= 5 OR suggested_changes_quality IS NULL',
            name='check_suggested_changes_quality'
        ),
    )

    def __repr__(self):
        return f"<AnalysisFeedback(id={self.id}, rating={self.overall_rating})>"


__all__ = [
    "ContractRisk",
    "ContractRecommendation",
    "ContractAnnotation",
    "ContractSuggestedChange",
    "AnalysisFeedback"
]
