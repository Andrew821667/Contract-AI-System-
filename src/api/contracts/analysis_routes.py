# -*- coding: utf-8 -*-
"""
Contract Analysis Routes

Analysis runs in RQ workers (separate process), not in gunicorn.
Progress is tracked via contract.meta_info in DB and exposed via WebSocket polling.
"""
import json
import re
import uuid
from datetime import datetime
from typing import Any, List, Optional
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, status
from loguru import logger
from redis import Redis
from rq import Queue
from sse_starlette.sse import EventSourceResponse
from sqlalchemy.orm import Session

from config.settings import settings
from src.api.dependencies import get_current_user
from src.models import Contract
from src.models.auth_models import User
from src.models.database import get_db
from src.services.document_parser import DocumentParser
from src.services.llm_gateway import LLMGateway
from src.utils.xml_security import parse_xml_safely

from .schemas import (
    AnalysisResultRequest,
    AnalysisResultResponse,
    BatchAnalysisRequest,
    BatchAnalysisResponse,
)


router = APIRouter()


ROLE_LABELS = {
    "supplier": "Поставщик",
    "buyer": "Покупатель",
    "seller": "Продавец",
    "customer": "Заказчик",
    "executor": "Исполнитель",
    "contractor": "Подрядчик",
    "client": "Клиент",
    "patient": "Пациент",
    "clinic": "Клиника",
    "employer": "Работодатель",
    "employee": "Работник",
    "landlord": "Арендодатель",
    "tenant": "Арендатор",
    "lender": "Займодавец",
    "borrower": "Заемщик",
    "party": "Сторона",
    "unknown": "Сторона",
}


def _get_analysis_queue() -> Queue:
    """Get RQ analysis queue (Redis connection from settings)."""
    redis_conn = Redis.from_url(settings.redis_url)
    return Queue("analysis", connection=redis_conn)


def _load_meta(meta: Any) -> dict[str, Any]:
    if isinstance(meta, dict):
        return meta
    if isinstance(meta, str) and meta:
        try:
            loaded = json.loads(meta)
            return loaded if isinstance(loaded, dict) else {}
        except Exception:
            return {}
    return {}


def _normalize_for_match(value: Optional[str]) -> str:
    if not value:
        return ""
    return re.sub(r"[^a-zа-я0-9]+", "", value.lower(), flags=re.IGNORECASE)


def _humanize_role(role: Optional[str]) -> str:
    role_key = (role or "unknown").strip().lower()
    return ROLE_LABELS.get(role_key, role.replace("_", " ").title() if role else "Сторона")


def _build_party_label(role: Optional[str], name: Optional[str]) -> str:
    role_label = _humanize_role(role)
    clean_name = (name or "").strip()
    if clean_name and _normalize_for_match(clean_name) != _normalize_for_match(role_label):
        return f"{role_label}: {clean_name}"
    return role_label


def _extract_party_candidates(parsed_xml: str) -> List[str]:
    """Extract human-readable party options for perspective selection."""
    candidates: List[str] = []
    seen: set[str] = set()

    def add_candidate(label: Optional[str]) -> None:
        clean = (label or "").strip()
        key = _normalize_for_match(clean)
        if clean and key and key not in seen:
            seen.add(key)
            candidates.append(clean)

    try:
        root = parse_xml_safely(parsed_xml)

        for party in root.findall('.//party'):
            add_candidate(
                _build_party_label(
                    party.get('role') or party.findtext('role', ''),
                    party.findtext('name', ''),
                )
            )

        sample_parts = root.xpath('.//clauses/clause[position() <= 3]//paragraph/text()')
        sample_text = ' '.join(part.strip() for part in sample_parts if part and part.strip())[:6000]

        # Patterns like: ООО "...", именуемое в дальнейшем «Исполнитель»
        entity_role_pattern = re.compile(
            r'([^,\n]{3,160}?)\s*,\s*именуем(?:ый|ая|ое|ые)?\s+в\s+дальнейшем\s+[«\"]([^»\"]+)[»\"]',
            re.IGNORECASE,
        )
        for match in entity_role_pattern.finditer(sample_text):
            name = re.sub(r'\s+', ' ', match.group(1)).strip(' .')
            role = re.sub(r'\s+', ' ', match.group(2)).strip(' .')
            add_candidate(_build_party_label(role, name))

        # Patterns like: именуемый в дальнейшем "Пациент"
        role_only_pattern = re.compile(
            r'именуем(?:ый|ая|ое|ые)?\s+в\s+дальнейшем\s+[«\"]([^»\"]+)[»\"]',
            re.IGNORECASE,
        )
        for match in role_only_pattern.finditer(sample_text):
            add_candidate(match.group(1).strip())

        keyword_labels = [
            (r'\bисполнитель\b', 'Исполнитель'),
            (r'\bзаказчик\b', 'Заказчик'),
            (r'\bподрядчик\b', 'Подрядчик'),
            (r'\bпоставщик\b', 'Поставщик'),
            (r'\bпокупатель\b', 'Покупатель'),
            (r'\bпродавец\b', 'Продавец'),
            (r'\bпациент\b', 'Пациент'),
            (r'\bклиник[аи]\b', 'Клиника'),
            (r'\bарендодатель\b', 'Арендодатель'),
            (r'\bарендатор\b', 'Арендатор'),
            (r'\bработодатель\b', 'Работодатель'),
            (r'\bработник\b', 'Работник'),
        ]
        lowered = sample_text.lower()
        for pattern, label in keyword_labels:
            if re.search(pattern, lowered):
                add_candidate(label)

    except Exception as exc:
        logger.warning(f"Failed to extract party candidates: {exc}")

    return candidates


