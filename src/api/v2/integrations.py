# -*- coding: utf-8 -*-
"""
API v2 — Integrations

Управление webhooks, просмотр domain events, повтор доставок.
"""
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from src.api.dependencies import get_current_user
from src.api.v2.dependencies import verify_org_membership
from src.models.database import get_db, generate_uuid
from src.models.auth_models import User
from src.core.integrations.models import IntegrationConfig, WebhookDelivery, DomainEvent
from src.core.integrations.schemas import DomainEventRead, WebhookDeliveryRead
from src.core.integrations.event_types import ALL_EVENT_TYPES

router = APIRouter(prefix="/integrations", tags=["Integrations"])


# ── Pydantic schemas ─────────────────────────────────────────────


class EventTypeInfo(BaseModel):
    name: str
    entity_type: str
    description: str
    severity: str


class WebhookConfigCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    url: str = Field(..., min_length=1, max_length=2000)
    secret: str | None = Field(None, max_length=500)
    event_filter: list[str] | None = Field(None, max_length=100)
    org_id: str | None = Field(None, max_length=50)


class WebhookConfigRead(BaseModel):
    id: str
    name: str
    integration_type: str
    config: dict
    active: bool
    org_id: str | None

    model_config = {"from_attributes": True}

    def model_post_init(self, __context: object) -> None:
        """Скрываем webhook secret из API-ответов."""
        if isinstance(self.config, dict) and "secret" in self.config:
            self.config = {**self.config, "secret": "***"}


class RetryResult(BaseModel):
    retried: int


# ──────────────────────────────────────────────
# GET /integrations/events
# ──────────────────────────────────────────────
@router.get(
    "/events",
    response_model=List[DomainEventRead],
    summary="Список domain events с фильтрами",
)
async def list_events(
    entity_type: str | None = Query(None, description="Тип сущности"),
    entity_id: str | None = Query(None, description="ID сущности"),
    event_type: str | None = Query(None, description="Тип события"),
    limit: int = Query(50, ge=1, le=500, description="Лимит записей"),
    offset: int = Query(0, ge=0, description="Смещение"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Возвращает историю domain events с возможностью фильтрации."""
    # AuthZ: только admin видит все events
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Просмотр domain events доступен только администраторам",
        )
    query = db.query(DomainEvent)
    if entity_type:
        query = query.filter(DomainEvent.entity_type == entity_type)
    if entity_id:
        query = query.filter(DomainEvent.entity_id == entity_id)
    if event_type:
        query = query.filter(DomainEvent.event_type == event_type)
    return query.order_by(DomainEvent.created_at.desc()).offset(offset).limit(limit).all()


# ──────────────────────────────────────────────
# GET /integrations/events/types
# ──────────────────────────────────────────────
@router.get(
    "/events/types",
    response_model=List[EventTypeInfo],
    summary="Все зарегистрированные типы событий",
)
async def list_event_types(
    current_user: User = Depends(get_current_user),
):
    """Возвращает каталог всех зарегистрированных типов событий с метаданными."""
    return [
        EventTypeInfo(
            name=et.name,
            entity_type=et.entity_type,
            description=et.description,
            severity=et.severity,
        )
        for et in ALL_EVENT_TYPES.values()
    ]


# ──────────────────────────────────────────────
# POST /integrations/webhooks
# ──────────────────────────────────────────────
@router.post(
    "/webhooks",
    response_model=WebhookConfigRead,
    status_code=status.HTTP_201_CREATED,
    summary="Создать webhook конфигурацию",
)
async def create_webhook(
    body: WebhookConfigCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Создаёт новую webhook конфигурацию для получения событий."""
    # AuthZ: только admin или org_admin может создавать webhooks
    if current_user.role != "admin":
        if not body.org_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Требуется указать org_id или быть администратором платформы",
            )
        verify_org_membership(body.org_id, current_user, db)

    # SSRF protection: валидация URL при создании
    from src.core.integrations.webhook_service import _validate_webhook_url
    try:
        _validate_webhook_url(body.url)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Недопустимый URL: {e}",
        )

    config = IntegrationConfig(
        id=generate_uuid(),
        integration_type="webhook",
        name=body.name,
        config={
            "url": body.url,
            "secret": body.secret,
            "event_filter": body.event_filter,
        },
        org_id=body.org_id,
        active=True,
    )
    db.add(config)
    db.commit()
    db.refresh(config)
    return config


