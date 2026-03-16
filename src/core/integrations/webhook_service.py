"""
Webhook Service — отправка webhooks для внешних интеграций.
"""

from __future__ import annotations

import hashlib
import hmac
import json
from datetime import datetime
from typing import Any

from loguru import logger
from sqlalchemy.orm import Session

from .models import IntegrationConfig, WebhookDelivery


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

        delivery.attempts += 1
        delivery.last_attempt_at = datetime.utcnow()

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
                delivery.delivered_at = datetime.utcnow()
                return True
            else:
                delivery.status = "failed"
                return False

        except Exception as exc:
            delivery.status = "failed"
            delivery.response_body = str(exc)[:500]
            logger.error(f"Webhook delivery failed: {exc}")
            return False
