"""
Workflow Engine — SQLAlchemy модели.

WorkflowDefinition — шаблон маршрута согласования.
WorkflowExecution — экземпляр выполнения workflow для документа.
WorkflowTask — задача на конкретного участника.
WorkflowEvent — событие workflow (для audit trail).
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
from sqlalchemy.orm import relationship

from src.models.database import Base, generate_uuid


class WorkflowDefinition(Base):
    """Шаблон маршрута согласования."""

    __tablename__ = "workflow_definitions"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)

    document_type = Column(String(50), nullable=True, index=True)  # contract, disagreement, etc.
    jurisdiction = Column(String(50), nullable=True)  # RF, CIS, etc.
    org_id = Column(String(36), ForeignKey("organizations.id", ondelete="SET NULL"), nullable=True, index=True)

    # Условия активации
    conditions = Column(JSON, nullable=True)  # {"risk_level": ["HIGH", "CRITICAL"], "contract_type": ["supply"]}

    # Шаги маршрута
    steps = Column(JSON, nullable=False)
    # [
    #   {"name": "Первичная проверка", "assignee_role": "lawyer", "sla_hours": 24},
    #   {"name": "Согласование руководителем", "assignee_role": "senior_lawyer", "sla_hours": 48},
    #   {"name": "Финальное утверждение", "assignee_role": "admin", "sla_hours": 72},
    # ]

    active = Column(Boolean, default=True, index=True)
    version = Column(Integer, default=1)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    executions = relationship("WorkflowExecution", back_populates="definition")

    __table_args__ = (
        Index("idx_wf_def_doctype", "document_type", "active"),
    )

    def __repr__(self) -> str:
        return f"<WorkflowDefinition(id={self.id}, name={self.name})>"


class WorkflowExecution(Base):
    """Экземпляр выполнения workflow для конкретного документа."""

    __tablename__ = "workflow_executions"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    definition_id = Column(String(36), ForeignKey("workflow_definitions.id", ondelete="SET NULL"), nullable=True, index=True)
    document_id = Column(String(36), ForeignKey("contracts.id", ondelete="CASCADE"), nullable=False, index=True)

    current_step = Column(Integer, default=0)  # Текущий шаг (0-based)
    status = Column(String(20), nullable=False, default="active")

    started_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)

    # Relationships
    definition = relationship("WorkflowDefinition", back_populates="executions")
    tasks = relationship("WorkflowTask", back_populates="execution", cascade="all, delete-orphan")
    events = relationship("WorkflowEvent", back_populates="execution", cascade="all, delete-orphan")

    __table_args__ = (
        CheckConstraint(
            status.in_(["active", "completed", "cancelled", "failed"]),
            name="check_wf_execution_status",
        ),
        Index("idx_wf_exec_doc", "document_id", "status"),
    )

    def __repr__(self) -> str:
        return f"<WorkflowExecution(id={self.id}, doc={self.document_id}, step={self.current_step}, status={self.status})>"


class WorkflowTask(Base):
    """Задача на конкретного участника."""

    __tablename__ = "workflow_tasks"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    execution_id = Column(String(36), ForeignKey("workflow_executions.id", ondelete="CASCADE"), nullable=False, index=True)

    step_name = Column(String(255), nullable=False)
    step_order = Column(Integer, nullable=False)
    assignee_id = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    task_type = Column(String(50), default="review")  # review, approve, sign, negotiate

    status = Column(String(20), nullable=False, default="pending")
    decision = Column(String(30), nullable=True)  # approve, reject, return_for_revision
    comment = Column(Text, nullable=True)

    sla_deadline = Column(DateTime, nullable=True, index=True)
    sla_breached = Column(Boolean, default=False)

    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)

    # Relationships
    execution = relationship("WorkflowExecution", back_populates="tasks")

    __table_args__ = (
        CheckConstraint(
            status.in_(["pending", "in_progress", "completed", "escalated", "skipped"]),
            name="check_wf_task_status",
        ),
        Index("idx_wf_task_assignee_status", "assignee_id", "status"),
        Index("idx_wf_task_sla", "sla_deadline", "sla_breached"),
    )

    def __repr__(self) -> str:
        return f"<WorkflowTask(id={self.id}, step={self.step_name}, status={self.status})>"


class WorkflowEvent(Base):
    """Событие workflow (для audit trail и event-driven интеграций)."""

    __tablename__ = "workflow_events"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    execution_id = Column(String(36), ForeignKey("workflow_executions.id", ondelete="CASCADE"), nullable=False, index=True)

    event_type = Column(String(50), nullable=False, index=True)
    # task_created, task_completed, task_escalated, step_advanced,
    # workflow_completed, workflow_cancelled, sla_breached

    payload = Column(JSON, nullable=True)
    triggered_by = Column(String(100), nullable=True)  # user:<id> | system | ai

    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    # Relationships
    execution = relationship("WorkflowExecution", back_populates="events")

    __table_args__ = (
        Index("idx_wf_event_exec_type", "execution_id", "event_type"),
    )

    def __repr__(self) -> str:
        return f"<WorkflowEvent(id={self.id}, type={self.event_type})>"
