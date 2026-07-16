# -*- coding: utf-8 -*-
"""Usage quota helpers shared by auth and contract upload routes."""

from typing import Dict, Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from src.models.auth_models import DemoToken, User
from src.models.database import Contract


DEFAULT_DEMO_CONTRACTS = 3
DEFAULT_DEMO_LLM_REQUESTS = 10


def uses_demo_quota(user: User) -> bool:
    return user.subscription_tier == "demo" or user.role == "demo" or bool(user.is_demo)


def contracts_used_in_demo(db: Session, user_id: str) -> int:
    return db.query(func.count(Contract.id)).filter(
        Contract.assigned_to == user_id,
        Contract.status != "deleted",
    ).scalar() or 0


def _demo_token(db: Session, user: User) -> DemoToken | None:
    if not user.demo_token:
        return None
    return db.query(DemoToken).filter(DemoToken.token == user.demo_token).first()


def get_contract_quota(db: Session, user: User) -> Dict[str, Any]:
    if uses_demo_quota(user):
        token = _demo_token(db, user)
        return {
            "used": contracts_used_in_demo(db, user.id),
            "limit": token.max_contracts if token else DEFAULT_DEMO_CONTRACTS,
            "period": "demo",
        }

    user.reset_daily_limits()
    return {
        "used": user.contracts_today or 0,
        "limit": user.max_contracts_per_day,
        "period": "day",
    }


def get_llm_quota(db: Session, user: User) -> Dict[str, Any]:
    if uses_demo_quota(user):
        token = _demo_token(db, user)
        return {
            "used": user.llm_requests_total or 0,
            "limit": token.max_llm_requests if token else DEFAULT_DEMO_LLM_REQUESTS,
            "period": "demo",
        }

    user.reset_daily_limits()
    return {
        "used": user.llm_requests_today or 0,
        "limit": user.max_llm_requests_per_day,
        "period": "day",
    }


def contract_limit_message(limit: int, period: str) -> str:
    if period == "demo":
        return f"Лимит персонального демо-доступа ({limit}) исчерпан. Оставьте запрос на рабочий доступ."
    return f"Дневной лимит загрузки ({limit}) исчерпан. Попробуйте завтра."
