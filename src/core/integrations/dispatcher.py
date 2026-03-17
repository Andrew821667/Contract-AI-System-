"""
Event Dispatcher — автоматическая доставка событий через webhooks.

Подписывается на EventBus как wildcard handler (*),
для каждого события проверяет подписки и запускает webhook delivery.
"""
from __future__ import annotations
from typing import Any

from loguru import logger
from sqlalchemy.orm import Session

from .event_bus import EventBusService
from .webhook_service import WebhookService
from .models import DomainEvent
from .event_types import ALL_EVENT_TYPES


class EventDispatcher:
    """Связующий слой между EventBus и внешними интеграциями."""

    def __init__(
        self,
        db: Session,
        event_bus: EventBusService,
        webhook_service: WebhookService,
    ) -> None:
        self.db = db
        self.event_bus = event_bus
        self.webhook_service = webhook_service
        self._webhook_event_filter: set[str] | None = None  # None = all events

    def setup(self) -> None:
        """Подписаться на все события EventBus."""
        self.event_bus.subscribe("*", self._on_event)
        logger.info("EventDispatcher: subscribed to all events")

    def set_webhook_filter(self, event_types: set[str]) -> None:
        """Ограничить webhook delivery только указанными типами."""
        self._webhook_event_filter = event_types

    async def _on_event(self, event: DomainEvent) -> None:
        """Handler для каждого события — отправляет webhook если нужно."""
        if self._webhook_event_filter is not None:
            if event.event_type not in self._webhook_event_filter:
                return

        event_meta = ALL_EVENT_TYPES.get(event.event_type)

        try:
            await self.webhook_service.dispatch(
                event_type=event.event_type,
                payload={
                    "event_id": event.id,
                    "event_type": event.event_type,
                    "entity_type": event.entity_type,
                    "entity_id": event.entity_id,
                    "payload": event.payload,
                    "severity": event_meta.severity if event_meta else "info",
                    "emitted_by": event.emitted_by,
                    "timestamp": event.created_at.isoformat() if event.created_at else None,
                },
            )
        except Exception as exc:
            logger.error(f"EventDispatcher: webhook dispatch failed for '{event.event_type}': {exc}")
