"""
Integrations — SQLAlchemy модели.

IntegrationConfig — конфиг интеграции (webhook, API, EDO, ESign).
WebhookDelivery — лог доставки webhook.
DomainEvent — внутренние события системы.
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
    Boolean,
)

from src.models.database import Base, generate_uuid


class IntegrationConfig(Base):
    """Конфигурация интеграции."""

    __tablename__ = "integration_configs"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    org_id = Column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True, index=True)

    integration_type = Column(String(30), nullable=False)  # webhook|api|edo|esign
    name = Column(String(255), nullable=False)
    config = Column(JSON, nullable=False)  # URL, secret, credentials (зашифрованы)

    active = Column(Boolean, default=True, index=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        CheckConstraint(
            integration_type.in_(["webhook", "api", "edo", "esign"]),
            name="check_integration_type",
        ),
        Index("idx_integration_org_type", "org_id", "integration_type"),
    )

    def __repr__(self) -> str:
        return f"<IntegrationConfig(id={self.id}, type={self.integration_type}, name={self.name})>"


class WebhookDelivery(Base):
    """Лог доставки webhook."""

    __tablename__ = "webhook_deliveries"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    config_id = Column(String(36), ForeignKey("integration_configs.id", ondelete="CASCADE"), nullable=False, index=True)

    event_type = Column(String(100), nullable=False, index=True)
    payload = Column(JSON, nullable=False)

    status = Column(String(20), nullable=False, default="pending")  # pending|delivered|failed
    response_code = Column(Integer, nullable=True)
    response_body = Column(Text, nullable=True)

    attempts = Column(Integer, default=0)
    max_attempts = Column(Integer, default=3)
    last_attempt_at = Column(DateTime, nullable=True)
    delivered_at = Column(DateTime, nullable=True)

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)

    __table_args__ = (
        CheckConstraint(
            status.in_(["pending", "delivered", "failed"]),
            name="check_webhook_delivery_status",
        ),
        Index("idx_webhook_status_created", "status", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<WebhookDelivery(id={self.id}, event={self.event_type}, status={self.status})>"


class DomainEvent(Base):
    """Внутреннее событие системы (event sourcing lite)."""

    __tablename__ = "domain_events"

    id = Column(String(36), primary_key=True, default=generate_uuid)

    event_type = Column(String(100), nullable=False, index=True)
    # contract.uploaded, contract.analyzed, contract.approved,
    # workflow.started, workflow.completed,
    # ai.action.executed, ai.session.created, ...

    entity_type = Column(String(50), nullable=False, index=True)  # contract, workflow, ai_session, ...
    entity_id = Column(String(36), nullable=False, index=True)

    payload = Column(JSON, nullable=True)
    emitted_by = Column(String(100), nullable=True)  # user:<id> | system | agent:<id>

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)

    __table_args__ = (
        Index("idx_domain_event_entity", "entity_type", "entity_id"),
        Index("idx_domain_event_type_created", "event_type", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<DomainEvent(id={self.id}, type={self.event_type}, entity={self.entity_type}:{self.entity_id})>"
