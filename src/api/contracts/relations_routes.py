# -*- coding: utf-8 -*-
"""
Contract Relations & Parties API.

Управление сторонами договора (m2m с counterparties) и связями
parent↔child для производных документов.
"""
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from loguru import logger
from sqlalchemy.orm import Session

from src.api.dependencies import get_contract_with_access_sync, get_current_user
from src.models import Contract, Counterparty
from src.models.auth_models import User
from src.models.contract_relations_models import (
    PARTY_ROLES,
    RELATION_TYPES,
    ContractParty,
    ContractRelation,
    DerivativeVerification,
)
from src.models.database import get_db

from .relations_schemas import (
    ContractBriefRef,
    ContractPartiesResponse,
    ContractPartyCreate,
    ContractPartyResponse,
    ContractPartyUpdate,
    ContractRelatedBundle,
    ContractRelationCreate,
    ContractRelationResponse,
    ContractRelationUpdate,
    ContractRelationsListResponse,
    RelationTypeOption,
)


router = APIRouter()


# ── helpers ─────────────────────────────────────────────────────────────────


_RELATION_LABELS = {
    "supplementary_agreement": (
        "Дополнительное соглашение",
        "Изменяет или дополняет условия основного договора.",
    ),
    "specification": (
        "Спецификация",
        "Расширение условий под отдельный продукт или партию.",
    ),
    "annex": ("Приложение", "Документ, прилагаемый к основному договору."),
    "act": ("Акт", "Акт выполненных работ / приёма-передачи и т.п."),
    "addendum": ("Дополнение", "Прочие дополнения, не изменяющие условий."),
    "termination": ("Соглашение о расторжении", "Прекращает действие основного договора."),
    "custom": ("Свой тип", "Пользовательский тип со свободным промптом."),
}


def _validate_party_role(role: str) -> None:
    if role not in PARTY_ROLES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Недопустимая роль. Разрешены: {', '.join(PARTY_ROLES)}",
        )


def _validate_relation_type(value: str) -> None:
    if value not in RELATION_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Недопустимый тип связи. Разрешены: {', '.join(RELATION_TYPES)}",
        )


def _verify_counterparty_access(
    db: Session, counterparty_id: str, current_user: User, contract: Contract
) -> Counterparty:
    cp = db.query(Counterparty).filter(Counterparty.id == counterparty_id).first()
    if not cp:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Контрагент не найден"
        )
    # Если у контракта есть org — контрагент должен быть из той же org
    # либо legacy (org_id IS NULL).
    if (
        contract.organization_id
        and cp.organization_id
        and cp.organization_id != contract.organization_id
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Контрагент принадлежит другой организации",
        )
    return cp


def _verify_contract_access(
    db: Session, contract_id: str, current_user: User
) -> Contract:
    """Sync-версия проверки доступа к договору (как get_contract_with_access_sync)."""
    contract = db.query(Contract).filter(Contract.id == contract_id).first()
    if not contract:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Договор не найден"
        )
    if contract.assigned_to != current_user.id and current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Нет доступа к договору"
        )
    return contract


def _party_to_response(
    party: ContractParty, db: Session
) -> ContractPartyResponse:
    cp = (
        db.query(Counterparty)
        .filter(Counterparty.id == party.counterparty_id)
        .first()
    )
    return ContractPartyResponse(
        id=party.id,
        contract_id=party.contract_id,
        counterparty_id=party.counterparty_id,
        counterparty_name=cp.name if cp else None,
        counterparty_inn=cp.inn if cp else None,
        role=party.role,
        sequence_number=party.sequence_number,
        notes=party.notes,
        created_at=party.created_at.isoformat() if party.created_at else None,
    )


def _contract_brief(contract: Contract) -> ContractBriefRef:
    return ContractBriefRef(
        id=contract.id,
        file_name=contract.file_name,
        document_type=contract.document_type,
        contract_type=contract.contract_type,
        contract_number=getattr(contract, "contract_number", None),
        contract_date=(
            contract.contract_date.isoformat()
            if getattr(contract, "contract_date", None)
            else None
        ),
        status=contract.status,
        primary_relation_type=getattr(contract, "primary_relation_type", None),
        parties_summary=getattr(contract, "parties_summary", None),
    )


def _relation_to_response(
    rel: ContractRelation, db: Session, include_brief: bool = True
) -> ContractRelationResponse:
    parent_brief = None
    child_brief = None
    if include_brief:
        parent = db.query(Contract).filter(Contract.id == rel.parent_contract_id).first()
        child = db.query(Contract).filter(Contract.id == rel.child_contract_id).first()
        if parent:
            parent_brief = _contract_brief(parent)
        if child:
            child_brief = _contract_brief(child)

    return ContractRelationResponse(
        id=rel.id,
        parent_contract_id=rel.parent_contract_id,
        child_contract_id=rel.child_contract_id,
        relation_type=rel.relation_type,
        custom_label=rel.custom_label,
        custom_prompt=rel.custom_prompt,
        derived_from_text=rel.derived_from_text,
        confidence=rel.confidence,
        auto_detected=rel.auto_detected,
        created_by=rel.created_by,
        created_at=rel.created_at.isoformat() if rel.created_at else None,
        updated_at=rel.updated_at.isoformat() if rel.updated_at else None,
        parent=parent_brief,
        child=child_brief,
    )


def _refresh_primary_relation_type(db: Session, contract: Contract) -> None:
    """Денормализованная синхронизация Contract.primary_relation_type:
    выбираем relation_type первой по дате связи, где contract — child."""
    first_parent_rel = (
        db.query(ContractRelation)
        .filter(ContractRelation.child_contract_id == contract.id)
        .order_by(ContractRelation.created_at.asc())
        .first()
    )
    contract.primary_relation_type = (
        first_parent_rel.relation_type if first_parent_rel else None
    )


def _refresh_parties_summary(db: Session, contract: Contract) -> None:
    """Кэш сторон в Contract.parties_summary для быстрого отображения."""
    rows = (
        db.query(ContractParty, Counterparty)
        .join(Counterparty, ContractParty.counterparty_id == Counterparty.id)
        .filter(ContractParty.contract_id == contract.id)
        .order_by(ContractParty.sequence_number.asc().nulls_last(), ContractParty.created_at.asc())
        .all()
    )
    contract.parties_summary = [
        {
            "counterparty_id": cp.id,
            "name": cp.name,
            "inn": cp.inn,
            "role": party.role,
        }
        for party, cp in rows
    ]


# ── Static metadata routes ─────────────────────────────────────────────────


@router.get("/relation-types", response_model=List[RelationTypeOption])
async def get_relation_types(
    current_user: User = Depends(get_current_user),
):
    """Допустимые типы связей parent↔child."""
    return [
        RelationTypeOption(value=t, label=label, description=description)
        for t, (label, description) in _RELATION_LABELS.items()
    ]


@router.get("/party-roles")
async def get_party_roles(current_user: User = Depends(get_current_user)):
    labels = {
        "counterparty": "Контрагент",
        "guarantor": "Поручитель",
        "third_party": "Третья сторона",
        "other": "Прочее",
    }
    return [{"value": r, "label": labels.get(r, r)} for r in PARTY_ROLES]


# ── Parties endpoints ──────────────────────────────────────────────────────


