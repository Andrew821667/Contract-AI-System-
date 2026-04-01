# -*- coding: utf-8 -*-
"""
Clause Library API Routes
Browse, search, and inspect extracted clauses
"""
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from loguru import logger

from src.models.database import get_db
from src.models.auth_models import User
from src.api.contracts.routes import get_current_user
from src.services.clause_library_service import ClauseLibraryService


class ClauseCreateRequest(BaseModel):
    contract_id: Optional[str] = None
    title: str
    text: str
    clause_type: str = 'general'
    risk_level: str = 'none'
    tags: Optional[List[str]] = None


class ClauseUpdateRequest(BaseModel):
    title: Optional[str] = None
    text: Optional[str] = None
    clause_type: Optional[str] = None
    risk_level: Optional[str] = None
    tags: Optional[List[str]] = None


router = APIRouter()


@router.post("")
async def create_clause(
    data: ClauseCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create a new clause manually."""
    try:
        # If contract_id provided, verify ownership
        if data.contract_id:
            from src.models import Contract
            contract = db.query(Contract).filter(Contract.id == data.contract_id).first()
            if not contract:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Договор не найден")
            if current_user.role != "admin" and contract.assigned_to != current_user.id:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Нет доступа к договору")

        service = ClauseLibraryService(db)
        result = service.create_clause(data.model_dump())
        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating clause: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Ошибка создания условия",
        )


@router.get("")
async def list_clauses(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    clause_type: Optional[str] = None,
    risk_level: Optional[str] = None,
    contract_id: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    List clauses with pagination and filters.

    **Filters:**
    - clause_type: financial, temporal, liability, termination, confidentiality, etc.
    - risk_level: critical, high, medium, low, none
    - contract_id: Filter by specific contract
    """
    try:
        service = ClauseLibraryService(db)
        filters = {}
        if clause_type:
            filters['clause_type'] = clause_type
        if risk_level:
            filters['risk_level'] = risk_level
        if contract_id:
            filters['contract_id'] = contract_id

        # SECURITY: filter by current user's contracts only (admins see all)
        if current_user.role != "admin":
            filters['user_id'] = current_user.id

        return service.get_library(filters=filters, page=page, page_size=page_size)

    except Exception as e:
        logger.error(f"Error listing clauses: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


@router.get("/stats")
async def get_clause_stats(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get clause library statistics: counts by type, risk level, etc."""
    try:
        service = ClauseLibraryService(db)
        user_id = None if current_user.role == "admin" else current_user.id
        return service.get_stats(user_id=user_id)

    except Exception as e:
        logger.error(f"Error getting clause stats: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


@router.get("/search")
async def search_clauses(
    q: str = Query(..., min_length=2, description="Search query"),
    clause_type: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Search clauses by text content with optional type filter."""
    try:
        service = ClauseLibraryService(db)
        user_id = None if current_user.role == "admin" else current_user.id
        return service.search(
            query=q,
            clause_type=clause_type,
            page=page,
            page_size=page_size,
            user_id=user_id
        )

    except Exception as e:
        logger.error(f"Error searching clauses: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


@router.get("/{clause_id}")
async def get_clause_details(
    clause_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get clause details including full LLM analysis."""
    try:
        service = ClauseLibraryService(db)
        clause = service.get_clause(clause_id)

        if not clause:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Clause not found"
            )

        # IDOR fix: проверяем, что условие принадлежит контракту текущего пользователя
        if current_user.role != "admin":
            from src.models.database import Contract
            contract_id = clause.get("contract_id") if isinstance(clause, dict) else getattr(clause, "contract_id", None)
            if contract_id:
                contract = db.query(Contract).filter(Contract.id == contract_id).first()
                if not contract or contract.assigned_to != current_user.id:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="Нет доступа к данному условию"
                    )

        return clause

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting clause {clause_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


def _check_clause_ownership(clause_id: str, current_user: User, db: Session):
    """Check that user owns the contract this clause belongs to."""
    from src.models.clause_models import ExtractedClause
    from src.models import Contract

    clause = db.query(ExtractedClause).filter(ExtractedClause.id == clause_id).first()
    if not clause:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Условие не найдено")

    if current_user.role != "admin":
        contract = db.query(Contract).filter(Contract.id == clause.contract_id).first()
        if not contract or contract.assigned_to != current_user.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Нет доступа")

    return clause


@router.put("/{clause_id}")
async def update_clause(
    clause_id: str,
    data: ClauseUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update clause title, text, type, risk level, or tags."""
    try:
        _check_clause_ownership(clause_id, current_user, db)

        service = ClauseLibraryService(db)
        update_data = data.model_dump(exclude_none=True)
        if not update_data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Нет данных для обновления",
            )

        result = service.update_clause(clause_id, update_data)
        if not result:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Условие не найдено")
        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating clause {clause_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Ошибка обновления",
        )


@router.delete("/{clause_id}")
async def delete_clause(
    clause_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Delete a clause from the library."""
    try:
        _check_clause_ownership(clause_id, current_user, db)

        service = ClauseLibraryService(db)
        deleted = service.delete_clause(clause_id)
        if not deleted:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Условие не найдено")
        return {"ok": True, "message": "Условие удалено"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting clause {clause_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Ошибка удаления",
        )
