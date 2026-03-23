# -*- coding: utf-8 -*-
"""
Admin Contract Routes — deletion with audit logging
"""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from loguru import logger

from src.models.database import get_db, Contract
from src.models.auth_models import User
from src.api.dependencies import get_current_user


router = APIRouter(tags=["Admin Contracts"])


class DeleteContractRequest(BaseModel):
    reason: str = Field(..., min_length=5, max_length=1000,
                        description="Причина удаления (обязательно)")


class DeleteContractResponse(BaseModel):
    contract_id: str
    status: str
    message: str
    deleted_by: str
    deleted_at: str
    reason: str


@router.delete(
    "/{contract_id}",
    response_model=DeleteContractResponse,
    summary="Удалить документ (только для админа)",
)
async def delete_contract(
    contract_id: str,
    body: DeleteContractRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Мягкое удаление документа (status='deleted') с обязательным логированием причины.
    Только для пользователей с ролью admin.
    История удаления сохраняется в meta_info документа.
    """
    # Admin only
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Удаление документов доступно только администраторам",
        )

    contract = db.query(Contract).filter(Contract.id == contract_id).first()
    if not contract:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Документ не найден",
        )

    if contract.status == "deleted":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Документ уже удалён",
        )

    now = datetime.now(timezone.utc)

    # Save deletion audit in meta_info
    meta = contract.meta_info or {}
    if not isinstance(meta, dict):
        import json
        meta = json.loads(meta) if meta else {}

    meta["_deletion_audit"] = {
        "deleted_by_id": current_user.id,
        "deleted_by_email": current_user.email,
        "deleted_at": now.isoformat(),
        "reason": body.reason,
        "previous_status": contract.status,
        "file_name": contract.file_name,
    }

    contract.status = "deleted"
    contract.meta_info = meta
    contract.updated_at = now

    db.commit()

    logger.info(
        f"Contract {contract_id} ({contract.file_name}) deleted by "
        f"{current_user.email}: {body.reason}"
    )

    return DeleteContractResponse(
        contract_id=contract_id,
        status="deleted",
        message="Документ успешно удалён",
        deleted_by=current_user.email,
        deleted_at=now.isoformat(),
        reason=body.reason,
    )
