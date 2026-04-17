# -*- coding: utf-8 -*-
"""
API v2 — Playbook Library

Библиотека готовых наборов условий компании по индустриям.
- GET  /playbooks          — список доступных playbook-пакетов
- GET  /playbooks/{id}     — детали конкретного playbook
- POST /playbooks/{id}/apply — применить playbook к аккаунту (создать CompanyCondition записи)
"""
import json
import os
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from src.api.dependencies import get_current_user
from src.api.v2.dependencies import OrganizationContext, get_org_context
from src.models.database import get_db
from src.models.auth_models import User
from src.models.condition_models import CompanyCondition

router = APIRouter(prefix="/playbooks", tags=["Playbook Library"])

PLAYBOOKS_DIR = os.path.join(
    os.path.dirname(__file__), "..", "..", "..", "data", "playbooks"
)


def _load_playbooks() -> list[dict[str, Any]]:
    """Загрузить все playbook-файлы из data/playbooks/."""
    playbooks = []
    pb_dir = os.path.normpath(PLAYBOOKS_DIR)
    if not os.path.isdir(pb_dir):
        return playbooks
    for fname in sorted(os.listdir(pb_dir)):
        if not fname.endswith(".json"):
            continue
        with open(os.path.join(pb_dir, fname), "r", encoding="utf-8") as f:
            playbooks.append(json.load(f))
    return playbooks


def _find_playbook(playbook_id: str) -> dict[str, Any] | None:
    for pb in _load_playbooks():
        if pb["id"] == playbook_id:
            return pb
    return None


# ── Response models ──────────────────────────────

class PlaybookSummary(BaseModel):
    id: str
    name: str
    description: str
    industry: str
    conditions_count: int


class PlaybookConditionItem(BaseModel):
    category: str
    title: str
    description: str | None = None
    condition_text: str
    priority: int


class PlaybookDetail(BaseModel):
    id: str
    name: str
    description: str
    industry: str
    conditions: list[PlaybookConditionItem]


class ApplyResult(BaseModel):
    playbook_id: str
    applied_count: int
    skipped_count: int
    message: str


# ──────────────────────────────────────────────
# GET /playbooks
# ──────────────────────────────────────────────
@router.get(
    "",
    response_model=list[PlaybookSummary],
    summary="Список playbook-пакетов",
)
async def list_playbooks() -> list[PlaybookSummary]:
    """Возвращает список доступных playbook-пакетов без деталей условий."""
    playbooks = _load_playbooks()
    return [
        PlaybookSummary(
            id=pb["id"],
            name=pb["name"],
            description=pb["description"],
            industry=pb["industry"],
            conditions_count=len(pb.get("conditions", [])),
        )
        for pb in playbooks
    ]


# ──────────────────────────────────────────────
# GET /playbooks/{playbook_id}
# ──────────────────────────────────────────────
@router.get(
    "/{playbook_id}",
    response_model=PlaybookDetail,
    summary="Детали playbook-пакета",
)
async def get_playbook(playbook_id: str) -> PlaybookDetail:
    """Возвращает полное содержимое playbook-пакета с условиями."""
    pb = _find_playbook(playbook_id)
    if not pb:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Playbook не найден",
        )
    return PlaybookDetail(
        id=pb["id"],
        name=pb["name"],
        description=pb["description"],
        industry=pb["industry"],
        conditions=[
            PlaybookConditionItem(**c)
            for c in pb.get("conditions", [])
        ],
    )


# ──────────────────────────────────────────────
# POST /playbooks/{playbook_id}/apply
# ──────────────────────────────────────────────
@router.post(
    "/{playbook_id}/apply",
    response_model=ApplyResult,
    status_code=status.HTTP_201_CREATED,
    summary="Применить playbook к аккаунту",
)
async def apply_playbook(
    playbook_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    ctx: OrganizationContext | None = Depends(get_org_context),
) -> ApplyResult:
    """
    Создаёт CompanyCondition записи из playbook для текущего пользователя.
    Пропускает условия, если у пользователя уже есть условие с таким же title.
    """
    pb = _find_playbook(playbook_id)
    if not pb:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Playbook не найден",
        )

    # Собираем существующие titles для дедупликации
    existing_titles = set(
        row[0]
        for row in db.query(CompanyCondition.title)
        .filter(CompanyCondition.user_id == current_user.id, CompanyCondition.is_active.is_(True))
        .all()
    )

    applied = 0
    skipped = 0
    for cond in pb.get("conditions", []):
        if cond["title"] in existing_titles:
            skipped += 1
            continue
        record = CompanyCondition(
            user_id=current_user.id,
            category=cond["category"],
            title=cond["title"],
            description=cond.get("description"),
            condition_text=cond["condition_text"],
            priority=cond.get("priority", 1),
            is_active=True,
        )
        db.add(record)
        applied += 1

    db.commit()

    return ApplyResult(
        playbook_id=playbook_id,
        applied_count=applied,
        skipped_count=skipped,
        message=f"Применено {applied} условий из playbook «{pb['name']}»"
        + (f" (пропущено {skipped} дубликатов)" if skipped else ""),
    )