# ──────────────────────────────────────────────
# GET /integrations/webhooks
# ──────────────────────────────────────────────
@router.get(
    "/webhooks",
    response_model=List[WebhookConfigRead],
    summary="Список webhook конфигураций",
)
async def list_webhooks(
    org_id: str | None = Query(None, description="Фильтр по организации"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Возвращает список webhook конфигураций."""
    # AuthZ: non-admin видит только webhooks своих организаций
    if current_user.role != "admin" and org_id:
        verify_org_membership(org_id, current_user, db)

    query = db.query(IntegrationConfig).filter(
        IntegrationConfig.integration_type == "webhook",
    )
    if org_id:
        query = query.filter(IntegrationConfig.org_id == org_id)
    elif current_user.role != "admin":
        # Non-admin без org_id — пустой список (нельзя видеть все webhooks)
        return []
    return query.order_by(IntegrationConfig.created_at.desc()).all()


# ──────────────────────────────────────────────
# DELETE /integrations/webhooks/{config_id}
# ──────────────────────────────────────────────
@router.delete(
    "/webhooks/{config_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Деактивировать webhook",
)
async def deactivate_webhook(
    config_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Деактивирует webhook конфигурацию (soft delete)."""
    # AuthZ: проверяем, что пользователь имеет доступ
    if current_user.role != "admin":
        existing = db.query(IntegrationConfig).filter(
            IntegrationConfig.id == config_id,
        ).first()
        if existing and existing.org_id:
            verify_org_membership(existing.org_id, current_user, db)
        elif existing:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Только администратор может деактивировать глобальные webhooks",
            )

    config = db.query(IntegrationConfig).filter(
        IntegrationConfig.id == config_id,
        IntegrationConfig.integration_type == "webhook",
    ).first()
    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Webhook конфигурация с id={config_id} не найдена",
        )
    config.active = False
    db.commit()


# ──────────────────────────────────────────────
# GET /integrations/webhooks/{config_id}/deliveries
# ──────────────────────────────────────────────
@router.get(
    "/webhooks/{config_id}/deliveries",
    response_model=List[WebhookDeliveryRead],
    summary="Лог доставок для webhook",
)
async def list_deliveries(
    config_id: str,
    limit: int = Query(50, ge=1, le=500, description="Лимит записей"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Возвращает историю доставок для указанной webhook конфигурации."""
    config = db.query(IntegrationConfig).filter(
        IntegrationConfig.id == config_id,
        IntegrationConfig.integration_type == "webhook",
    ).first()
    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Webhook конфигурация с id={config_id} не найдена",
        )
    return (
        db.query(WebhookDelivery)
        .filter(WebhookDelivery.config_id == config_id)
        .order_by(WebhookDelivery.created_at.desc())
        .limit(limit)
        .all()
    )


# ──────────────────────────────────────────────
# POST /integrations/webhooks/retry
# ──────────────────────────────────────────────
@router.post(
    "/webhooks/retry",
    response_model=RetryResult,
    summary="Повторить неудавшиеся доставки",
)
async def retry_failed_deliveries(
    limit: int = Query(50, ge=1, le=200, description="Макс. количество повторов"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Повторяет отправку неудавшихся webhook доставок."""
    # AuthZ: только admin может повторять доставки
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Повтор доставок доступен только администраторам",
        )

    from src.core.integrations.webhook_service import WebhookService

    webhook_service = WebhookService(db)
    retried = await webhook_service.retry_failed(limit=limit)
    db.commit()
    return RetryResult(retried=retried)
