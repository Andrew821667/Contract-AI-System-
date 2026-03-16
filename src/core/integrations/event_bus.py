"""
Event Bus — публикация и подписка на domain events.

Внутренний event bus для loose coupling между модулями.
"""

from __future__ import annotations

from typing import Any, Callable, Awaitable

from loguru import logger
from sqlalchemy.orm import Session

from .models import DomainEvent


# Тип хэндлера: async def handler(event: DomainEvent) -> None
EventHandler = Callable[[DomainEvent], Awaitable[None]]


class EventBusService:
    """In-process event bus с persistence."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self._handlers: dict[str, list[EventHandler]] = {}

    def subscribe(self, event_type: str, handler: EventHandler) -> None:
        """Подписаться на тип события."""
        if event_type not in self._handlers:
            self._handlers[event_type] = []
        self._handlers[event_type].append(handler)
        logger.debug(f"EventBus: subscribed to '{event_type}'")

    async def emit(
        self,
        event_type: str,
        entity_type: str,
        entity_id: str,
        payload: dict[str, Any] | None = None,
        emitted_by: str | None = None,
    ) -> DomainEvent:
        """Опубликовать событие."""
        event = DomainEvent(
            event_type=event_type,
            entity_type=entity_type,
            entity_id=entity_id,
            payload=payload,
            emitted_by=emitted_by,
        )
        self.db.add(event)
        self.db.flush()

        # Вызвать handlers
        handlers = self._handlers.get(event_type, [])
        # Также wildcard handlers
        handlers += self._handlers.get("*", [])

        for handler in handlers:
            try:
                await handler(event)
            except Exception as exc:
                logger.error(f"EventBus handler error for '{event_type}': {exc}")

        logger.debug(f"EventBus: emitted '{event_type}' ({entity_type}:{entity_id}), {len(handlers)} handlers")
        return event

    def get_events(
        self,
        entity_type: str | None = None,
        entity_id: str | None = None,
        event_type: str | None = None,
        limit: int = 50,
    ) -> list[DomainEvent]:
        """Получить историю событий."""
        query = self.db.query(DomainEvent)
        if entity_type:
            query = query.filter(DomainEvent.entity_type == entity_type)
        if entity_id:
            query = query.filter(DomainEvent.entity_id == entity_id)
        if event_type:
            query = query.filter(DomainEvent.event_type == event_type)
        return query.order_by(DomainEvent.created_at.desc()).limit(limit).all()
