# -*- coding: utf-8 -*-
"""
Contract Listing Routes

Uses async DB sessions (asyncpg) when available for non-blocking queries.
Falls back to sync sessions on SQLite (dev mode).
"""
import os
import time
from typing import Optional, Any

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy import select, func, or_, and_
from loguru import logger

from src.models.database import get_async_db, AsyncSessionLocal
from src.models import Contract, AnalysisResult
from src.models.auth_models import User
from src.api.dependencies import get_current_user

from .schemas import ContractListResponse


# ── Contract list cache (30s TTL) ────────────────────────────────────────
# Short-lived cache to reduce DB load when many users refresh the list page.
_LIST_CACHE_TTL = 30
_list_cache: dict[str, tuple[Any, float]] = {}
_LIST_CACHE_MAX = 128


def _list_cache_key(user_id, page, page_size, status_f, type_f, search, cursor) -> str:
    return f"{user_id}:{page}:{page_size}:{status_f}:{type_f}:{search}:{cursor}"


def _list_cache_get(key: str) -> Any | None:
    entry = _list_cache.get(key)
    if entry and entry[1] > time.time():
        return entry[0]
    _list_cache.pop(key, None)
    return None


def _list_cache_set(key: str, data: Any) -> None:
    if len(_list_cache) >= _LIST_CACHE_MAX:
        now = time.time()
        expired = [k for k, v in _list_cache.items() if v[1] <= now]
        for k in expired:
            del _list_cache[k]
    _list_cache[key] = (data, time.time() + _LIST_CACHE_TTL)


router = APIRouter()

# Check if we're in async mode (PostgreSQL) or sync fallback (SQLite)
_ASYNC_MODE = AsyncSessionLocal is not None


