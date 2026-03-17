"""
Identity & Organization — SQLAlchemy модели.

Таблицы:
- organizations — организации-тенанты
- organization_units — подразделения (дерево)
- organization_memberships — участие пользователей в организациях
- document_participations — роли пользователей на уровне документа
- tenant_contexts — режим работы (standalone / branch)
- user_agent_policy_profiles — AI-policy на уровне пользователя
"""

from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Index,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from src.models.database import Base, generate_uuid


class Organization(Base):
    """Организация-тенант."""

    __tablename__ = "organizations"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    name = Column(String(255), nullable=False)
    slug = Column(String(100), unique=True, nullable=False, index=True)
    description = Column(Text, nullable=True)
    settings = Column(JSON, nullable=True)  # org-level настройки (LLM policy, defaults, etc.)
    active = Column(Boolean, default=True, index=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    units = relationship("OrganizationUnit", back_populates="organization", cascade="all, delete-orphan")
    memberships = relationship("OrganizationMembership", back_populates="organization", cascade="all, delete-orphan")
    tenant_context = relationship("TenantContext", back_populates="organization", uselist=False, cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Organization(id={self.id}, slug={self.slug})>"


class OrganizationUnit(Base):
    """Подразделение организации (дерево)."""

    __tablename__ = "organization_units"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    org_id = Column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    parent_unit_id = Column(String(36), ForeignKey("organization_units.id", ondelete="SET NULL"), nullable=True, index=True)
    level = Column(String(50), nullable=False, default="department")  # department, division, team
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    # Relationships
    organization = relationship("Organization", back_populates="units")
    parent = relationship("OrganizationUnit", remote_side=[id], backref="children")

    __table_args__ = (
        Index("idx_unit_org_parent", "org_id", "parent_unit_id"),
    )

    def __repr__(self) -> str:
        return f"<OrganizationUnit(id={self.id}, name={self.name}, org={self.org_id})>"


class OrganizationMembership(Base):
    """Участие пользователя в организации."""

    __tablename__ = "organization_memberships"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    org_id = Column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    unit_id = Column(String(36), ForeignKey("organization_units.id", ondelete="SET NULL"), nullable=True)

    # Роли в организации
    company_role = Column(String(100), nullable=True)  # Должность: "Старший юрист", "Руководитель отдела"
    functional_role = Column(String(50), nullable=False, default="member")  # org_admin, manager, member, viewer

    active = Column(Boolean, default=True, index=True)
    joined_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        UniqueConstraint("user_id", "org_id", name="uq_user_org_membership"),
        CheckConstraint(
            functional_role.in_(["org_admin", "manager", "member", "viewer"]),
            name="check_functional_role",
        ),
        Index("idx_membership_org_active", "org_id", "active"),
    )

    # Relationships
    organization = relationship("Organization", back_populates="memberships")

    def __repr__(self) -> str:
        return f"<OrganizationMembership(user={self.user_id}, org={self.org_id}, role={self.functional_role})>"


class DocumentParticipation(Base):
    """Роль пользователя в рамках конкретного документа."""

    __tablename__ = "document_participations"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    document_id = Column(String(36), ForeignKey("contracts.id", ondelete="CASCADE"), nullable=False, index=True)
    role = Column(String(50), nullable=False)  # owner, reviewer, approver, observer, negotiator, signer, ai_supervisor
    assigned_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    assigned_by = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    __table_args__ = (
        UniqueConstraint("user_id", "document_id", "role", name="uq_user_doc_role"),
        CheckConstraint(
            role.in_(["owner", "reviewer", "approver", "observer", "negotiator", "signer", "ai_supervisor"]),
            name="check_doc_participation_role",
        ),
        Index("idx_doc_participation_doc", "document_id", "role"),
    )

    def __repr__(self) -> str:
        return f"<DocumentParticipation(user={self.user_id}, doc={self.document_id}, role={self.role})>"


class TenantContext(Base):
    """Режим работы tenant (standalone / branch)."""

    __tablename__ = "tenant_contexts"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    org_id = Column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), unique=True, nullable=False)
    mode = Column(String(20), nullable=False, default="standalone")  # standalone | branch
    parent_tenant_id = Column(String(36), ForeignKey("tenant_contexts.id", ondelete="SET NULL"), nullable=True)
    config = Column(JSON, nullable=True)  # branch-specific overrides
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        CheckConstraint(mode.in_(["standalone", "branch"]), name="check_tenant_mode"),
    )

    # Relationships
    organization = relationship("Organization", back_populates="tenant_context")
    parent = relationship("TenantContext", remote_side=[id])

    def __repr__(self) -> str:
        return f"<TenantContext(org={self.org_id}, mode={self.mode})>"


class UserAgentPolicyProfile(Base):
    """AI-policy на уровне пользователя — что AI может делать для этого пользователя."""

    __tablename__ = "user_agent_policy_profiles"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    org_id = Column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True, index=True)

    # Что разрешено AI
    allowed_ai_modes = Column(JSON, nullable=True)      # ["advisor", "copilot"]
    allowed_actions = Column(JSON, nullable=True)        # ["explain_finding", "suggest_clause", ...]
    allowed_agents = Column(JSON, nullable=True)         # ["review_agent", "generator_agent"]
    allowed_tools = Column(JSON, nullable=True)          # ["document_parser", "risk_scorer"]
    approval_required_for = Column(JSON, nullable=True)  # ["create_comment", "modify_clause"]

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        UniqueConstraint("user_id", "org_id", name="uq_user_org_agent_policy"),
    )

    def __repr__(self) -> str:
        return f"<UserAgentPolicyProfile(user={self.user_id}, org={self.org_id})>"
