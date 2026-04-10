# -*- coding: utf-8 -*-
"""
Contract Listing Routes

Uses async DB sessions (asyncpg) when available for non-blocking queries.
Falls back to sync sessions on SQLite (dev mode).
"""
import os
import time
from typing import Optional, Any, Dict

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy import select, func, or_, and_
from loguru import logger

from src.models.database import get_async_db, AsyncSessionLocal
from src.models import Contract, AnalysisResult
from src.models.auth_models import User
from src.models.analyzer_models import ContractRisk, ContractRecommendation
from src.api.dependencies import get_current_user, get_contract_with_access

from .schemas import ContractListResponse


_LIST_CACHE_TTL = 10  # Short TTL to reduce staleness across workers
_list_cache: dict[str, tuple[Any, float]] = {}
_LIST_CACHE_MAX = 64


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


from src.api.contracts.utils import load_json_dict as _load_meta
_json_field = _load_meta  # alias for backward compat


router = APIRouter()
_ASYNC_MODE = AsyncSessionLocal is not None


@router.get('', response_model=ContractListResponse)
async def list_contracts(
    page: int = 1,
    page_size: int = 20,
    status: Optional[str] = None,
    contract_type: Optional[str] = None,
    search: Optional[str] = None,
    cursor: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db=Depends(get_async_db),
):
    """List contracts for current user."""
    try:
        if page_size > 100:
            page_size = 100
        if page < 1:
            page = 1

        cache_key = _list_cache_key(
            current_user.id, page, page_size, status, contract_type, search, cursor
        )
        cached = _list_cache_get(cache_key)
        if cached:
            return cached

        stmt = select(Contract)

        if current_user.role not in ['admin']:
            stmt = stmt.where(Contract.assigned_to == current_user.id)

        if status:
            stmt = stmt.where(Contract.status == status)
        else:
            stmt = stmt.where(Contract.status != 'deleted')
        if contract_type:
            stmt = stmt.where(Contract.contract_type == contract_type)
        if search:
            safe_search = search.replace('%', r'\%').replace('_', r'\_')
            stmt = stmt.where(Contract.file_name.ilike(f'%{safe_search}%', escape='\\'))

        count_stmt = select(func.count()).select_from(stmt.subquery())
        if _ASYNC_MODE:
            total_result = await db.execute(count_stmt)
            total = total_result.scalar()
        else:
            total = db.execute(count_stmt).scalar()

        if cursor:
            try:
                cursor_ts, cursor_id = cursor.rsplit(':', 1)
                from datetime import datetime
                cursor_dt = datetime.fromisoformat(cursor_ts)
                stmt = stmt.where(
                    or_(
                        Contract.created_at < cursor_dt,
                        and_(Contract.created_at == cursor_dt, Contract.id < cursor_id),
                    )
                )
            except (ValueError, TypeError):
                pass

            stmt = stmt.order_by(Contract.created_at.desc(), Contract.id.desc()).limit(page_size)
        else:
            stmt = stmt.order_by(Contract.created_at.desc()).offset((page - 1) * page_size).limit(page_size)

        if _ASYNC_MODE:
            result = await db.execute(stmt)
            contracts = result.scalars().all()
        else:
            contracts = db.execute(stmt).scalars().all()

        contracts_data = []
        for contract in contracts:
            contracts_data.append({
                'id': contract.id,
                'file_name': contract.file_name,
                'status': contract.status,
                'contract_type': contract.contract_type,
                'created_at': contract.created_at.isoformat() if contract.created_at else None,
                'updated_at': contract.updated_at.isoformat() if contract.updated_at else None,
            })

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

    except Exception as exc:
        logger.error(f"Error listing contracts: {exc}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail='Internal server error',
        )


