"""
Tool Ecosystem — SQLAlchemy модели.

ToolDefinition — регистрация инструмента в системе.
ToolInvocation — лог каждого вызова инструмента.
"""

from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
)

from src.models.database import Base, generate_uuid


class ToolDefinition(Base):
    """Определение инструмента в registry."""

    __tablename__ = "tool_definitions"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    tool_id = Column(String(100), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    tool_type = Column(String(20), nullable=False, default="internal")  # internal | external

    # Schemas
    input_schema = Column(JSON, nullable=True)
    output_schema = Column(JSON, nullable=True)

    # Security & Policy
    permissions = Column(JSON, nullable=True)    # ["contract.read", "analysis.execute"]
    policy_tags = Column(JSON, nullable=True)    # ["analysis", "risk"]
    risk_level = Column(String(20), nullable=False, default="low")  # low|medium|high|critical
    sync_mode = Column(String(10), nullable=False, default="sync")  # sync|async

    # Metadata
    active = Column(Boolean, default=True, index=True)
    version = Column(String(20), default="1.0.0")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        CheckConstraint(risk_level.in_(["low", "medium", "high", "critical"]), name="check_tool_risk_level"),
        CheckConstraint(sync_mode.in_(["sync", "async"]), name="check_tool_sync_mode"),
        CheckConstraint(tool_type.in_(["internal", "external"]), name="check_tool_type"),
    )

    def __repr__(self) -> str:
        return f"<ToolDefinition(tool_id={self.tool_id}, name={self.name}, risk={self.risk_level})>"


class ToolInvocation(Base):
    """Лог вызова инструмента."""

    __tablename__ = "tool_invocations"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    tool_id = Column(String(100), nullable=False, index=True)
    invoked_by = Column(String(100), nullable=False)  # user:<id> | agent:<id> | orchestrator
    session_id = Column(String(36), nullable=True, index=True)
    run_id = Column(String(36), nullable=True, index=True)
    correlation_id = Column(String(36), nullable=True, index=True)

    # Input/Output
    input_data = Column(JSON, nullable=True)
    output_data = Column(JSON, nullable=True)

    # Result
    status = Column(String(20), nullable=False, default="pending")  # pending|running|completed|failed|blocked
    error = Column(Text, nullable=True)
    duration_ms = Column(Integer, default=0)

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)

    __table_args__ = (
        CheckConstraint(
            status.in_(["pending", "running", "completed", "failed", "blocked"]),
            name="check_tool_invocation_status",
        ),
        Index("idx_tool_inv_tool_status", "tool_id", "status"),
        Index("idx_tool_inv_created", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<ToolInvocation(id={self.id}, tool={self.tool_id}, status={self.status})>"
