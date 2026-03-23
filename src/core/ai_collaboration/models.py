"""
AI Collaboration — SQLAlchemy модели.

AISession — сессия взаимодействия AI с документом.
AIConversationTurn — отдельное сообщение (user/assistant/system).
AIAction — предложенное или выполненное действие AI.
AIActionApproval — решение человека по действию.
AIAuditRecord — детальный аудит AI-взаимодействий.
"""

from datetime import datetime, timezone
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
from sqlalchemy.orm import relationship

from src.models.database import Base, generate_uuid


class AISession(Base):
    """AI-сессия — контекст взаимодействия AI с документом."""

    __tablename__ = "ai_sessions"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    document_id = Column(String(36), ForeignKey("contracts.id", ondelete="CASCADE"), nullable=True, index=True)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    organization_id = Column(String(36), ForeignKey("organizations.id", ondelete="SET NULL"), nullable=True, index=True)

    stage = Column(String(30), nullable=False, default="intake")
    status = Column(String(20), nullable=False, default="active")

    # Снимок контекста (для восстановления сессии)
    context_snapshot = Column(JSON, nullable=True)

    # Метрики
    total_turns = Column(Integer, default=0)
    total_actions = Column(Integer, default=0)
    total_tokens_used = Column(Integer, default=0)

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    closed_at = Column(DateTime, nullable=True)

    # Relationships
    turns = relationship("AIConversationTurn", back_populates="session", cascade="all, delete-orphan", order_by="AIConversationTurn.created_at")
    actions = relationship("AIAction", back_populates="session", cascade="all, delete-orphan")
    audit_records = relationship("AIAuditRecord", back_populates="session", cascade="all, delete-orphan")

    __table_args__ = (
        CheckConstraint(
            stage.in_(["intake", "classification", "analysis", "review", "negotiation", "approval", "generation", "export", "general"]),
            name="check_ai_session_stage",
        ),
        CheckConstraint(
            status.in_(["active", "paused", "closed"]),
            name="check_ai_session_status",
        ),
        Index("idx_ai_session_doc_user", "document_id", "user_id"),
        Index("idx_ai_session_status", "status", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<AISession(id={self.id}, doc={self.document_id}, stage={self.stage}, status={self.status})>"


class AIConversationTurn(Base):
    """Одно сообщение в AI-диалоге."""

    __tablename__ = "ai_conversation_turns"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    session_id = Column(String(36), ForeignKey("ai_sessions.id", ondelete="CASCADE"), nullable=False, index=True)

    role = Column(String(20), nullable=False)  # user | assistant | system
    content = Column(Text, nullable=False)

    # LLM метаданные
    model_used = Column(String(100), nullable=True)
    tokens_input = Column(Integer, default=0)
    tokens_output = Column(Integer, default=0)

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)

    # Relationships
    session = relationship("AISession", back_populates="turns")

    __table_args__ = (
        CheckConstraint(role.in_(["user", "assistant", "system"]), name="check_turn_role"),
        Index("idx_turn_session_created", "session_id", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<AIConversationTurn(id={self.id}, role={self.role}, len={len(self.content or '')})>"


class AIAction(Base):
    """AI-действие — предложено AI, ожидает/получило одобрение, выполнено."""

    __tablename__ = "ai_actions"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    session_id = Column(String(36), ForeignKey("ai_sessions.id", ondelete="CASCADE"), nullable=False, index=True)

    # Тип действия
    action_type = Column(String(50), nullable=False, index=True)
    # explain_finding, suggest_clause, create_comment_draft, modify_clause,
    # suggest_risk_mitigation, create_summary, assign_reviewer, ...

    # Целевая сущность
    target_entity_type = Column(String(50), nullable=True)  # finding | clause | comment | document | ...
    target_entity_id = Column(String(36), nullable=True)

    # Данные действия
    payload = Column(JSON, nullable=True)        # Содержимое действия
    rationale = Column(Text, nullable=True)      # Объяснение AI, почему предлагает это
    confidence = Column(Float, default=0.0)      # Уверенность AI (0.0–1.0)

    # Approval
    approval_required = Column(Boolean, default=True)
    execution_status = Column(String(20), nullable=False, default="pending")

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    executed_at = Column(DateTime, nullable=True)

    # Relationships
    session = relationship("AISession", back_populates="actions")
    approval = relationship("AIActionApproval", back_populates="action", uselist=False, cascade="all, delete-orphan")

    __table_args__ = (
        CheckConstraint(
            execution_status.in_(["pending", "approved", "rejected", "executed", "blocked", "failed"]),
            name="check_ai_action_status",
        ),
        Index("idx_ai_action_session_status", "session_id", "execution_status"),
        Index("idx_ai_action_type", "action_type", "execution_status"),
    )

    def __repr__(self) -> str:
        return f"<AIAction(id={self.id}, type={self.action_type}, status={self.execution_status}, conf={self.confidence})>"


class AIActionApproval(Base):
    """Решение человека по AI-действию."""

    __tablename__ = "ai_action_approvals"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    action_id = Column(String(36), ForeignKey("ai_actions.id", ondelete="CASCADE"), unique=True, nullable=False)
    approver_id = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)

    decision = Column(String(30), nullable=False)  # approve | reject | edit_and_approve
    comment = Column(Text, nullable=True)
    edited_payload = Column(JSON, nullable=True)  # Если edit_and_approve — отредактированные данные

    decided_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    # Relationships
    action = relationship("AIAction", back_populates="approval")

    __table_args__ = (
        CheckConstraint(
            decision.in_(["approve", "reject", "edit_and_approve"]),
            name="check_approval_decision",
        ),
    )

    def __repr__(self) -> str:
        return f"<AIActionApproval(action={self.action_id}, decision={self.decision})>"


class AIAuditRecord(Base):
    """Детальный аудит AI-взаимодействий (что отправлено в LLM, что получено)."""

    __tablename__ = "ai_audit_records"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    session_id = Column(String(36), ForeignKey("ai_sessions.id", ondelete="CASCADE"), nullable=True, index=True)
    action_id = Column(String(36), ForeignKey("ai_actions.id", ondelete="SET NULL"), nullable=True, index=True)

    actor = Column(String(100), nullable=False)  # user:<id> | agent:<id> | orchestrator
    event_type = Column(String(50), nullable=False, index=True)
    # llm_call, tool_call, action_proposed, action_approved, action_rejected,
    # action_executed, policy_check, context_built, ...

    details = Column(JSON, nullable=True)
    model_used = Column(String(100), nullable=True)
    context_sent = Column(JSON, nullable=True)  # Какой контекст отправлен в LLM (для воспроизводимости)

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)

    # Relationships
    session = relationship("AISession", back_populates="audit_records")

    __table_args__ = (
        Index("idx_ai_audit_session_event", "session_id", "event_type"),
        Index("idx_ai_audit_created", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<AIAuditRecord(id={self.id}, event={self.event_type}, actor={self.actor})>"


class AIActionPolicy(Base):
    """
    Политика AI-действий — правила approval, risk level, tool mapping.

    Заменяет хардкод-константы в action_executor/action_parser.
    Позволяет управлять правилами через БД (admin UI, API).
    """

    __tablename__ = "ai_action_policies"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    action_type = Column(String(50), nullable=False, unique=True, index=True)

    # Risk level для policy checks
    risk_level = Column(String(20), nullable=False, default="medium")  # low|medium|high|critical

    # Approval requirements
    approval_required = Column(Boolean, default=True)
    auto_approve_threshold = Column(Float, default=0.9)  # confidence >= порога → auto-approve

    # Execution mapping
    tool_id = Column(String(100), nullable=True)  # если None → direct execution
    direct_execution = Column(Boolean, default=False)

    # Scope ограничения
    allowed_roles = Column(JSON, nullable=True)  # ["admin", "senior_lawyer"] или null = все
    org_id = Column(String(36), nullable=True, index=True)  # null = глобальная

    # Описание для UI
    description = Column(Text, nullable=True)

    active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    def __repr__(self) -> str:
        return f"<AIActionPolicy(action_type={self.action_type}, risk={self.risk_level}, approval={self.approval_required})>"
