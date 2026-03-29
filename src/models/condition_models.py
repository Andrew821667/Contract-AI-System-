# -*- coding: utf-8 -*-
"""
Company Conditions Models
Стандартные условия компании, влияющие на анализ договоров.
"""
from datetime import datetime, timezone
from sqlalchemy import (
    Column, String, Text, Integer, Boolean,
    DateTime, ForeignKey, Index
)
from sqlalchemy.orm import relationship

from .database import Base, generate_uuid


CONDITION_CATEGORIES = [
    'financial',        # Финансовые
    'deadlines',        # Сроки
    'liability',        # Ответственность
    'termination',      # Расторжение
    'confidentiality',  # Конфиденциальность
    'warranties',       # Гарантии
    'force_majeure',    # Форс-мажор
    'dispute',          # Разрешение споров
    'ip',               # Интеллектуальная собственность
    'compliance',       # Соответствие требованиям
    'other',            # Прочие
]


class CompanyCondition(Base):
    """Стандартное условие компании пользователя"""
    __tablename__ = "company_conditions"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(
        String(36),
        ForeignKey('users.id', ondelete='CASCADE'),
        nullable=False
    )
    category = Column(String(50), nullable=False, default='other')
    title = Column(String(500), nullable=False)
    description = Column(Text, nullable=True)
    condition_text = Column(Text, nullable=False)
    priority = Column(Integer, nullable=False, default=1)  # 1=low, 2=medium, 3=high
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    user = relationship("User", backref="company_conditions")

    __table_args__ = (
        Index('idx_condition_user_id', 'user_id'),
        Index('idx_condition_category', 'category'),
        Index('idx_condition_active', 'is_active'),
    )

    def __repr__(self):
        return f"<CompanyCondition(id={self.id}, title={self.title}, category={self.category})>"

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'category': self.category,
            'title': self.title,
            'description': self.description,
            'condition_text': self.condition_text,
            'priority': self.priority,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }
