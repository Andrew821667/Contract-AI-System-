# -*- coding: utf-8 -*-
"""
Clause Library API Routes
Browse, search, and inspect extracted clauses
"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session

from loguru import logger

from src.models.database import get_db
from src.models.auth_models import User
from src.api.contracts.routes import get_current_user
from src.services.clause_library_service import ClauseLibraryService


router = APIRouter()


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
        return service.get_stats()

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
        return service.search(
            query=q,
            clause_type=clause_type,
            page=page,
            page_size=page_size
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

        # IDOR fix: проверяем, что клаузула принадлежит контракту текущего пользователя
        if current_user.role != "admin":
            from src.models.database import Contract
            contract_id = clause.get("contract_id") if isinstance(clause, dict) else getattr(clause, "contract_id", None)
            if contract_id:
                contract = db.query(Contract).filter(Contract.id == contract_id).first()
                if not contract or contract.assigned_to != current_user.id:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="Нет доступа к данной клаузуле"
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
