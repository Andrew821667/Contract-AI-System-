# -*- coding: utf-8 -*-
"""Usage quota helpers shared by auth and contract upload routes."""

from datetime import datetime
from typing import Dict, Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from src.models.auth_models import User
from src.models.database import Contract


FREE_CONTRACTS_PER_MONTH = 3


def _month_start() -> datetime:
    return datetime.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def uses_monthly_contract_quota(user: User) -> bool:
    return user.subscription_tier == "demo" or user.role == "demo" or bool(user.is_demo)


def contracts_used_this_month(db: Session, user_id: str) -> int:
    return db.query(func.count(Contract.id)).filter(
        Contract.assigned_to == user_id,
        Contract.created_at >= _month_start(),
        Contract.status != "deleted",
    ).scalar() or 0


def get_contract_quota(db: Session, user: User) -> Dict[str, Any]:
    if uses_monthly_contract_quota(user):
        return {
            "used": contracts_used_this_month(db, user.id),
            "limit": FREE_CONTRACTS_PER_MONTH,
            "period": "month",
        }

    user.reset_daily_limits()
    return {
        "used": user.contracts_today or 0,
        "limit": user.max_contracts_per_day,
        "period": "day",
    }


def contract_limit_message(limit: int, period: str) -> str:
    if period == "month":
        return f"Месячный бесплатный лимит загрузки ({limit}) исчерпан. Обновите тариф или дождитесь следующего месяца."
    return f"Дневной лимит загрузки ({limit}) исчерпан. Попробуйте завтра."

