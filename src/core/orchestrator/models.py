"""
Orchestrator — SQLAlchemy модели.

OrchestratorRun — запуск оркестрации по цели.
ExecutionPlan — план выполнения (детерминированный).
PlanStep — шаг плана (tool_call, agent_delegation, approval_checkpoint, condition).
OrchestratorCheckpoint — approval/review checkpoint.
"""

from datetime import datetime

from sqlalchemy import (
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
from sqlalchemy.orm import relationship

from src.models.database import Base, generate_uuid


class OrchestratorRun(Base):
    """Запуск оркестрации — high-level цель."""

    __tablename__ = "orchestrator_runs"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    goal = Column(Text, nullable=False)  # High-level цель: "Подготовь документ к согласованию"
    initiated_by = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    document_id = Column(String(36), ForeignKey("contracts.id", ondelete="SET NULL"), nullable=True, index=True)
    session_id = Column(String(36), ForeignKey("ai_sessions.id", ondelete="SET NULL"), nullable=True, index=True)

    status = Column(String(20), nullable=False, default="planning")

    # Метрики
    total_steps = Column(Integer, default=0)
    completed_steps = Column(Integer, default=0)
    failed_steps = Column(Integer, default=0)

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    completed_at = Column(DateTime, nullable=True)

    # Relationships
    plans = relationship("ExecutionPlan", back_populates="run", cascade="all, delete-orphan")
    checkpoints = relationship("OrchestratorCheckpoint", back_populates="run", cascade="all, delete-orphan")

    __table_args__ = (
        CheckConstraint(
            status.in_(["planning", "executing", "paused", "completed", "failed", "cancelled"]),
            name="check_orch_run_status",
        ),
        Index("idx_orch_run_status", "status", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<OrchestratorRun(id={self.id}, status={self.status}, goal={self.goal[:50]})>"


class ExecutionPlan(Base):
    """План выполнения — версионируемый."""

    __tablename__ = "execution_plans"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    run_id = Column(String(36), ForeignKey("orchestrator_runs.id", ondelete="CASCADE"), nullable=False, index=True)

    plan_definition = Column(JSON, nullable=False)  # Полное определение плана
    version = Column(Integer, default=1)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    # Relationships
    run = relationship("OrchestratorRun", back_populates="plans")
    steps = relationship("PlanStep", back_populates="plan", cascade="all, delete-orphan", order_by="PlanStep.order")

    __table_args__ = (
        Index("idx_exec_plan_run_ver", "run_id", "version"),
    )

    def __repr__(self) -> str:
        return f"<ExecutionPlan(id={self.id}, run={self.run_id}, v={self.version})>"


class PlanStep(Base):
    """Шаг плана — tool_call, agent_delegation, approval_checkpoint, condition."""

    __tablename__ = "plan_steps"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    plan_id = Column(String(36), ForeignKey("execution_plans.id", ondelete="CASCADE"), nullable=False, index=True)

    order = Column(Integer, nullable=False)  # Порядок выполнения
    name = Column(String(255), nullable=True)  # Человекочитаемое имя шага
    step_type = Column(String(30), nullable=False)  # tool_call|agent_delegation|approval_checkpoint|condition

    # Привязка к tool/agent
    tool_id = Column(String(100), nullable=True)
    agent_id = Column(String(100), nullable=True)

    # Input/Output
    input_data = Column(JSON, nullable=True)   # Может ссылаться на output предыдущих шагов: {"$ref": "step.2.output.risks"}
    output_data = Column(JSON, nullable=True)

    # Condition (для step_type=condition)
    condition = Column(JSON, nullable=True)  # {"field": "step.2.output.risk_level", "op": ">", "value": "HIGH"}

    # Status
    status = Column(String(20), nullable=False, default="pending")
    error = Column(Text, nullable=True)

    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)

    # Relationships
    plan = relationship("ExecutionPlan", back_populates="steps")

    __table_args__ = (
        CheckConstraint(
            step_type.in_(["tool_call", "agent_delegation", "approval_checkpoint", "condition"]),
            name="check_plan_step_type",
        ),
        CheckConstraint(
            status.in_(["pending", "running", "completed", "failed", "blocked", "skipped"]),
            name="check_plan_step_status",
        ),
        Index("idx_plan_step_plan_order", "plan_id", "order"),
    )

    def __repr__(self) -> str:
        return f"<PlanStep(id={self.id}, order={self.order}, type={self.step_type}, status={self.status})>"


class OrchestratorCheckpoint(Base):
    """Approval/review checkpoint — pause point для human review."""

    __tablename__ = "orchestrator_checkpoints"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    run_id = Column(String(36), ForeignKey("orchestrator_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    step_id = Column(String(36), ForeignKey("plan_steps.id", ondelete="SET NULL"), nullable=True, index=True)

    checkpoint_type = Column(String(30), nullable=False)  # approval | review | escalation
    status = Column(String(20), nullable=False, default="pending")  # pending | approved | rejected | escalated

    resolved_by = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    resolved_at = Column(DateTime, nullable=True)
    comment = Column(Text, nullable=True)

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    # Relationships
    run = relationship("OrchestratorRun", back_populates="checkpoints")

    __table_args__ = (
        CheckConstraint(
            checkpoint_type.in_(["approval", "review", "escalation"]),
            name="check_checkpoint_type",
        ),
        CheckConstraint(
            status.in_(["pending", "approved", "rejected", "escalated"]),
            name="check_checkpoint_status",
        ),
        Index("idx_checkpoint_run_status", "run_id", "status"),
    )

    def __repr__(self) -> str:
        return f"<OrchestratorCheckpoint(id={self.id}, type={self.checkpoint_type}, status={self.status})>"
