# -*- coding: utf-8 -*-
"""
Contract Listing Routes

Uses async DB sessions (asyncpg) when available for non-blocking queries.
Falls back to sync sessions on SQLite (dev mode).
"""
import os
import time
from collections import defaultdict
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse
from sqlalchemy import select, func, or_, and_, exists
from loguru import logger

from src.models.database import get_async_db, AsyncSessionLocal
from src.models import Contract, AnalysisResult, ContractParty, ContractRelation, Counterparty
from src.models.auth_models import User
from src.models.analyzer_models import ContractRisk, ContractRecommendation
from src.api.dependencies import get_current_user, get_contract_with_access

from .schemas import ContractGroup, ContractListResponse


_LIST_CACHE_TTL = 10
_list_cache: dict[str, tuple[Any, float]] = {}
_LIST_CACHE_MAX = 64


def _list_cache_key(*parts: Any) -> str:
    return "|".join("" if p is None else str(p) for p in parts)


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


def _parse_iso_date(raw: Optional[str]) -> Optional[datetime]:
    if not raw:
        return None
    try:
        # Поддерживаем YYYY-MM-DD и полный ISO
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None


def _contract_to_item(contract: Contract) -> Dict[str, Any]:
    """Сериализация Contract в листинговый item с реквизитами/контрагентом."""
    parties_summary = list(contract.parties_summary or [])
    primary_cp = next(
        (p for p in parties_summary if p.get("role") == "counterparty"),
        parties_summary[0] if parties_summary else None,
    )
    return {
        "id": contract.id,
        "file_name": contract.file_name,
        "status": contract.status,
        "contract_type": contract.contract_type,
        "document_type": contract.document_type,
        "primary_relation_type": getattr(contract, "primary_relation_type", None),
        "contract_number": getattr(contract, "contract_number", None),
        "contract_date": (
            contract.contract_date.isoformat()
            if getattr(contract, "contract_date", None)
            else None
        ),
        "effective_from": (
            contract.effective_from.isoformat()
            if getattr(contract, "effective_from", None)
            else None
        ),
        "effective_to": (
            contract.effective_to.isoformat()
            if getattr(contract, "effective_to", None)
            else None
        ),
        "total_amount": (
            float(contract.total_amount)
            if getattr(contract, "total_amount", None) is not None
            else None
        ),
        "currency": getattr(contract, "currency", None),
        "counterparty": (
            {
                "id": primary_cp.get("counterparty_id"),
                "name": primary_cp.get("name"),
                "inn": primary_cp.get("inn"),
                "role": primary_cp.get("role"),
            }
            if primary_cp
            else None
        ),
        "parties_summary": parties_summary,
        "created_at": contract.created_at.isoformat() if contract.created_at else None,
        "updated_at": contract.updated_at.isoformat() if contract.updated_at else None,
    }


