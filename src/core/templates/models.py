"""
Template Governance — SQLAlchemy модели.

TemplateVersion — версионирование шаблонов.
ClausePolicy — политика использования клауз (approved/prohibited/risky).
GeneratedDocumentTrace — traceability генерации (какой шаблон, какие переменные, какой AI).
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

from src.models.database import Base, generate_uuid


class TemplateVersion(Base):
    """Версия шаблона."""

    __tablename__ = "template_versions"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    template_id = Column(String(36), ForeignKey("templates.id", ondelete="CASCADE"), nullable=False, index=True)

    version = Column(Integer, nullable=False)
    content = Column(JSON, nullable=False)  # Структура шаблона (XML/JSON)
    variables = Column(JSON, nullable=True)  # Переменные шаблона: [{"name": "party_name", "type": "string", ...}]
    validation_rules = Column(JSON, nullable=True)  # Правила валидации

    status = Column(String(20), nullable=False, default="draft")  # draft|active|deprecated
    created_by = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        CheckConstraint(
            status.in_(["draft", "active", "deprecated"]),
            name="check_template_version_status",
        ),
        Index("idx_tpl_ver_template_ver", "template_id", "version"),
    )

    def __repr__(self) -> str:
        return f"<TemplateVersion(template={self.template_id}, v={self.version}, status={self.status})>"


class ClausePolicy(Base):
    """Политика использования клаузы в организации."""

    __tablename__ = "clause_policies"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    org_id = Column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True, index=True)

    clause_type = Column(String(50), nullable=False, index=True)  # financial, liability, termination, etc.
    status = Column(String(20), nullable=False)  # approved|fallback|prohibited|risky

    alternative_clause_id = Column(String(36), nullable=True)  # ID рекомендуемой альтернативной клаузы
    risk_explanation = Column(Text, nullable=True)  # Почему risky/prohibited

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        CheckConstraint(
            status.in_(["approved", "fallback", "prohibited", "risky"]),
            name="check_clause_policy_status",
        ),
        Index("idx_clause_policy_org_type", "org_id", "clause_type"),
    )

    def __repr__(self) -> str:
        return f"<ClausePolicy(org={self.org_id}, type={self.clause_type}, status={self.status})>"


class GeneratedDocumentTrace(Base):
    """Traceability генерации документа — из чего собран."""

    __tablename__ = "generated_document_traces"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    document_id = Column(String(36), ForeignKey("contracts.id", ondelete="CASCADE"), nullable=False, index=True)
    template_id = Column(String(36), ForeignKey("templates.id", ondelete="SET NULL"), nullable=True)
    template_version = Column(Integer, nullable=True)

    variables_used = Column(JSON, nullable=True)  # Какие переменные подставлены
    clauses_used = Column(JSON, nullable=True)    # Какие клаузы вошли в документ
    ai_session_id = Column(String(36), ForeignKey("ai_sessions.id", ondelete="SET NULL"), nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("idx_gen_trace_doc", "document_id"),
    )

    def __repr__(self) -> str:
        return f"<GeneratedDocumentTrace(doc={self.document_id}, tpl={self.template_id})>"