@router.get("", response_model=ContractListResponse)
async def list_contracts(
    page: int = 1,
    page_size: int = 20,
    status: Optional[str] = None,
    contract_type: Optional[str] = None,
    search: Optional[str] = None,
    cursor: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db=Depends(get_async_db)
):
    """
    List contracts for current user

    **Filters:**
    - status: uploaded, analyzing, completed, error
    - contract_type: supply, service, lease, etc.

    **Pagination:**
    - Offset mode (default): use `page` + `page_size`
    - Cursor mode (faster for deep pages): pass `cursor` from previous response's `next_cursor`

    **Returns:** Paginated list of contracts
    """
    try:
        # Cap page_size
        if page_size > 100:
            page_size = 100
        if page < 1:
            page = 1

        # Check cache (30s TTL)
        cache_key = _list_cache_key(
            current_user.id, page, page_size, status, contract_type, search, cursor
        )
        cached = _list_cache_get(cache_key)
        if cached:
            return cached

        # Build query using SQLAlchemy 2.0 select() style (works with both sync and async)
        stmt = select(Contract)

        # Filter by user (non-admins can only see their own contracts)
        if current_user.role not in ['admin']:
            stmt = stmt.where(Contract.assigned_to == current_user.id)

        # Apply filters (exclude deleted by default)
        if status:
            stmt = stmt.where(Contract.status == status)
        else:
            stmt = stmt.where(Contract.status != 'deleted')
        if contract_type:
            stmt = stmt.where(Contract.contract_type == contract_type)
        if search:
            safe_search = search.replace('%', r'\%').replace('_', r'\_')
            stmt = stmt.where(
                Contract.file_name.ilike(f'%{safe_search}%', escape='\\')
            )

        # Get total count
        count_stmt = select(func.count()).select_from(stmt.subquery())

        if _ASYNC_MODE:
            total_result = await db.execute(count_stmt)
            total = total_result.scalar()
        else:
            total = db.execute(count_stmt).scalar()

        # Paginate — cursor-based if cursor provided, else offset
        if cursor:
            # Cursor is "created_at:id" for keyset pagination (O(1) vs O(N) for offset)
            try:
                cursor_ts, cursor_id = cursor.rsplit(":", 1)
                from datetime import datetime
                cursor_dt = datetime.fromisoformat(cursor_ts)
                stmt = stmt.where(
                    or_(
                        Contract.created_at < cursor_dt,
                        and_(Contract.created_at == cursor_dt, Contract.id < cursor_id)
                    )
                )
            except (ValueError, TypeError):
                pass  # Invalid cursor — fall through to normal ordering

            stmt = stmt.order_by(Contract.created_at.desc(), Contract.id.desc()).limit(page_size)
        else:
            # Offset mode for backward compat
            stmt = stmt.order_by(Contract.created_at.desc()).offset((page - 1) * page_size).limit(page_size)

        if _ASYNC_MODE:
            result = await db.execute(stmt)
            contracts = result.scalars().all()
        else:
            contracts = db.execute(stmt).scalars().all()

        # Format response
        contracts_data = []
        for contract in contracts:
            contracts_data.append({
                'id': contract.id,
                'file_name': contract.file_name,
                'status': contract.status,
                'contract_type': contract.contract_type,
                'created_at': contract.created_at.isoformat() if contract.created_at else None,
                'updated_at': contract.updated_at.isoformat() if contract.updated_at else None
            })

        # Build next_cursor for keyset pagination
        next_cursor = None
        if contracts_data and len(contracts_data) == page_size:
            last = contracts[-1]
            if last.created_at:
                next_cursor = f"{last.created_at.isoformat()}:{last.id}"

        result = ContractListResponse(
            contracts=contracts_data,
            total=total,
            page=page,
            page_size=page_size,
            next_cursor=next_cursor,
        )
        _list_cache_set(cache_key, result)
        return result

    except Exception as e:
        logger.error(f"Error listing contracts: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


@router.get("/{contract_id}")
async def get_contract_details(
    contract_id: str,
    current_user: User = Depends(get_current_user),
    db=Depends(get_async_db)
):
    """Get contract details including analysis results"""
    try:
        stmt = select(Contract).where(Contract.id == contract_id)

        if _ASYNC_MODE:
            result = await db.execute(stmt)
            contract = result.scalar_one_or_none()
        else:
            contract = db.execute(stmt).scalar_one_or_none()

        if not contract:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Contract not found"
            )

        # Check ownership
        if contract.assigned_to != current_user.id and current_user.role not in ['admin']:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have permission to view this contract"
            )

        # Get analysis results if available
        analysis_stmt = select(AnalysisResult).where(AnalysisResult.contract_id == contract_id)

        if _ASYNC_MODE:
            analysis_result = await db.execute(analysis_stmt)
            analysis = analysis_result.scalar_one_or_none()
        else:
            analysis = db.execute(analysis_stmt).scalar_one_or_none()

        return {
            'contract': {
                'id': contract.id,
                'file_name': contract.file_name,
                'status': contract.status,
                'contract_type': contract.contract_type,
                'created_at': contract.created_at.isoformat() if contract.created_at else None,
                'updated_at': contract.updated_at.isoformat() if contract.updated_at else None,
            },
            'analysis': {
                'id': analysis.id if analysis else None,
                'risks': analysis.risks_by_category if analysis else [],
                'recommendations': analysis.recommendations if analysis else [],
                'status': analysis.status if analysis else None
            } if analysis else None
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting contract details: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


@router.get("/{contract_id}/download")
async def download_contract(
    contract_id: str,
    current_user: User = Depends(get_current_user),
    db=Depends(get_async_db)
):
    """Download original contract file"""
    try:
        stmt = select(Contract).where(Contract.id == contract_id)

        if _ASYNC_MODE:
            result = await db.execute(stmt)
            contract = result.scalar_one_or_none()
        else:
            contract = db.execute(stmt).scalar_one_or_none()

        if not contract:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Contract not found"
            )

        # Check ownership
        if contract.assigned_to != current_user.id and current_user.role not in ['admin']:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have permission to download this contract"
            )

        if not os.path.exists(contract.file_path):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Contract file not found on disk"
            )

        return FileResponse(
            path=contract.file_path,
            filename=contract.file_name,
            media_type='application/octet-stream'
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error downloading contract: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )
