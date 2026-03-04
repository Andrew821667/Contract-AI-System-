"""
Clause Library Models
Stores extracted clauses from contract analysis for the Clause Library feature.
"""
from datetime import datetime
from sqlalchemy import (
    Column, String, Text, Integer, Float,
    DateTime, ForeignKey, Index, UniqueConstraint
)
from sqlalchemy.orm import relationship

from .database import Base, generate_uuid


class ExtractedClause(Base):
    """Extracted clause from contract analysis"""
    __tablename__ = "extracted_clauses"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    contract_id = Column(
        String(36),
        ForeignKey('contracts.id', ondelete='CASCADE'),
        nullable=False
    )
    clause_number = Column(Integer, nullable=False)
    clause_type = Column(String(50), nullable=False)  # financial, temporal, liability, etc.
    title = Column(String(500), nullable=False)
    text = Column(Text, nullable=False)
    xpath_location = Column(Text, nullable=True)
    analysis_json = Column(Text, nullable=True)  # Full LLM analysis as JSON
    risk_level = Column(String(20), nullable=True)  # critical/high/medium/low/none
    severity_score = Column(Float, nullable=True)  # 0.0-1.0
    tags = Column(Text, nullable=True)  # JSON array of tags
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    contract = relationship("Contract", backref="extracted_clauses")

    __table_args__ = (
        Index('idx_clause_contract_id', 'contract_id'),
        Index('idx_clause_type', 'clause_type'),
        Index('idx_clause_risk_level', 'risk_level'),
        UniqueConstraint('contract_id', 'clause_number', name='uq_clause_contract_number'),
    )

    def __repr__(self):
        return f"<ExtractedClause(id={self.id}, type={self.clause_type}, risk={self.risk_level})>"
