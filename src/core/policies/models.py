"""
Policy Engine — SQLAlchemy модели.

Каскад политик: platform → tenant → organization → branch → document → user.
Более специфичный уровень переопределяет более общий.
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


class Policy(Base):
    """Политика — набор правил для определённого уровня и scope."""

    __tablename__ = "policies"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)

    # Уровень каскада
    level = Column(String(20), nullable=False, index=True)  # platform|tenant|organization|branch|document|user

    # К чему привязана (scope)
    scope_id = Column(String(36), nullable=True, index=True)  # org_id, user_id, document_id — зависит от level

    # Тип политики
    policy_type = Column(String(50), nullable=False, index=True)
    # ai_autonomy — уровень автономности AI
    # tool_access — доступ к инструментам
    # action_approval — какие действия требуют одобрения
    # data_sensitivity — ограничения по чувствительности данных
    # llm_routing — правила выбора LLM

    # Правила (JSON)
    rules = Column(JSON, nullable=False)
    # Пример для ai_autonomy:
    # {"max_autonomy_level": "copilot", "auto_approve_confidence_above": 0.9}
    # Пример для tool_access:
    # {"allowed_tools": ["document_parser", "risk_scorer"], "denied_tools": ["contract_generator"]}

    priority = Column(Integer, default=0)  # При конфликте — выигрывает больший priority
    active = Column(Boolean, default=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    approval_rules = relationship("ApprovalRule", back_populates="policy", cascade="all, delete-orphan")
    action_permissions = relationship("ActionPermission", back_populates="policy", cascade="all, delete-orphan")

    __table_args__ = (
        CheckConstraint(
            level.in_(["platform", "tenant", "organization", "branch", "document", "user"]),
            name="check_policy_level",
        ),
        Index("idx_policy_level_scope", "level", "scope_id", "active"),
        Index("idx_policy_type_active", "policy_type", "active"),
    )

    def __repr__(self) -> str:
        return f"<Policy(id={self.id}, name={self.name}, level={self.level}, type={self.policy_type})>"


class ApprovalRule(Base):
    """Правило одобрения — какие действия требуют human approval."""

    __tablename__ = "approval_rules"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    policy_id = Column(String(36), ForeignKey("policies.id", ondelete="CASCADE"), nullable=False, index=True)

    # Паттерн действия (glob-like): "tool.*", "agent.review_agent.*", "action.create_comment"
    action_pattern = Column(String(255), nullable=False)

    # Сколько approvers нужно
    required_approvers = Column(Integer, default=1)

    # Таймаут эскалации (секунды). 0 = без таймаута.
    escalation_timeout = Column(Integer, default=0)

    # Кому эскалировать (роль или user_id)
    escalation_target = Column(String(100), nullable=True)  # "org_admin" | user_id

    active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    policy = relationship("Policy", back_populates="approval_rules")

    __table_args__ = (
        Index("idx_approval_policy_pattern", "policy_id", "action_pattern"),
    )

    def __repr__(self) -> str:
        return f"<ApprovalRule(id={self.id}, pattern={self.action_pattern}, approvers={self.required_approvers})>"


class ActionPermission(Base):
    """Разрешение на действие — для конкретных ролей с условиями."""

    __tablename__ = "action_permissions"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    policy_id = Column(String(36), ForeignKey("policies.id", ondelete="CASCADE"), nullable=False, index=True)

    action_type = Column(String(100), nullable=False)  # tool.execute, agent.delegate, session.create, ...
    allowed_roles = Column(JSON, nullable=False)  # ["admin", "senior_lawyer", "org_admin"]
    conditions = Column(JSON, nullable=True)  # {"risk_level_max": "medium", "document_role": ["owner", "reviewer"]}

    active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    policy = relationship("Policy", back_populates="action_permissions")

    __table_args__ = (
        Index("idx_action_perm_policy_type", "policy_id", "action_type"),
    )

    def __repr__(self) -> str:
        return f"<ActionPermission(id={self.id}, action={self.action_type})>"