@router.get("", response_model=ContractListResponse)
async def list_contracts(
    page: int = 1,
    page_size: int = 20,
    status: Optional[str] = None,
    contract_type: Optional[str] = None,
    search: Optional[str] = None,
    cursor: Optional[str] = None,
    # Расширенные фильтры (миграции 021/022)
    q: Optional[str] = Query(None, description="Полнотекстовый поиск по содержимому/реквизитам"),
    document_type: Optional[str] = None,
    relation_type: Optional[str] = Query(None, description="Фильтр по primary_relation_type"),
    parent_contract_id: Optional[str] = None,
    counterparty_id: Optional[str] = None,
    counterparty_inn: Optional[str] = None,
    contract_date_from: Optional[str] = None,
    contract_date_to: Optional[str] = None,
    amount_from: Optional[float] = None,
    amount_to: Optional[float] = None,
    currency: Optional[str] = None,
    group_by: Optional[str] = Query(None, description="counterparty | parent"),
    current_user: User = Depends(get_current_user),
    db=Depends(get_async_db),
):
    """Список договоров (текущего пользователя/организации) с расширенными фильтрами.

    - q: полнотекстовый поиск по file_name, contract_number и parsed_text
         (на SQLite — ilike; FTS будет добавлен миграцией 023).
    - group_by='counterparty': возвращает groups сгруппированными по контрагенту.
    - group_by='parent': группировка по основному договору (для производных).
    """
    try:
        if page_size > 100:
            page_size = 100
        if page < 1:
            page = 1

        cache_key = _list_cache_key(
            current_user.id, current_user.role,
            page, page_size, status, contract_type, search, cursor,
            q, document_type, relation_type, parent_contract_id,
            counterparty_id, counterparty_inn,
            contract_date_from, contract_date_to,
            amount_from, amount_to, currency, group_by,
        )
        cached = _list_cache_get(cache_key)
        if cached:
            return cached

        stmt = select(Contract)

        # Tenancy / ownership
        if current_user.role not in ["admin"]:
            stmt = stmt.where(Contract.assigned_to == current_user.id)

        # Status
        if status:
            stmt = stmt.where(Contract.status == status)
        else:
            stmt = stmt.where(Contract.status != "deleted")

        if contract_type:
            stmt = stmt.where(Contract.contract_type == contract_type)
        if document_type:
            stmt = stmt.where(Contract.document_type == document_type)
        if relation_type:
            stmt = stmt.where(Contract.primary_relation_type == relation_type)

        # Поиск по имени файла (legacy совместимость)
        if search:
            safe = search.replace("%", r"\%").replace("_", r"\_")
            stmt = stmt.where(Contract.file_name.ilike(f"%{safe}%", escape="\\"))

        # Полнотекстовый запрос: file_name + contract_number + parsed_text
        if q:
            safe = q.replace("%", r"\%").replace("_", r"\_")
            like = f"%{safe}%"
            stmt = stmt.where(
                or_(
                    Contract.file_name.ilike(like, escape="\\"),
                    Contract.contract_number.ilike(like, escape="\\"),
                    Contract.parsed_text.ilike(like, escape="\\"),
                )
            )

        # Контрагент: явный id или inn (через JOIN ContractParty)
        if counterparty_id:
            stmt = stmt.where(
                exists().where(
                    and_(
                        ContractParty.contract_id == Contract.id,
                        ContractParty.counterparty_id == counterparty_id,
                    )
                )
            )
        if counterparty_inn:
            stmt = stmt.where(
                exists().where(
                    and_(
                        ContractParty.contract_id == Contract.id,
                        ContractParty.counterparty_id == Counterparty.id,
                        Counterparty.inn == counterparty_inn,
                    )
                )
            )

        # Parent: договоры, у которых указанный parent_contract_id среди связей-родителей
        if parent_contract_id:
            stmt = stmt.where(
                exists().where(
                    and_(
                        ContractRelation.child_contract_id == Contract.id,
                        ContractRelation.parent_contract_id == parent_contract_id,
                    )
                )
            )

        # Диапазоны дат и сумм
        date_from = _parse_iso_date(contract_date_from)
        date_to = _parse_iso_date(contract_date_to)
        if date_from:
            stmt = stmt.where(Contract.contract_date >= date_from)
        if date_to:
            stmt = stmt.where(Contract.contract_date <= date_to)
        if amount_from is not None:
            stmt = stmt.where(Contract.total_amount >= amount_from)
        if amount_to is not None:
            stmt = stmt.where(Contract.total_amount <= amount_to)
        if currency:
            stmt = stmt.where(Contract.currency == currency.upper())

        # ── Подсчёт total ───────────────────────────────────────────────────
        count_stmt = select(func.count()).select_from(stmt.subquery())
        if _ASYNC_MODE:
            total_result = await db.execute(count_stmt)
            total = total_result.scalar() or 0
        else:
            total = db.execute(count_stmt).scalar() or 0

        # ── Группировка ─────────────────────────────────────────────────────
        if group_by in ("counterparty", "parent"):
            # При группировке pagination применяем к группам.
            # Сначала забираем достаточный набор контрактов (capped 500),
            # затем строим группы и пагинируем по ним.
            ordered = stmt.order_by(Contract.created_at.desc()).limit(500)
            if _ASYNC_MODE:
                result = await db.execute(ordered)
                contracts = result.scalars().all()
            else:
                contracts = db.execute(ordered).scalars().all()

            items = [_contract_to_item(c) for c in contracts]
            groups = await _build_groups(db, group_by, contracts, items)

            # Pagination on groups
            total_groups = len(groups)
            offset = (page - 1) * page_size
            page_groups = groups[offset : offset + page_size]

            return ContractListResponse(
                contracts=items,  # плоский список, на UI используется при group_by=None
                total=total,
                page=page,
                page_size=page_size,
                next_cursor=None,
                groups=page_groups if page_groups is not None else None,
            )

        # ── Обычный (плоский) список ────────────────────────────────────────
        if cursor:
            try:
                cursor_ts, cursor_id = cursor.rsplit(":", 1)
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
            stmt = (
                stmt.order_by(Contract.created_at.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            )

        if _ASYNC_MODE:
            result = await db.execute(stmt)
            contracts = result.scalars().all()
        else:
            contracts = db.execute(stmt).scalars().all()

        contracts_data = [_contract_to_item(c) for c in contracts]

        next_cursor = None
        if contracts_data and len(contracts_data) == page_size:
            last = contracts[-1]
            if last.created_at:
                next_cursor = f"{last.created_at.isoformat()}:{last.id}"

        response = ContractListResponse(
            contracts=contracts_data,
            total=total,
            page=page,
            page_size=page_size,
            next_cursor=next_cursor,
        )
        _list_cache_set(cache_key, response)
        return response

    except Exception as exc:
        logger.error(f"Error listing contracts: {exc}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


async def _build_groups(
    db,
    group_by: str,
    contracts: List[Contract],
    items: List[Dict[str, Any]],
) -> List[ContractGroup]:
    """Сгруппировать договоры по контрагенту или основному договору."""
    if group_by == "counterparty":
        # ключ — counterparty_id из parties_summary[primary] или None
        groups: Dict[Optional[str], List[Dict[str, Any]]] = defaultdict(list)
        labels: Dict[Optional[str], str] = {}
        meta: Dict[Optional[str], Dict[str, Any]] = {}
        for item in items:
            cp = item.get("counterparty") or {}
            cp_id = cp.get("id")
            groups[cp_id].append(item)
            if cp_id and cp_id not in labels:
                labels[cp_id] = cp.get("name") or "—"
                meta[cp_id] = {"inn": cp.get("inn")}
            elif not cp_id:
                labels[None] = "Без контрагента"

        result_list: List[ContractGroup] = []
        # Сначала с контрагентом, отсортированные по числу договоров
        for cp_id, rows in sorted(
            ((k, v) for k, v in groups.items() if k is not None),
            key=lambda x: -len(x[1]),
        ):
            result_list.append(
                ContractGroup(
                    group_id=cp_id,
                    group_label=labels.get(cp_id, "—"),
                    group_meta=meta.get(cp_id, {}),
                    contracts=rows,
                    total=len(rows),
                )
            )
        if None in groups:
            result_list.append(
                ContractGroup(
                    group_id=None,
                    group_label="Без контрагента",
                    group_meta={},
                    contracts=groups[None],
                    total=len(groups[None]),
                )
            )
        return result_list

    if group_by == "parent":
        # Для каждого contract: ищем parent через ContractRelation
        ids = [c.id for c in contracts]
        parent_map: Dict[str, str] = {}  # child_id -> parent_id (первый по дате)
        parent_labels: Dict[str, str] = {}

        if ids:
            # Загружаем parent_relations пакетом
            rel_stmt = (
                select(ContractRelation)
                .where(ContractRelation.child_contract_id.in_(ids))
                .order_by(ContractRelation.created_at.asc())
            )
            if _ASYNC_MODE:
                rel_result = await db.execute(rel_stmt)
                rels = rel_result.scalars().all()
            else:
                rels = db.execute(rel_stmt).scalars().all()
            for r in rels:
                if r.child_contract_id not in parent_map:
                    parent_map[r.child_contract_id] = r.parent_contract_id

            # Подгружаем имена parent-контрактов
            parent_ids = list(set(parent_map.values()))
            if parent_ids:
                p_stmt = select(Contract).where(Contract.id.in_(parent_ids))
                if _ASYNC_MODE:
                    p_result = await db.execute(p_stmt)
                    parents = p_result.scalars().all()
                else:
                    parents = db.execute(p_stmt).scalars().all()
                for p in parents:
                    parent_labels[p.id] = p.file_name

        groups2: Dict[Optional[str], List[Dict[str, Any]]] = defaultdict(list)
        for item in items:
            pid = parent_map.get(item["id"])
            groups2[pid].append(item)

        result_list: List[ContractGroup] = []
        # Группа "Самостоятельные" (без parent) — отдельно
        for pid, rows in groups2.items():
            if pid is None:
                continue
            result_list.append(
                ContractGroup(
                    group_id=pid,
                    group_label=parent_labels.get(pid, "—"),
                    group_meta={"parent_id": pid},
                    contracts=rows,
                    total=len(rows),
                )
            )
        if None in groups2:
            result_list.append(
                ContractGroup(
                    group_id=None,
                    group_label="Самостоятельные договоры",
                    group_meta={},
                    contracts=groups2[None],
                    total=len(groups2[None]),
                )
            )
        return result_list

    return []


@router.get("/{contract_id}")
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
                'document_type': contract.document_type,
                'primary_relation_type': getattr(contract, 'primary_relation_type', None),
                'contract_number': getattr(contract, 'contract_number', None),
                'contract_date': contract.contract_date.isoformat() if getattr(contract, 'contract_date', None) else None,
                'effective_from': contract.effective_from.isoformat() if getattr(contract, 'effective_from', None) else None,
                'effective_to': contract.effective_to.isoformat() if getattr(contract, 'effective_to', None) else None,
                'total_amount': float(contract.total_amount) if getattr(contract, 'total_amount', None) is not None else None,
                'currency': getattr(contract, 'currency', None),
                'parties_summary': contract.parties_summary or [],
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
