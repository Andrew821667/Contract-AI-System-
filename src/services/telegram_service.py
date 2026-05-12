# -*- coding: utf-8 -*-
"""Telegram notifications for operational events."""

import os
from pathlib import Path
from html import escape
from typing import Optional

import requests
from loguru import logger
from dotenv import load_dotenv

from src.models.auth_models import User


load_dotenv(Path.cwd() / ".env", override=False)


def _telegram_config() -> tuple[Optional[str], Optional[str]]:
    token = os.getenv("TELEGRAM_BOT_TOKEN") or os.getenv("CONTRACT_AI_TELEGRAM_BOT_TOKEN")
    chat_id = (
        os.getenv("TELEGRAM_ADMIN_CHAT_ID")
        or os.getenv("CONTRACT_AI_TELEGRAM_ADMIN_CHAT_ID")
        or os.getenv("TELEGRAM_CHAT_ID")
    )
    return token, chat_id


def notify_new_user(user_id: str, email: str, name: str, role: str, subscription_tier: str, ip_address: Optional[str] = None) -> None:
    token, chat_id = _telegram_config()
    if not token or not chat_id:
        logger.info("Telegram new-user notification skipped: bot token or chat id is not configured")
        return

    text = (
        "<b>Новый пользователь Contract AI</b>\n"
        f"Email: <code>{escape(email)}</code>\n"
        f"Имя: {escape(name)}\n"
        f"Роль: <code>{escape(role)}</code>\n"
        f"Тариф: <code>{escape(subscription_tier)}</code>\n"
        f"IP: <code>{escape(ip_address or '-')}</code>\n"
        f"ID: <code>{escape(user_id)}</code>"
    )

    try:
        response = requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={
                "chat_id": chat_id,
                "text": text,
                "parse_mode": "HTML",
                "disable_web_page_preview": True,
            },
            timeout=5,
        )
        response.raise_for_status()
        logger.info(f"Telegram new-user notification sent for user {user_id}")
    except Exception as exc:
        logger.warning(f"Telegram new-user notification failed: {exc}")


def notify_new_user_model(user: User, ip_address: Optional[str] = None) -> None:
    notify_new_user(
        user_id=user.id,
        email=user.email,
        name=user.name,
        role=user.role,
        subscription_tier=user.subscription_tier,
        ip_address=ip_address,
    )
