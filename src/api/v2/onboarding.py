# -*- coding: utf-8 -*-
"""
API v2 — Guided Onboarding

Эндпоинты для первого знакомства пользователя с системой:
- GET  /onboarding/status   — статус onboarding текущего пользователя
- POST /onboarding/start    — создать демо-NDA и запустить анализ
- POST /onboarding/complete — пометить onboarding завершённым
"""
import os
import shutil

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.api.dependencies import get_current_user
from src.api.v2.dependencies import OrganizationContext, get_org_context
from src.models.database import get_db
from src.models import Contract
from src.models.auth_models import User

router = APIRouter(prefix="/onboarding", tags=["Onboarding"])

DEMO_NDA_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..", "..", "data", "demo", "nda_demo.txt"
)
UPLOAD_DIR = "data/contracts"


class OnboardingStatusResponse(BaseModel):
    onboarding_completed: bool
    demo_contract_id: str | None = None


class OnboardingStartResponse(BaseModel):
    contract_id: str
    file_name: str
    message: str


# ──────────────────────────────────────────────
# GET /onboarding/status
# ──────────────────────────────────────────────
@router.get(
    "/status",
    response_model=OnboardingStatusResponse,
    summary="Статус онбординга",
)
async def onboarding_status(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> OnboardingStatusResponse:
    """Проверить, прошёл ли пользователь onboarding."""
    demo_contract = (
        db.query(Contract)
        .filter(
            Contract.assigned_to == current_user.id,
            Contract.document_type == "demo",
        )
        .first()
    )
    return OnboardingStatusResponse(
        onboarding_completed=bool(current_user.onboarding_completed),
        demo_contract_id=demo_contract.id if demo_contract else None,
    )


# ──────────────────────────────────────────────
# POST /onboarding/start
# ──────────────────────────────────────────────
@router.post(
    "/start",
    response_model=OnboardingStartResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Запустить онбординг с демо-NDA",
)
async def start_onboarding(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    ctx: OrganizationContext | None = Depends(get_org_context),
) -> OnboardingStartResponse:
    """
    Создаёт демо-контракт (NDA) для пользователя и возвращает его ID.
    Повторный вызов возвращает уже созданный демо-контракт.
    """
    # Идемпотентность: если демо-NDA уже есть — вернуть его
    existing = (
        db.query(Contract)
        .filter(
            Contract.assigned_to == current_user.id,
            Contract.document_type == "demo",
        )
        .first()
    )
    if existing:
        return OnboardingStartResponse(
            contract_id=existing.id,
            file_name=existing.file_name,
            message="Демо-NDA уже создан",
        )

    # Копируем демо-NDA в uploads
    src_path = os.path.normpath(DEMO_NDA_PATH)
    if not os.path.isfile(src_path):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Демо-шаблон NDA не найден на сервере",
        )

    safe_name = f"demo_nda_{current_user.id[:8]}.txt"
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    dest_path = os.path.join(UPLOAD_DIR, safe_name)
    shutil.copy2(src_path, dest_path)

    contract = Contract(
        file_name=safe_name,
        file_path=dest_path,
        document_type="demo",
        contract_type="nda",
        status="uploaded",
        assigned_to=current_user.id,
        organization_id=ctx.org.id if ctx else None,
        meta_info={
            "demo": True,
            "template": "nda_demo",
            "parties": "ООО «Альфа Технологии» / ООО «Бета Консалтинг»",
        },
    )
    db.add(contract)
    db.commit()
    db.refresh(contract)

    return OnboardingStartResponse(
        contract_id=contract.id,
        file_name=safe_name,
        message="Демо-NDA создан. Теперь запустите анализ через POST /api/contracts/{id}/analyze",
    )


# ──────────────────────────────────────────────
# POST /onboarding/complete
# ──────────────────────────────────────────────
@router.post(
    "/complete",
    status_code=status.HTTP_200_OK,
    summary="Завершить онбординг",
)
async def complete_onboarding(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """Пометить onboarding завершённым для текущего пользователя."""
    current_user.onboarding_completed = True
    db.commit()
    return {"status": "completed", "message": "Онбординг завершён"}
