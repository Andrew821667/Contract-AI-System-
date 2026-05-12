# -*- coding: utf-8 -*-
"""
Counterparties CRUD + Lookup API.

Контрагент — внешняя сторона договора. Привязывается к организации (тенант).
В legacy-режиме (без X-Organization-Id) фильтр по created_by.
"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from loguru import logger
from sqlalchemy import or_
from sqlalchemy.orm import Session

from src.api.dependencies import get_current_user
from src.api.v2.dependencies import OrganizationContext, get_org_context
from src.models import Contract, ContractParty
from src.models.auth_models import User
from src.models.counterparty_models import (
    COUNTERPARTY_STATUSES,
    COUNTERPARTY_TYPES,
    Counterparty,
)
from src.models.database import get_db
from src.services.counterparty_service import CounterpartyService

from .schemas import (
    CounterpartyContractItem,
    CounterpartyContractsResponse,
    CounterpartyCreate,
    CounterpartyListResponse,
    CounterpartyLookupRequest,
    CounterpartyLookupResponse,
    CounterpartyResponse,
    CounterpartyUpdate,
)

router = APIRouter()


# ─── helpers ────────────────────────────────────────────────────────────────


def _scope_query(query, current_user: User, ctx: Optional[OrganizationContext]):
    """Применить tenant/owner фильтр.

    - С ctx: только записи этой организации.
    - Без ctx: legacy-режим — записи, созданные текущим пользователем,
      либо с organization_id IS NULL.
    - Platform admin (user.role == 'admin') без ctx видит всё.
    """
    if ctx is not None:
        return query.filter(Counterparty.organization_id == ctx.org.id)
    if current_user.role == "admin":
        return query
    return query.filter(
        or_(
            Counterparty.created_by == current_user.id,
            Counterparty.organization_id.is_(None),
        )
    )


def _get_or_404(
    counterparty_id: str,
    db: Session,
    current_user: User,
    ctx: Optional[OrganizationContext],
) -> Counterparty:
    query = db.query(Counterparty).filter(Counterparty.id == counterparty_id)
    cp = _scope_query(query, current_user, ctx).first()
    if not cp:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Контрагент не найден"
        )
    return cp


def _validate_type(value: str) -> None:
    if value not in COUNTERPARTY_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Недопустимый тип. Разрешены: {', '.join(COUNTERPARTY_TYPES)}",
        )


def _validate_status(value: str) -> None:
    if value not in COUNTERPARTY_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Недопустимый статус. Разрешены: {', '.join(COUNTERPARTY_STATUSES)}",
        )


def _check_inn_unique(
    db: Session,
    organization_id: Optional[str],
    inn: Optional[str],
    exclude_id: Optional[str] = None,
) -> None:
    if not inn:
        return
    q = db.query(Counterparty).filter(
        Counterparty.inn == inn,
        Counterparty.organization_id == organization_id,
    )
    if exclude_id:
        q = q.filter(Counterparty.id != exclude_id)
    if q.first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Контрагент с ИНН {inn} уже существует в этой организации",
        )


# ─── routes ─────────────────────────────────────────────────────────────────


@router.get("", response_model=CounterpartyListResponse)
async def list_counterparties(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    search: Optional[str] = Query(None, description="Поиск по названию/ИНН/ОГРН"),
    cp_type: Optional[str] = Query(None, alias="type"),
    cp_status: Optional[str] = Query(None, alias="status"),
    current_user: User = Depends(get_current_user),
    ctx: Optional[OrganizationContext] = Depends(get_org_context),
    db: Session = Depends(get_db),
):
    """Список контрагентов (текущей организации или, в legacy-режиме, текущего пользователя)."""
    query = db.query(Counterparty)
    query = _scope_query(query, current_user, ctx)

    if cp_status:
        query = query.filter(Counterparty.status == cp_status)
    else:
        query = query.filter(Counterparty.status != "archived")

    if cp_type:
        query = query.filter(Counterparty.type == cp_type)

    if search:
        safe = search.replace("%", r"\%").replace("_", r"\_")
        like = f"%{safe}%"
        query = query.filter(
            or_(
                Counterparty.name.ilike(like, escape="\\"),
                Counterparty.short_name.ilike(like, escape="\\"),
                Counterparty.inn.ilike(like, escape="\\"),
                Counterparty.ogrn.ilike(like, escape="\\"),
            )
        )

    total = query.count()
    rows = (
        query.order_by(Counterparty.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    return CounterpartyListResponse(
        counterparties=[CounterpartyResponse(**c.to_dict()) for c in rows],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/types")
async def get_types(current_user: User = Depends(get_current_user)):
    """Допустимые типы контрагентов."""
    labels = {
        "legal": "Юридическое лицо",
        "individual": "Физическое лицо",
        "individual_entrepreneur": "Индивидуальный предприниматель",
        "foreign": "Иностранное лицо",
        "other": "Прочее",
    }
    return [{"value": t, "label": labels.get(t, t)} for t in COUNTERPARTY_TYPES]


@router.post(
    "", response_model=CounterpartyResponse, status_code=status.HTTP_201_CREATED
)
async def create_counterparty(
    data: CounterpartyCreate,
    current_user: User = Depends(get_current_user),
    ctx: Optional[OrganizationContext] = Depends(get_org_context),
    db: Session = Depends(get_db),
):
    """Создать контрагента вручную."""
    _validate_type(data.type)

    organization_id = ctx.org.id if ctx else None
    _check_inn_unique(db, organization_id, data.inn)

    cp = Counterparty(
        organization_id=organization_id,
        created_by=current_user.id,
        type=data.type,
        status="active",
        name=data.name,
        short_name=data.short_name,
        inn=data.inn,
        kpp=data.kpp,
        ogrn=data.ogrn,
        legal_address=data.legal_address,
        postal_address=data.postal_address,
        contact_person=data.contact_person,
        contact_email=data.contact_email,
        contact_phone=data.contact_phone,
        bank_details=data.bank_details,
        notes=data.notes,
        meta_info=data.meta_info,
    )
    db.add(cp)
    db.commit()
    db.refresh(cp)

    logger.info(f"Counterparty created: {cp.id} by user {current_user.id}")
    return CounterpartyResponse(**cp.to_dict())


@router.post("/lookup", response_model=CounterpartyLookupResponse)
async def lookup_counterparty(
    data: CounterpartyLookupRequest,
    current_user: User = Depends(get_current_user),
    ctx: Optional[OrganizationContext] = Depends(get_org_context),
    db: Session = Depends(get_db),
):
    """
    Lookup контрагента по ИНН через ФНС/Федресурс с опциональным сохранением.

    Если save=true и контрагент уже существует в текущей организации —
    обновляются поля fns_data/bankruptcy_data, остальные не перезаписываются.
    """
    service = CounterpartyService()
    check = service.check_counterparty(data.inn, check_bankruptcy=data.check_bankruptcy)

    cp_payload = None
    saved = False

    if data.save and check.get("fns_data", {}).get("found"):
        organization_id = ctx.org.id if ctx else None
        cp = service.get_or_create_by_inn(
            db=db,
            inn=data.inn,
            organization_id=organization_id,
            created_by=current_user.id,
            fns_check_result=check,
        )
        if cp:
            cp_payload = CounterpartyResponse(**cp.to_dict())
            saved = True

    return CounterpartyLookupResponse(
        counterparty=cp_payload,
        fns_data=check.get("fns_data", {}),
        bankruptcy_data=check.get("bankruptcy_data", {}),
        overall_status=check.get("overall_status", "unknown"),
        warnings=check.get("warnings", []),
        errors=check.get("errors", []),
        saved=saved,
    )


@router.get("/{counterparty_id}", response_model=CounterpartyResponse)
async def get_counterparty(
    counterparty_id: str,
    current_user: User = Depends(get_current_user),
    ctx: Optional[OrganizationContext] = Depends(get_org_context),
    db: Session = Depends(get_db),
):
    cp = _get_or_404(counterparty_id, db, current_user, ctx)
    payload = cp.to_dict()
    payload["contracts_count"] = _count_contracts_for_counterparty(db, cp)
    return CounterpartyResponse(**payload)


@router.patch("/{counterparty_id}", response_model=CounterpartyResponse)
async def update_counterparty(
    counterparty_id: str,
    data: CounterpartyUpdate,
    current_user: User = Depends(get_current_user),
    ctx: Optional[OrganizationContext] = Depends(get_org_context),
    db: Session = Depends(get_db),
):
    cp = _get_or_404(counterparty_id, db, current_user, ctx)

    update = data.model_dump(exclude_unset=True)
    if "type" in update:
        _validate_type(update["type"])
    if "status" in update:
        _validate_status(update["status"])
    if "inn" in update and update["inn"] != cp.inn:
        _check_inn_unique(db, cp.organization_id, update["inn"], exclude_id=cp.id)

    for key, value in update.items():
        setattr(cp, key, value)

    db.commit()
    db.refresh(cp)
    logger.info(f"Counterparty updated: {cp.id}")
    return CounterpartyResponse(**cp.to_dict())


@router.delete("/{counterparty_id}")
async def archive_counterparty(
    counterparty_id: str,
    hard: bool = Query(False, description="Удалить физически (только админ)"),
    current_user: User = Depends(get_current_user),
    ctx: Optional[OrganizationContext] = Depends(get_org_context),
    db: Session = Depends(get_db),
):
    """Архивировать контрагента (по умолчанию soft-delete)."""
    cp = _get_or_404(counterparty_id, db, current_user, ctx)

    if hard:
        if current_user.role != "admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Физическое удаление доступно только администратору",
            )
        db.delete(cp)
        db.commit()
        logger.info(f"Counterparty hard-deleted: {counterparty_id}")
        return {"ok": True, "message": "Контрагент удалён"}

    cp.status = "archived"
    db.commit()
    logger.info(f"Counterparty archived: {cp.id}")
    return {"ok": True, "message": "Контрагент архивирован"}


@router.get(
    "/{counterparty_id}/contracts", response_model=CounterpartyContractsResponse
)
async def list_counterparty_contracts(
    counterparty_id: str,
    current_user: User = Depends(get_current_user),
    ctx: Optional[OrganizationContext] = Depends(get_org_context),
    db: Session = Depends(get_db),
):
    """Список договоров, привязанных к этому контрагенту через contract_parties."""
    cp = _get_or_404(counterparty_id, db, current_user, ctx)
    items = _fetch_contracts_for_counterparty(db, cp)
    return CounterpartyContractsResponse(
        counterparty_id=cp.id,
        total=len(items),
        contracts=items,
    )


def _count_contracts_for_counterparty(db: Session, cp: Counterparty) -> int:
    return (
        db.query(Contract)
        .join(ContractParty, ContractParty.contract_id == Contract.id)
        .filter(ContractParty.counterparty_id == cp.id)
        .filter(Contract.status != "deleted")
        .count()
    )


def _fetch_contracts_for_counterparty(db: Session, cp: Counterparty):
    rows = (
        db.query(Contract)
        .join(ContractParty, ContractParty.contract_id == Contract.id)
        .filter(ContractParty.counterparty_id == cp.id)
        .filter(Contract.status != "deleted")
        .order_by(Contract.created_at.desc())
        .all()
    )
    return [
        CounterpartyContractItem(
            id=c.id,
            file_name=c.file_name,
            contract_type=c.contract_type,
            document_type=c.document_type,
            status=c.status,
            created_at=c.created_at.isoformat() if c.created_at else None,
        )
        for c in rows
    ]
