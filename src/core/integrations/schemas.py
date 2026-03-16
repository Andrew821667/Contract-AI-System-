"""Integrations — Pydantic schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel


class DomainEventRead(BaseModel):
    id: str
    event_type: str
    entity_type: str
    entity_id: str
    payload: dict[str, Any] | None
    emitted_by: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class WebhookDeliveryRead(BaseModel):
    id: str
    config_id: str
    event_type: str
    status: str
    response_code: int | None
    attempts: int
    delivered_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}