@router.get(
    "/{contract_id}/parties", response_model=ContractPartiesResponse
)
async def list_contract_parties(
    contract_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    contract = _verify_contract_access(db, contract_id, current_user)
    parties = (
        db.query(ContractParty)
        .filter(ContractParty.contract_id == contract.id)
        .order_by(
            ContractParty.sequence_number.asc().nulls_last(),
            ContractParty.created_at.asc(),
        )
        .all()
    )
    return ContractPartiesResponse(
        contract_id=contract.id,
        parties=[_party_to_response(p, db) for p in parties],
    )


@router.post(
    "/{contract_id}/parties",
    response_model=ContractPartyResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_contract_party(
    contract_id: str,
    data: ContractPartyCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    contract = _verify_contract_access(db, contract_id, current_user)
    _validate_party_role(data.role)
    cp = _verify_counterparty_access(db, data.counterparty_id, current_user, contract)

    # idempotency: если такая роль уже есть — конфликт
    existing = (
        db.query(ContractParty)
        .filter(
            ContractParty.contract_id == contract.id,
            ContractParty.counterparty_id == cp.id,
            ContractParty.role == data.role,
        )
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Этот контрагент уже привязан к договору с такой ролью",
        )

    party = ContractParty(
        contract_id=contract.id,
        counterparty_id=cp.id,
        role=data.role,
        sequence_number=data.sequence_number,
        notes=data.notes,
    )
    db.add(party)
    db.flush()
    _refresh_parties_summary(db, contract)
    db.commit()
    db.refresh(party)

    logger.info(
        f"ContractParty added: contract={contract.id} cp={cp.id} role={data.role}"
    )
    return _party_to_response(party, db)


@router.patch(
    "/{contract_id}/parties/{party_id}", response_model=ContractPartyResponse
)
async def update_contract_party(
    contract_id: str,
    party_id: str,
    data: ContractPartyUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    contract = _verify_contract_access(db, contract_id, current_user)
    party = (
        db.query(ContractParty)
        .filter(ContractParty.id == party_id, ContractParty.contract_id == contract.id)
        .first()
    )
    if not party:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Сторона не найдена"
        )
    update = data.model_dump(exclude_unset=True)
    if "role" in update:
        _validate_party_role(update["role"])
    for key, value in update.items():
        setattr(party, key, value)
    _refresh_parties_summary(db, contract)
    db.commit()
    db.refresh(party)
    return _party_to_response(party, db)


@router.delete("/{contract_id}/parties/{party_id}")
async def remove_contract_party(
    contract_id: str,
    party_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    contract = _verify_contract_access(db, contract_id, current_user)
    party = (
        db.query(ContractParty)
        .filter(ContractParty.id == party_id, ContractParty.contract_id == contract.id)
        .first()
    )
    if not party:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Сторона не найдена"
        )
    db.delete(party)
    db.flush()
    _refresh_parties_summary(db, contract)
    db.commit()
    return {"ok": True, "message": "Сторона отвязана от договора"}


# ── Relations endpoints (parent ↔ child) ───────────────────────────────────


@router.get(
    "/{contract_id}/parents", response_model=List[ContractRelationResponse]
)
async def list_contract_parents(
    contract_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Основные договоры этого документа (если он — производный)."""
    contract = _verify_contract_access(db, contract_id, current_user)
    rows = (
        db.query(ContractRelation)
        .filter(ContractRelation.child_contract_id == contract.id)
        .order_by(ContractRelation.created_at.asc())
        .all()
    )
    return [_relation_to_response(r, db) for r in rows]


@router.get(
    "/{contract_id}/derivatives", response_model=List[ContractRelationResponse]
)
async def list_contract_derivatives(
    contract_id: str,
    relation_type: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Производные документы этого договора, опционально фильтр по типу."""
    contract = _verify_contract_access(db, contract_id, current_user)
    query = db.query(ContractRelation).filter(
        ContractRelation.parent_contract_id == contract.id
    )
    if relation_type:
        _validate_relation_type(relation_type)
        query = query.filter(ContractRelation.relation_type == relation_type)
    rows = query.order_by(
        ContractRelation.relation_type.asc(),
        ContractRelation.created_at.desc(),
    ).all()
    return [_relation_to_response(r, db) for r in rows]


@router.get("/{contract_id}/related", response_model=ContractRelatedBundle)
async def get_contract_related(
    contract_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Сводный объект: parents + derivatives + parties."""
    contract = _verify_contract_access(db, contract_id, current_user)

    parents = (
        db.query(ContractRelation)
        .filter(ContractRelation.child_contract_id == contract.id)
        .order_by(ContractRelation.created_at.asc())
        .all()
    )
    derivatives = (
        db.query(ContractRelation)
        .filter(ContractRelation.parent_contract_id == contract.id)
        .order_by(
            ContractRelation.relation_type.asc(), ContractRelation.created_at.desc()
        )
        .all()
    )
    parties = (
        db.query(ContractParty)
        .filter(ContractParty.contract_id == contract.id)
        .order_by(
            ContractParty.sequence_number.asc().nulls_last(),
            ContractParty.created_at.asc(),
        )
        .all()
    )

    return ContractRelatedBundle(
        contract_id=contract.id,
        parents=[_relation_to_response(r, db) for r in parents],
        derivatives=[_relation_to_response(r, db) for r in derivatives],
        parties=[_party_to_response(p, db) for p in parties],
    )


@router.post(
    "/{contract_id}/relations",
    response_model=ContractRelationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def link_parent(
    contract_id: str,
    data: ContractRelationCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Привязать основной договор к текущему (текущий = child).

    Path contract_id — производный документ, body.parent_contract_id — основной.
    Создаёт ContractRelation. Также проставляет document_type='derivative'
    у child и обновляет primary_relation_type.
    """
    child = _verify_contract_access(db, contract_id, current_user)
    if data.parent_contract_id == child.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Договор не может быть производным от самого себя",
        )

    _validate_relation_type(data.relation_type)
    parent = _verify_contract_access(db, data.parent_contract_id, current_user)

    # custom требует явного label или prompt
    if data.relation_type == "custom" and not (
        (data.custom_label and data.custom_label.strip())
        or (data.custom_prompt and data.custom_prompt.strip())
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Для custom-связи укажите custom_label и/или custom_prompt",
        )

    existing = (
        db.query(ContractRelation)
        .filter(
            ContractRelation.parent_contract_id == parent.id,
            ContractRelation.child_contract_id == child.id,
            ContractRelation.relation_type == data.relation_type,
        )
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Такая связь уже существует",
        )

    rel = ContractRelation(
        parent_contract_id=parent.id,
        child_contract_id=child.id,
        relation_type=data.relation_type,
        custom_label=data.custom_label,
        custom_prompt=data.custom_prompt,
        derived_from_text=data.derived_from_text,
        confidence=data.confidence,
        auto_detected=data.auto_detected,
        created_by=current_user.id,
    )
    db.add(rel)
    db.flush()

    # Маркируем дочерний документ как production document
    if child.document_type == "contract":
        child.document_type = "derivative"
    _refresh_primary_relation_type(db, child)

    db.commit()
    db.refresh(rel)
    logger.info(
        f"ContractRelation created: parent={parent.id} child={child.id} type={data.relation_type}"
    )
    return _relation_to_response(rel, db)


@router.patch(
    "/{contract_id}/relations/{relation_id}",
    response_model=ContractRelationResponse,
)
async def update_relation(
    contract_id: str,
    relation_id: str,
    data: ContractRelationUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    contract = _verify_contract_access(db, contract_id, current_user)
    rel = (
        db.query(ContractRelation)
        .filter(
            ContractRelation.id == relation_id,
            (
                (ContractRelation.parent_contract_id == contract.id)
                | (ContractRelation.child_contract_id == contract.id)
            ),
        )
        .first()
    )
    if not rel:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Связь не найдена"
        )

    update = data.model_dump(exclude_unset=True)
    if "relation_type" in update:
        _validate_relation_type(update["relation_type"])

    for key, value in update.items():
        setattr(rel, key, value)
    db.flush()

    # Если поменяли тип у child-side — обновим primary_relation_type
    child = (
        db.query(Contract)
        .filter(Contract.id == rel.child_contract_id)
        .first()
    )
    if child:
        _refresh_primary_relation_type(db, child)

    db.commit()
    db.refresh(rel)
    return _relation_to_response(rel, db)


@router.post("/{contract_id}/find-parent")
async def find_parent(
    contract_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Найти кандидатов на основной договор для уже загруженного производного.

    Использует Contract.parsed_text если он есть; иначе пытается
    распарсить файл заново. Возвращает top-5 кандидатов с confidence.
    """
    contract = _verify_contract_access(db, contract_id, current_user)

    text = (contract.parsed_text or "").strip()
    if not text:
        # Попытка пере-парсить файл
        try:
            from src.services.document_parser import DocumentParser

            parser = DocumentParser()
            text = parser.parse(contract.file_path) or ""
            if text:
                contract.parsed_text = text[:10_000]
                db.commit()
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"find_parent: parse failed for {contract.id}: {exc}")

    if not text:
        return {
            "contract_id": contract.id,
            "candidates": [],
            "extracted": {},
            "message": "Не удалось извлечь текст из документа для поиска основного договора",
        }

    from src.services.main_contract_finder import (
        MainContractFinderService,
        extract_contract_refs,
    )

    refs = extract_contract_refs(text)
    finder = MainContractFinderService()
    candidates = finder.find_candidates(
        db=db,
        text=text,
        current_user=current_user,
        organization_id=contract.organization_id,
        exclude_contract_id=contract.id,
        limit=5,
    )

    return {
        "contract_id": contract.id,
        "candidates": [
            {
                "contract_id": c.contract_id,
                "file_name": c.file_name,
                "contract_number": c.contract_number,
                "contract_date": c.contract_date,
                "counterparties": c.counterparties,
                "confidence": c.confidence,
                "matched_fields": c.matched_fields,
            }
            for c in candidates
        ],
        "extracted": {
            "numbers": refs.numbers,
            "dates": [d.isoformat() for d in refs.dates],
            "inns": refs.inns,
        },
    }


@router.post("/{contract_id}/verify-against-parent")
async def verify_against_parent(
    contract_id: str,
    relation_id: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Запустить трёхэтапную сверку производного документа с основным.

    Если у документа несколько parent-связей — нужно передать relation_id.
    Если одна — берётся автоматически.
    """
    contract = _verify_contract_access(db, contract_id, current_user)

    query = db.query(ContractRelation).filter(
        ContractRelation.child_contract_id == contract.id
    )
    if relation_id:
        query = query.filter(ContractRelation.id == relation_id)

    relations = query.order_by(ContractRelation.created_at.asc()).all()
    if not relations:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="У документа нет связи с основным договором — сверка невозможна",
        )
    if len(relations) > 1 and not relation_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="У документа несколько основных договоров — укажите relation_id",
        )
    relation = relations[0]

    # Проверяем доступ к parent тоже
    _verify_contract_access(db, relation.parent_contract_id, current_user)

    from src.services.derivative_verification import DerivativeVerificationService

    svc = DerivativeVerificationService()
    verif = svc.verify(db=db, relation=relation, current_user=current_user)
    logger.info(
        f"Verification done: id={verif.id} child={contract.id} overall={verif.overall_assessment}"
    )
    return verif.to_dict()


@router.get("/{contract_id}/verifications")
async def list_verifications(
    contract_id: str,
    relation_id: Optional[str] = None,
    limit: int = 20,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """История сверок: новые сверху."""
    contract = _verify_contract_access(db, contract_id, current_user)

    query = db.query(DerivativeVerification).filter(
        DerivativeVerification.child_contract_id == contract.id
    )
    if relation_id:
        query = query.filter(DerivativeVerification.relation_id == relation_id)

    rows = query.order_by(DerivativeVerification.created_at.desc()).limit(min(limit, 100)).all()
    return {"contract_id": contract.id, "verifications": [v.to_dict() for v in rows]}


@router.delete("/{contract_id}/relations/{relation_id}")
async def unlink_relation(
    contract_id: str,
    relation_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    contract = _verify_contract_access(db, contract_id, current_user)
    rel = (
        db.query(ContractRelation)
        .filter(
            ContractRelation.id == relation_id,
            (
                (ContractRelation.parent_contract_id == contract.id)
                | (ContractRelation.child_contract_id == contract.id)
            ),
        )
        .first()
    )
    if not rel:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Связь не найдена"
        )

    child_id = rel.child_contract_id
    db.delete(rel)
    db.flush()

    child = db.query(Contract).filter(Contract.id == child_id).first()
    if child:
        _refresh_primary_relation_type(db, child)
        # Если у дочернего больше нет parent-связей — откатываем document_type
        remaining = (
            db.query(ContractRelation)
            .filter(ContractRelation.child_contract_id == child.id)
            .count()
        )
        if remaining == 0 and child.document_type == "derivative":
            child.document_type = "contract"

    db.commit()
    return {"ok": True, "message": "Связь удалена"}