def _match_user_perspective(current_user: User, party_candidates: List[str]) -> Optional[str]:
    """Best-effort attempt to infer user's side automatically."""
    tokens = []
    for raw in [current_user.name, current_user.email.split('@')[0] if current_user.email else ""]:
        for token in re.split(r"[^a-zа-я0-9]+", raw.lower() if raw else ""):
            token = token.strip()
            if len(token) >= 3:
                tokens.append(token)

    if not tokens:
        return None

    for candidate in party_candidates:
        normalized_candidate = _normalize_for_match(candidate)
        if any(token in normalized_candidate for token in tokens):
            return candidate

    return None


def _resolve_analysis_perspective(
    contract: Contract,
    request_data: AnalysisResultRequest,
    current_user: User,
) -> str:
    explicit = (request_data.analysis_perspective or "").strip()
    if explicit:
        return explicit

    meta = _load_meta(contract.meta_info)
    cached = (meta.get("analysis_perspective") or "").strip()
    if cached:
        return cached

    parser = DocumentParser()
    parsed_xml = parser.parse(contract.file_path)
    if not parsed_xml:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Не удалось подготовить договор для выбора стороны анализа.",
        )

    party_candidates = _extract_party_candidates(parsed_xml)
    matched = _match_user_perspective(current_user, party_candidates)
    if matched:
        return matched

    raise HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail={
            "code": "analysis_perspective_required",
            "message": "Не удалось автоматически определить, в чьих интересах выполнять анализ. Укажите сторону перед запуском.",
            "parties": party_candidates,
        },
    )


def _current_analysis_date() -> str:
    return datetime.now(ZoneInfo("Europe/Moscow")).date().isoformat()