@router.get('/{contract_id}')
async def get_contract_details(
    contract: Contract = Depends(get_contract_with_access),
    db=Depends(get_async_db),
):
    """Get contract details including the latest analysis results."""
    try:
        contract_id = contract.id
        # Get latest analysis result if available
        analysis_stmt = (
            select(AnalysisResult)
            .where(AnalysisResult.contract_id == contract_id)
            .order_by(AnalysisResult.created_at.desc(), AnalysisResult.version.desc())
            .limit(1)
        )

        if _ASYNC_MODE:
            analysis_result = await db.execute(analysis_stmt)
            analysis = analysis_result.scalar_one_or_none()
        else:
            analysis = db.execute(analysis_stmt).scalar_one_or_none()

        risks_data = []
        recs_data = []
        required_fields = []
        analysis_context: Dict[str, Any] = {}
        recommendation_summary = {
            'accepted': 0,
            'rejected': 0,
            'pending': 0,
            'total': 0,
        }

        if analysis:
            risks_stmt = select(ContractRisk).where(ContractRisk.analysis_id == analysis.id)
            recs_stmt = select(ContractRecommendation).where(ContractRecommendation.analysis_id == analysis.id)

            if _ASYNC_MODE:
                risks_result = await db.execute(risks_stmt)
                recs_result = await db.execute(recs_stmt)
                risks_rows = risks_result.scalars().all()
                recs_rows = recs_result.scalars().all()
            else:
                risks_rows = db.execute(risks_stmt).scalars().all()
                recs_rows = db.execute(recs_stmt).scalars().all()

            risks_data = [
                {
                    'id': r.id,
                    'risk_type': r.risk_type,
                    'severity': r.severity,
                    'probability': r.probability,
                    'title': r.title,
                    'description': r.description,
                    'consequences': r.consequences,
                    'section_name': r.section_name,
                    'rag_sources': r.rag_sources,
                }
                for r in risks_rows
            ]
            recommendation_meta = _json_field(analysis.recommendations)
            recommendation_workflow = recommendation_meta.get('workflow', {})
            if not isinstance(recommendation_workflow, dict):
                recommendation_workflow = {}

            recs_data = []
            for r in recs_rows:
                decision_payload = recommendation_workflow.get(str(r.id), {})
                recs_data.append({
                    'id': r.id,
                    'category': r.category,
                    'priority': r.priority,
                    'title': r.title,
                    'description': r.description,
                    'reasoning': r.reasoning,
                    'expected_benefit': r.expected_benefit,
                    'implementation_complexity': r.implementation_complexity,
                    'decision': decision_payload.get('decision', 'pending'),
                    'decided_at': decision_payload.get('updated_at'),
                })

            if recs_data:
                recommendation_summary = {
                    'accepted': sum(1 for rec in recs_data if rec.get('decision') == 'accepted'),
                    'rejected': sum(1 for rec in recs_data if rec.get('decision') == 'rejected'),
                    'pending': sum(1 for rec in recs_data if rec.get('decision') not in {'accepted', 'rejected'}),
                    'total': len(recs_data),
                }

            legal_issues = _json_field(analysis.legal_issues)
            entities = _json_field(analysis.entities)
            risk_meta = _json_field(analysis.risks_by_category)

            required_fields = legal_issues.get('required_fields', [])
            analysis_context = entities.get('analysis_context', {})
            if not analysis_context:
                analysis_context = {
                    'analysis_date': risk_meta.get('analysis_date'),
                    'analysis_perspective': risk_meta.get('analysis_perspective'),
                }

        meta = _load_meta(contract.meta_info)
        progress = meta.get('_progress')
        progress_message = meta.get('_progress_msg')

        if progress is None and contract.status == 'completed':
            progress = 100
        if progress_message is None and contract.status == 'completed':
            progress_message = 'Анализ завершен.'
        if progress is None and contract.status == 'error':
            progress = 0
        if progress_message is None and contract.status == 'error':
            progress_message = 'Ошибка анализа'

        return {
            'contract': {
                'id': contract.id,
                'file_name': contract.file_name,
                'status': contract.status,
                'contract_type': contract.contract_type,
                'progress': progress,
                'progress_message': progress_message,
                'created_at': contract.created_at.isoformat() if contract.created_at else None,
                'updated_at': contract.updated_at.isoformat() if contract.updated_at else None,
            },
            'analysis': {
                'id': analysis.id if analysis else None,
                'version': analysis.version if analysis else None,
                'risks': risks_data,
                'recommendations': recs_data,
                'recommendation_summary': recommendation_summary,
                'required_fields': required_fields,
                'analysis_context': analysis_context,
            } if analysis else None,
        }

    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"Error getting contract details: {exc}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail='Internal server error',
        )


@router.get('/{contract_id}/download')
async def download_contract(
    contract: Contract = Depends(get_contract_with_access),
):
    """Download original contract file."""
    try:
        if not os.path.exists(contract.file_path):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail='Contract file not found on disk',
            )

        return FileResponse(
            path=contract.file_path,
            filename=contract.file_name,
            media_type='application/octet-stream',
        )

    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"Error downloading contract: {exc}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail='Internal server error',
        )
