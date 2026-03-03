# -*- coding: utf-8 -*-
"""
SQLAlchemy Models for Digital Contract Verification
Hash-chain and DAG support for contract integrity tracking
"""
from datetime import datetime
from sqlalchemy import (
    Column, String, Text, Integer,
    DateTime, ForeignKey, UniqueConstraint, Index, CheckConstraint
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from .database import Base, generate_uuid


class DigitalContract(Base):
    """Digital contract version with SHA-256 hash-chain and HMAC signature"""
    __tablename__ = "digital_contracts"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    contract_id = Column(String(36), ForeignKey("contracts.id", ondelete="CASCADE"), nullable=False, index=True)
    version = Column(Integer, nullable=False, default=1)
    content_hash = Column(String(64), nullable=False)       # SHA-256 of file content
    signature = Column(String(128), nullable=False)          # HMAC-SHA256(content_hash, secret_key)
    parent_id = Column(String(36), ForeignKey("digital_contracts.id"), nullable=True)  # hash-chain link
    parent_ids = Column(Text, nullable=True)                 # JSON list for DAG (merge scenarios)
    status = Column(String(20), default="active")            # active / superseded / revoked
    metadata_json = Column(Text, nullable=True)              # Additional metadata (JSON)
    created_by = Column(String(36), ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=func.now())

    # Relationships
    contract = relationship("Contract", backref="digital_versions")
    parent = relationship("DigitalContract", remote_side=[id], foreign_keys=[parent_id])
    creator = relationship("User", foreign_keys=[created_by])

    __table_args__ = (
        UniqueConstraint("contract_id", "version", name="uq_digital_contract_version"),
        Index("idx_digital_content_hash", "content_hash"),
        Index("idx_digital_parent", "parent_id"),
        Index("idx_digital_status", "contract_id", "status"),
        CheckConstraint(
            "status IN ('active', 'superseded', 'revoked')",
            name="check_digital_status"
        ),
    )

    def __repr__(self):
        return f"<DigitalContract(id={self.id}, contract_id={self.contract_id}, v={self.version}, status={self.status})>"
