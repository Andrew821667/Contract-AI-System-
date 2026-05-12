# -*- coding: utf-8 -*-
"""
Counterparty models — контрагенты как сущность БД.

Контрагент — внешняя сторона договора (юрлицо или физлицо). Нужен для:
- Группировки договоров по контрагенту в UI и поиске.
- Кэширования данных проверки ФНС/Федресурс между загрузками договоров.
- Привязки реквизитов (ИНН/КПП/ОГРН/банковские) к договорам через FK,
  а не дублирования в meta_info каждого договора.

Мульти-тенантность: organization_id nullable (legacy fallback на created_by).
"""
from datetime import datetime, timezone

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

from .database import Base, generate_uuid


COUNTERPARTY_TYPES = ["legal", "individual", "individual_entrepreneur", "foreign", "other"]
COUNTERPARTY_STATUSES = ["active", "archived"]


class Counterparty(Base):
    """Контрагент — внешняя сторона договора."""

    __tablename__ = "counterparties"

    id = Column(String(36), primary_key=True, default=generate_uuid)

    # Тенант + автор
    organization_id = Column(
        String(36),
        ForeignKey("organizations.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    created_by = Column(
        String(36),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Тип и статус
    type = Column(String(30), nullable=False, default="legal")
    status = Column(String(20), nullable=False, default="active", index=True)

    # Идентификация
    name = Column(String(500), nullable=False)
    short_name = Column(String(255), nullable=True)
    inn = Column(String(20), nullable=True, index=True)
    kpp = Column(String(20), nullable=True)
    ogrn = Column(String(20), nullable=True, index=True)

    # Адреса
    legal_address = Column(Text, nullable=True)
    postal_address = Column(Text, nullable=True)

    # Контакты
    contact_person = Column(String(255), nullable=True)
    contact_email = Column(String(255), nullable=True)
    contact_phone = Column(String(50), nullable=True)

    # Реквизиты
    bank_details = Column(JSON, nullable=True)

    # Кэш проверки ФНС/Федресурс
    fns_data = Column(JSON, nullable=True)
    fns_checked_at = Column(DateTime, nullable=True)
    bankruptcy_data = Column(JSON, nullable=True)
    bankruptcy_checked_at = Column(DateTime, nullable=True)

    # Произвольные метаданные (категории, теги, заметки)
    notes = Column(Text, nullable=True)
    meta_info = Column(JSON, nullable=True)

    created_at = Column(
        DateTime, default=lambda: datetime.now(timezone.utc), nullable=False, index=True
    )
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    organization = relationship("Organization", foreign_keys=[organization_id])
    creator = relationship("User", foreign_keys=[created_by])

    __table_args__ = (
        # Один и тот же ИНН в одной организации — одна запись.
        # NULL inn (физлица без ИНН) допускают повторения — поведение SQL для NULL.
        UniqueConstraint("organization_id", "inn", name="uq_counterparty_org_inn"),
        CheckConstraint(
            f"type IN ({', '.join(repr(t) for t in COUNTERPARTY_TYPES)})",
            name="check_counterparty_type",
        ),
        CheckConstraint(
            f"status IN ({', '.join(repr(s) for s in COUNTERPARTY_STATUSES)})",
            name="check_counterparty_status",
        ),
        Index("idx_counterparty_org_status", "organization_id", "status"),
        Index("idx_counterparty_name", "name"),
    )

    def __repr__(self) -> str:
        return f"<Counterparty(id={self.id}, name={self.name}, inn={self.inn})>"

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "organization_id": self.organization_id,
            "created_by": self.created_by,
            "type": self.type,
            "status": self.status,
            "name": self.name,
            "short_name": self.short_name,
            "inn": self.inn,
            "kpp": self.kpp,
            "ogrn": self.ogrn,
            "legal_address": self.legal_address,
            "postal_address": self.postal_address,
            "contact_person": self.contact_person,
            "contact_email": self.contact_email,
            "contact_phone": self.contact_phone,
            "bank_details": self.bank_details,
            "fns_data": self.fns_data,
            "fns_checked_at": self.fns_checked_at.isoformat() if self.fns_checked_at else None,
            "bankruptcy_data": self.bankruptcy_data,
            "bankruptcy_checked_at": (
                self.bankruptcy_checked_at.isoformat() if self.bankruptcy_checked_at else None
            ),
            "notes": self.notes,
            "meta_info": self.meta_info,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


__all__ = ["Counterparty", "COUNTERPARTY_TYPES", "COUNTERPARTY_STATUSES"]
