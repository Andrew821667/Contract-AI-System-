"""
Agent Ecosystem — SQLAlchemy модели.

AgentDefinition — регистрация агента.
AgentInvocation — лог вызова агента.
AgentDelegation — делегация задачи от одного агента другому.
"""

from datetime import datetime

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
)

from src.models.database import Base, generate_uuid


class AgentDefinition(Base):
    """Определение агента в registry."""

    __tablename__ = "agent_definitions"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    agent_id = Column(String(100), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    specialization = Column(String(100), nullable=False)  # review, generation, negotiation, analysis, etc.

    # Capabilities
    allowed_tools = Column(JSON, nullable=True)   # ["document_parser", "risk_scorer", ...]
    task_types = Column(JSON, nullable=True)       # ["contract_review", "risk_assessment", ...]

    # Autonomy
    autonomy_level = Column(String(20), nullable=False, default="copilot")
    confidence_threshold = Column(Float, default=0.8)

    # LLM
    model_profile = Column(JSON, nullable=True)  # {"provider": "deepseek", "model": "deepseek-v3", ...}

    # Metadata
    active = Column(Boolean, default=True, index=True)
    version = Column(String(20), default="1.0.0")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        CheckConstraint(
            autonomy_level.in_(["advisor", "copilot", "processor", "autonomous"]),
            name="check_agent_autonomy_level",
        ),
        Index("idx_agent_def_spec", "specialization", "active"),
    )

    def __repr__(self) -> str:
        return f"<AgentDefinition(agent_id={self.agent_id}, spec={self.specialization})>"


class AgentInvocation(Base):
    """Лог вызова агента."""

    __tablename__ = "agent_invocations"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    agent_id = Column(String(100), nullable=False, index=True)
    task_type = Column(String(100), nullable=True, index=True)

    # Context
    session_id = Column(String(36), nullable=True, index=True)
    run_id = Column(String(36), nullable=True, index=True)
    correlation_id = Column(String(36), nullable=True, index=True)

    # Input/Output
    task_data = Column(JSON, nullable=True)
    context_data = Column(JSON, nullable=True)
    result_data = Column(JSON, nullable=True)
    tools_used = Column(JSON, nullable=True)

    # Result
    status = Column(String(20), nullable=False, default="pending")
    confidence = Column(Float, nullable=True)
    duration_ms = Column(Integer, default=0)
    error = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    __table_args__ = (
        CheckConstraint(
            status.in_(["pending", "running", "completed", "failed", "blocked"]),
            name="check_agent_invocation_status",
        ),
        Index("idx_agent_inv_agent_status", "agent_id", "status"),
    )

    def __repr__(self) -> str:
        return f"<AgentInvocation(id={self.id}, agent={self.agent_id}, status={self.status})>"


class AgentDelegation(Base):
    """Делегация задачи от одного агента другому."""

    __tablename__ = "agent_delegations"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    from_agent_id = Column(String(100), nullable=False, index=True)
    to_agent_id = Column(String(100), nullable=False, index=True)
    run_id = Column(String(36), nullable=True, index=True)

    task_data = Column(JSON, nullable=True)
    result_data = Column(JSON, nullable=True)
    status = Column(String(20), nullable=False, default="pending")

    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)

    __table_args__ = (
        CheckConstraint(
            status.in_(["pending", "running", "completed", "failed"]),
            name="check_delegation_status",
        ),
        Index("idx_delegation_run", "run_id", "status"),
    )

    def __repr__(self) -> str:
        return f"<AgentDelegation(from={self.from_agent_id}, to={self.to_agent_id}, status={self.status})>"
