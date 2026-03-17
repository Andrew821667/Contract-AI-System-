"""
Webhook Service — отправка webhooks для внешних интеграций.
"""

from __future__ import annotations

import hashlib
import hmac
import ipaddress
import json
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse

from loguru import logger
from sqlalchemy.orm import Session

from .models import IntegrationConfig, WebhookDelivery

# Запрещённые диапазоны для SSRF-защиты
_BLOCKED_NETWORKS = [
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("169.254.0.0/16"),  # link-local
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),  # unique-local
    ipaddress.ip_network("fe80::/10"),  # link-local v6
]


def _validate_webhook_url(url: str) -> None:
    """
    Валидация URL для защиты от SSRF.

    Запрещает:
    - Не-http(s) схемы
    - Приватные/локальные IP-адреса
    - localhost
    """
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise ValueError(f"Недопустимая схема URL: {parsed.scheme}")

    hostname = parsed.hostname
    if not hostname:
        raise ValueError("URL не содержит hostname")

    # Проверяем известные локальные имена
    if hostname.lower() in ("localhost", "0.0.0.0", "[::]"):
        raise ValueError(f"Недопустимый hostname: {hostname}")

    # Пробуем разрешить как IP
    try:
        addr = ipaddress.ip_address(hostname)
        for network in _BLOCKED_NETWORKS:
            if addr in network:
                raise ValueError(
                    f"Webhook URL указывает на приватный/локальный адрес: {hostname}"
                )
    except ValueError as e:
        if "приватный" in str(e) or "Недопустимый" in str(e) or "Недопустимая" in str(e):
            raise
        # Не IP-адрес — это доменное имя, пропускаем проверку IP
        pass


class WebhookService:
    """Сервис отправки webhooks."""

    def __init__(self, db: Session) -> None:
        self.db = db

    async def dispatch(self, event_type: str, payload: dict[str, Any], org_id: str | None = None) -> list[WebhookDelivery]:
        """Отправить webhook всем подписанным интеграциям."""
        configs = self._get_active_configs(org_id)
        deliveries: list[WebhookDelivery] = []

        for config in configs:
            delivery = WebhookDelivery(
                config_id=config.id,
                event_type=event_type,
                payload=payload,
                status="pending",
            )
            self.db.add(delivery)
            self.db.flush()

            success = await self._send(config, delivery)
            deliveries.append(delivery)

        self.db.flush()
        return deliveries

    async def retry_failed(self, limit: int = 50) -> int:
        """Повторить неудавшиеся доставки."""
        pending = (
            self.db.query(WebhookDelivery)
            .filter(
                WebhookDelivery.status == "failed",
                WebhookDelivery.attempts < WebhookDelivery.max_attempts,
            )
            .limit(limit)
            .all()
        )

        retried = 0
        for delivery in pending:
            config = self.db.query(IntegrationConfig).filter(
                IntegrationConfig.id == delivery.config_id
            ).first()
            if config and config.active:
                await self._send(config, delivery)
                retried += 1

        self.db.flush()
        return retried

    def _get_active_configs(self, org_id: str | None) -> list[IntegrationConfig]:
        """Получить активные webhook конфигурации."""
        query = self.db.query(IntegrationConfig).filter(
            IntegrationConfig.integration_type == "webhook",
            IntegrationConfig.active.is_(True),
        )
        if org_id:
            from sqlalchemy import or_
            query = query.filter(or_(
                IntegrationConfig.org_id == org_id,
                IntegrationConfig.org_id.is_(None),
            ))
        return query.all()

    async def _send(self, config: IntegrationConfig, delivery: WebhookDelivery) -> bool:
        """Отправить один webhook."""
        url = (config.config or {}).get("url")
        secret = (config.config or {}).get("secret")

        if not url:
            delivery.status = "failed"
            delivery.response_body = "No URL configured"
            return False

        # SSRF protection: валидация URL
        try:
            _validate_webhook_url(url)
        except ValueError as e:
            delivery.status = "failed"
            delivery.response_body = f"URL validation failed: {e}"
            logger.warning(f"Webhook SSRF blocked: {url} — {e}")
            return False

        delivery.attempts += 1
        delivery.last_attempt_at = datetime.now(timezone.utc)

        try:
            import httpx

            headers: dict[str, str] = {"Content-Type": "application/json"}

            # HMAC подпись если есть secret
            body = json.dumps(delivery.payload, default=str)
            if secret:
                signature = hmac.new(
                    secret.encode(),
                    body.encode(),
                    hashlib.sha256,
                ).hexdigest()
                headers["X-Webhook-Signature"] = f"sha256={signature}"

            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(url, content=body, headers=headers)

            delivery.response_code = response.status_code
            delivery.response_body = response.text[:500] if response.text else None

            if 200 <= response.status_code < 300:
                delivery.status = "delivered"
                delivery.delivered_at = datetime.now(timezone.utc)
                return True
            else:
                delivery.status = "failed"
                return False

        except Exception as exc:
            delivery.status = "failed"
            delivery.response_body = str(exc)[:500]
            logger.error(f"Webhook delivery failed: {exc}")
            return False