@router.post("/analyze", response_model=AnalysisResultResponse)
async def analyze_contract(
    request_data: AnalysisResultRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Analyze an uploaded contract.

    Enqueues analysis as an RQ job and requires a user-oriented perspective.
    If the user's side cannot be inferred, the client must ask which side's
    interests should be protected before the job is queued.
    """
    try:
        current_user.reset_daily_limits()

        if current_user.llm_requests_today >= current_user.max_llm_requests_per_day:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Дневной лимит LLM-запросов ({current_user.max_llm_requests_per_day}) исчерпан.",
            )

        contract = db.query(Contract).filter(Contract.id == request_data.contract_id).first()
        if not contract:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Contract not found",
            )

        if contract.assigned_to != current_user.id and current_user.role not in ["admin"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have permission to analyze this contract",
            )

        if contract.status in {"analyzing", "parsing"}:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Анализ уже запущен для этого договора",
            )

        max_concurrent_per_user = 3
        active_count = db.query(Contract).filter(
            Contract.assigned_to == current_user.id,
            Contract.status.in_(["analyzing", "parsing"]),
        ).count()
        if active_count >= max_concurrent_per_user:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Максимум {max_concurrent_per_user} одновременных анализа. Дождитесь завершения текущих.",
            )

        analysis_perspective = _resolve_analysis_perspective(contract, request_data, current_user)
        analysis_date = _current_analysis_date()

        q = _get_analysis_queue()
        job = q.enqueue(
            "src.tasks.analysis.run_analysis",
            contract_id=request_data.contract_id,
            user_id=current_user.id,
            check_counterparty=request_data.check_counterparty,
            counterparty_tin=request_data.counterparty_tin,
            analysis_perspective=analysis_perspective,
            analysis_date=analysis_date,
            job_timeout="30m",
        )

        current_user.llm_requests_today = (current_user.llm_requests_today or 0) + 1
        db.commit()

        logger.info(
            f"Analysis enqueued for contract {request_data.contract_id} "
            f"by user {current_user.id}, perspective={analysis_perspective}, job_id={job.id}"
        )

        return AnalysisResultResponse(
            analysis_id=request_data.contract_id,
            contract_id=request_data.contract_id,
            status="analyzing",
            risks_count=0,
            recommendations_count=0,
            message=(
                f"Анализ запущен на дату {analysis_date} в интересах стороны: {analysis_perspective}. "
                "Следите за прогрессом через WebSocket /ws/analysis/{contract_id}."
            ),
        )

    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"Error enqueuing analysis: {exc}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error starting analysis",
        )


@router.post("/{contract_id}/analyze/cancel")
async def cancel_analysis(
    contract_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Cancel a running analysis by resetting contract status to uploaded."""
    contract = db.query(Contract).filter(Contract.id == contract_id).first()
    if not contract:
        raise HTTPException(status_code=404, detail="Contract not found")

    if contract.assigned_to != current_user.id and current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Forbidden")

    if contract.status not in ("analyzing", "parsing"):
        raise HTTPException(status_code=409, detail="Анализ не запущен")

    contract.status = "uploaded"
    db.commit()
    logger.info(f"Analysis cancelled for contract {contract_id} by user {current_user.id}")
    return {"ok": True, "message": "Анализ остановлен"}


@router.post("/{contract_id}/analyze/stream")
async def analyze_contract_stream(
    contract_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Streaming contract analysis via Server-Sent Events (SSE).
    Sends incremental analysis results as they are generated.
    """
    contract = db.query(Contract).filter(Contract.id == contract_id).first()
    if not contract:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Contract not found")

    if contract.assigned_to != current_user.id and current_user.role not in ["admin"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No permission")

    parsed_xml = _load_meta(contract.meta_info).get("xml")
    if not parsed_xml:
        parser = DocumentParser()
        try:
            parsed_xml = parser.parse(contract.file_path)
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Document parse error",
            )

    async def event_generator():
        try:
            yield {"event": "status", "data": json.dumps({"status": "started", "contract_id": contract_id})}

            llm = LLMGateway(model=settings.llm_quick_model)
            system_prompt = (
                "You are a contract analysis expert specializing in Russian contract law. "
                "Analyze the following contract clauses and provide risk assessment in Russian."
            )

            yield {"event": "status", "data": json.dumps({"status": "analyzing"})}

            collected = []
            async for chunk in llm.stream(
                prompt=f"Проанализируй договор и выяви риски:\n\n{parsed_xml[:8000]}",
                system_prompt=system_prompt,
            ):
                collected.append(chunk)
                yield {"event": "chunk", "data": json.dumps({"text": chunk})}

            full_text = "".join(collected)
            yield {"event": "done", "data": json.dumps({"status": "completed", "full_text": full_text})}

        except Exception as exc:
            logger.error(f"Streaming analysis error: {exc}", exc_info=True)
            yield {"event": "error", "data": json.dumps({"error": "Ошибка анализа. Попробуйте снова."})}

    return EventSourceResponse(event_generator())


@router.post("/analyze/batch", response_model=BatchAnalysisResponse)
async def batch_analyze_contracts(
    request_data: BatchAnalysisRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Batch analysis — enqueues each contract as a separate RQ job.
    Each job can be retried and monitored independently.
    """
    contract_ids = request_data.contract_ids
    contracts = db.query(Contract).filter(Contract.id.in_(contract_ids)).all()

    if len(contracts) != len(contract_ids):
        found = {c.id for c in contracts}
        missing = [cid for cid in contract_ids if cid not in found]
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Contracts not found: {missing}",
        )

    for contract in contracts:
        if contract.assigned_to != current_user.id and current_user.role not in ["admin"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"No permission for contract {contract.id}",
            )

    task_id = str(uuid.uuid4())
    q = _get_analysis_queue()
    analysis_date = _current_analysis_date()

    for contract_id in contract_ids:
        q.enqueue(
            "src.tasks.analysis.run_analysis",
            contract_id=contract_id,
            user_id=current_user.id,
            check_counterparty=request_data.check_counterparty,
            analysis_perspective=request_data.analysis_perspective,
            analysis_date=analysis_date,
            job_timeout="30m",
        )

    logger.info(f"Batch analysis: enqueued {len(contract_ids)} jobs, task_id={task_id}")

    return BatchAnalysisResponse(
        task_id=task_id,
        total=len(contract_ids),
        status="started",
        message=f"Batch analysis started for {len(contract_ids)} contracts. Track via /ws/batch/{task_id}",
    )
