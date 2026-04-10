# -*- coding: utf-8 -*-
"""
Contract Analysis Routes
"""
import os
import re
import uuid
from datetime import datetime
from typing import Optional, Dict, List, Any
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sse_starlette.sse import EventSourceResponse
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified
from loguru import logger

from src.models.database import get_db
from src.models import Contract, AnalysisResult
from src.models.auth_models import User
from src.models.analyzer_models import ContractRecommendation
from src.services.document_parser_extended import ExtendedDocumentParser
from src.agents.contract_analyzer_agent import ContractAnalyzerAgent
from src.services.llm_gateway import LLMGateway
from src.services.digital_service import DigitalContractService
from src.services.clause_library_service import ClauseLibraryService
from src.services.clause_extractor import ClauseExtractor
from src.utils.xml_security import parse_xml_safely
from config.settings import settings
from src.api.dependencies import get_current_user, get_contract_with_access_sync

from .schemas import (
    AnalysisResultRequest,
    AnalysisResultResponse,
    BatchAnalysisRequest,
    BatchAnalysisResponse,
    RecommendationDecisionRequest,
    RecommendationDecisionResponse,
)


router = APIRouter()


from src.api.contracts.utils import load_json_dict as _load_meta


def _resolve_analysis_perspective(contract: Contract, request_data: AnalysisResultRequest, current_user: User) -> str:
    explicit = (request_data.analysis_perspective or '').strip()
    if explicit:
        return explicit

    meta = _load_meta(contract.meta_info)
    cached = (meta.get('analysis_perspective') or '').strip()
    if cached:
        return cached

    parser = ExtendedDocumentParser()
    parsed_xml = parser.parse(contract.file_path)
    if not parsed_xml:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail='Не удалось подготовить договор для выбора стороны анализа.',
        )

    def normalize(value: Optional[str]) -> str:
        if not value:
            return ''
        return re.sub(r'[^a-zа-я0-9]+', '', value.lower(), flags=re.IGNORECASE)

    candidates: List[str] = []
    seen: set[str] = set()

    def add_candidate(label: Optional[str]) -> None:
        clean = (label or '').strip()
        key = normalize(clean)
        if clean and key and key not in seen:
            seen.add(key)
            candidates.append(clean)

    try:
        root = parse_xml_safely(parsed_xml)
        for party in root.findall('.//party'):
            role = (party.get('role') or party.findtext('role', '') or '').strip()
            name = (party.findtext('name', '') or '').strip()
            label = f'{role.title()}: {name}' if role and name else role.title() or name
            add_candidate(label)

        sample_parts = root.xpath('.//clauses/clause[position() <= 3]//paragraph/text()')
        sample_text = ' '.join(part.strip() for part in sample_parts if part and part.strip())[:6000].lower()
        for keyword, label in [
            ('исполнитель', 'Исполнитель'),
            ('заказчик', 'Заказчик'),
            ('подрядчик', 'Подрядчик'),
            ('поставщик', 'Поставщик'),
            ('покупатель', 'Покупатель'),
            ('продавец', 'Продавец'),
            ('пациент', 'Пациент'),
            ('клиника', 'Клиника'),
            ('арендатор', 'Арендатор'),
            ('арендодатель', 'Арендодатель'),
        ]:
            if keyword in sample_text:
                add_candidate(label)
    except Exception as exc:
        logger.warning(f'Failed to extract party candidates: {exc}')

    tokens: List[str] = []
    for raw in [current_user.name, current_user.email.split('@')[0] if current_user.email else '']:
        for token in re.split(r'[^a-zа-я0-9]+', raw.lower() if raw else ''):
            token = token.strip()
            if len(token) >= 3:
                tokens.append(token)

    for candidate in candidates:
        normalized_candidate = normalize(candidate)
        if any(token in normalized_candidate for token in tokens):
            return candidate

    raise HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail={
            'code': 'analysis_perspective_required',
            'message': 'Не удалось автоматически определить, в чьих интересах выполнять анализ. Укажите сторону перед запуском.',
            'parties': candidates,
        },
    )


def _current_analysis_date() -> str:
    return datetime.now(ZoneInfo('Europe/Moscow')).date().isoformat()


def _recommendation_workflow_payload(analysis: AnalysisResult) -> Dict[str, Any]:
    payload = _load_meta(analysis.recommendations)
    workflow = payload.get('workflow')
    if not isinstance(workflow, dict):
        payload['workflow'] = {}
    return payload


def _workflow_summary(workflow: Dict[str, Any], recommendation_ids: List[int]) -> Dict[str, int]:
    accepted = 0
    rejected = 0
    for recommendation_id in recommendation_ids:
        state = workflow.get(str(recommendation_id), {})
        decision = state.get('decision')
        if decision == 'accepted':
            accepted += 1
        elif decision == 'rejected':
            rejected += 1
    total = len(recommendation_ids)
    return {
        'accepted': accepted,
        'rejected': rejected,
        'pending': max(total - accepted - rejected, 0),
        'total': total,
    }


async def analyze_contract_background(
    contract_id: str,
    user_id: str,
    check_counterparty: bool,
    counterparty_tin: Optional[str],
    analysis_perspective: Optional[str],
    analysis_date: Optional[str],
):
    """Background task for contract analysis — runs in thread to avoid blocking event loop"""
    import asyncio
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(
        None,
        _analyze_contract_sync,
        contract_id,
        user_id,
        check_counterparty,
        counterparty_tin,
        analysis_perspective,
        analysis_date,
    )


def _analyze_contract_sync(
    contract_id: str,
    user_id: str,
    check_counterparty: bool,
    counterparty_tin: Optional[str],
    analysis_perspective: Optional[str],
    analysis_date: Optional[str],
):
    """Synchronous contract analysis — runs in a thread pool executor"""
    from sqlalchemy.orm.attributes import flag_modified
    from src.models.database import SessionLocal
    from src.models.condition_models import CompanyCondition

    db = SessionLocal()
    try:
        contract = db.query(Contract).filter(Contract.id == contract_id).first()
        if not contract:
            logger.error(f"Contract {contract_id} not found for background analysis")
            return

        # Check that the file exists on disk
        if not contract.file_path or not os.path.exists(contract.file_path):
            logger.error(f"Contract file not found: {contract.file_path}")
            contract.status = 'error'
            meta = contract.meta_info or {}
            if not isinstance(meta, dict):
                import json as _json
                meta = _json.loads(meta) if meta else {}
            meta["_progress"] = 0
            meta["_progress_msg"] = f"Файл не найден: {contract.file_name}. Загрузите документ повторно."
            contract.meta_info = meta
            db.commit()
            return

        # Load user's active company conditions for analysis
        company_conditions = []
        try:
            conditions = db.query(CompanyCondition).filter(
                CompanyCondition.user_id == user_id,
                CompanyCondition.is_active == True,
            ).order_by(CompanyCondition.priority.desc()).all()
            company_conditions = [c.to_dict() for c in conditions]
            if company_conditions:
                logger.info(f"Loaded {len(company_conditions)} company conditions for user {user_id}")
        except Exception as cond_err:
            logger.warning(f"Failed to load company conditions: {cond_err}")

        def _set_progress(pct: int, msg: str = ""):
            try:
                meta = _load_meta(contract.meta_info)
                meta['_progress'] = pct
                meta['_progress_msg'] = msg
                if analysis_perspective:
                    meta['analysis_perspective'] = analysis_perspective
                if analysis_date:
                    meta['analysis_date'] = analysis_date
                contract.meta_info = meta
                flag_modified(contract, 'meta_info')
                db.commit()
            except Exception:
                try:
                    db.rollback()
                except Exception:
                    pass

        contract.status = 'parsing'
        _set_progress(5, 'Загрузка документа...')
        db.commit()

        parser = ExtendedDocumentParser()
        _set_progress(10, 'Парсинг документа...')
        parsed_xml = parser.parse(contract.file_path)

        if not parsed_xml:
            contract.status = 'error'
            db.commit()
            _set_progress(0, 'Ошибка парсинга документа')
            logger.error(f"Failed to parse contract {contract_id}")
            return

        meta = _load_meta(contract.meta_info)
        meta['xml'] = parsed_xml if isinstance(parsed_xml, str) else str(parsed_xml)
        contract.meta_info = meta
        flag_modified(contract, 'meta_info')
        db.commit()

        _set_progress(20, 'Документ распознан, подготовка к анализу...')

        db.refresh(contract)
        if contract.status == 'uploaded':
            logger.info(f"Analysis cancelled for contract {contract_id} (during parsing)")
            return

        meta = _load_meta(contract.meta_info)
        if analysis_perspective:
            meta['analysis_perspective'] = analysis_perspective
        if analysis_date:
            meta['analysis_date'] = analysis_date
        contract.meta_info = meta
        flag_modified(contract, 'meta_info')
        contract.status = 'analyzing'
        db.commit()

        _set_progress(30, 'AI анализ: выявление рисков...')

        llm_gateway = LLMGateway(model=settings.llm_quick_model)
        agent = ContractAnalyzerAgent(llm_gateway=llm_gateway, db_session=db)

        result = agent.execute({
            'contract_id': contract_id,
            'parsed_xml': parsed_xml,
            'check_counterparty': check_counterparty,
            'company_conditions': company_conditions,
            'metadata': {
                'contract_type': contract.contract_type,
                'counterparty_tin': counterparty_tin,
                'uploaded_by': user_id,
                'analysis_perspective': analysis_perspective,
                'analysis_date': analysis_date,
            }
        })

        db.refresh(contract)
        if contract.status == 'uploaded':
            logger.info(f"Analysis cancelled for contract {contract_id} (during analysis)")
            return

        if result.success:
            _set_progress(70, 'Анализ завершён, извлечение клауз...')
            logger.info(f"Contract {contract_id} analyzed successfully")

            detected_contract_type = None
            if result.data and isinstance(result.data, dict):
                detected_contract_type = result.data.get('contract_type')
            if detected_contract_type:
                contract.contract_type = detected_contract_type
                db.commit()

            try:
                xml_content = parsed_xml if isinstance(parsed_xml, str) else str(parsed_xml)
                extractor = ClauseExtractor()
                clauses = extractor.extract_clauses(xml_content)

                analyses = []
                if result.data and isinstance(result.data, dict):
                    analyses = result.data.get('clause_analyses', [])

                if clauses:
                    clause_service = ClauseLibraryService(db)
                    clause_service.save_clauses(contract_id, clauses, analyses)
                    logger.info(f"Contract {contract_id}: {len(clauses)} clauses saved to library")
            except Exception as clause_err:
                logger.warning(f"Auto clause extraction failed for {contract_id}: {clause_err}")

            _set_progress(82, 'Индексация в RAG...')
            try:
                contract_text = parsed_xml if isinstance(parsed_xml, str) else str(parsed_xml)
                if len(contract_text) > 100:
                    from src.services.enhanced_rag import EnhancedRAGSystem, CHROMA_AVAILABLE
                    if CHROMA_AVAILABLE:
                        rag = EnhancedRAGSystem()
                        num_chunks = rag.add_contract_with_chunking(
                            contract_id=contract_id,
                            contract_text=contract_text,
                            metadata={
                                'user_id': user_id,
                                'status': 'analyzed',
                            }
                        )
                        logger.info(f"Contract {contract_id} auto-indexed in RAG: {num_chunks} chunks")
            except Exception as rag_err:
                logger.warning(f"Auto RAG indexing failed for {contract_id}: {rag_err}")

            _set_progress(88, 'Цифровизация документа...')
            try:
                if contract.file_path and os.path.exists(contract.file_path):
                    with open(contract.file_path, 'rb') as f:
                        file_content = f.read()
                    digital_service = DigitalContractService(db)
                    digital_service.digitalize(contract_id, file_content, user_id)
                    logger.info(f"Contract {contract_id} auto-digitalized")
            except Exception as dig_err:
                logger.warning(f"Auto-digitalization failed for {contract_id}: {dig_err}")

            contract.status = 'completed'
            _set_progress(100, 'Анализ завершён!')
        else:
            contract.status = 'error'
            _set_progress(0, 'Ошибка анализа')
            logger.error(f"Contract {contract_id} analysis failed: {result.error}")

        db.commit()

    except Exception as e:
        logger.error(f"Background analysis error for contract {contract_id}: {e}", exc_info=True)
        try:
            contract = db.query(Contract).filter(Contract.id == contract_id).first()
            if contract:
                contract.status = 'error'
                db.commit()
        except Exception as update_err:
            logger.error(f"Failed to update contract {contract_id} status to error: {update_err}")
    finally:
        db.close()


@router.post('/analyze', response_model=AnalysisResultResponse)
async def analyze_contract(
    request_data: AnalysisResultRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Analyze an uploaded contract in background."""
    try:
        current_user.reset_daily_limits()

        if current_user.llm_requests_today >= current_user.max_llm_requests_per_day:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f'Дневной лимит LLM-запросов ({current_user.max_llm_requests_per_day}) исчерпан.'
            )

        contract = db.query(Contract).filter(Contract.id == request_data.contract_id).first()
        if not contract:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Contract not found')

        if contract.assigned_to != current_user.id and current_user.role not in ['admin']:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have permission to analyze this contract"
            )

        # Check file exists before starting analysis
        if not contract.file_path or not os.path.exists(contract.file_path):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Файл документа не найден: {contract.file_name}. Загрузите документ повторно."
            )

        if contract.status in ['analyzing', 'parsing']:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail='Анализ уже запущен для этого договора'
            )

        max_concurrent_per_user = 3
        active_count = db.query(Contract).filter(
            Contract.assigned_to == current_user.id,
            Contract.status.in_(['analyzing', 'parsing'])
        ).count()
        if active_count >= max_concurrent_per_user:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f'Максимум {max_concurrent_per_user} одновременных анализа. Дождитесь завершения текущих.'
            )

        analysis_perspective = _resolve_analysis_perspective(contract, request_data, current_user)
        analysis_date = _current_analysis_date()

        background_tasks.add_task(
            analyze_contract_background,
            contract_id=request_data.contract_id,
            user_id=current_user.id,
            check_counterparty=request_data.check_counterparty,
            counterparty_tin=request_data.counterparty_tin,
            analysis_perspective=analysis_perspective,
            analysis_date=analysis_date,
        )

        current_user.llm_requests_today = (current_user.llm_requests_today or 0) + 1
        db.commit()

        logger.info(
            f'Analysis started for contract {request_data.contract_id} by user {current_user.id}, '
            f'perspective={analysis_perspective}'
        )

        return AnalysisResultResponse(
            analysis_id=request_data.contract_id,
            contract_id=request_data.contract_id,
            status='analyzing',
            risks_count=0,
            recommendations_count=0,
            message=(
                f'Анализ запущен на дату {analysis_date} в интересах стороны: {analysis_perspective}. '
                f'Следите за прогрессом через WebSocket /ws/analysis/{request_data.contract_id}.'
            ),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f'Error starting analysis: {e}', exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail='Error starting analysis'
        )


@router.post(
    '/{contract_id}/recommendations/{recommendation_id}/decision',
    response_model=RecommendationDecisionResponse,
)
async def update_recommendation_decision(
    contract_id: str,
    recommendation_id: int,
    request_data: RecommendationDecisionRequest,
    contract: Contract = Depends(get_contract_with_access_sync),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Persist user decision for a recommendation to build a final result set."""
    try:
        analysis = (
            db.query(AnalysisResult)
            .filter(AnalysisResult.contract_id == contract_id)
            .order_by(AnalysisResult.created_at.desc(), AnalysisResult.version.desc())
            .first()
        )
        if not analysis:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Analysis not found')

        recommendation = (
            db.query(ContractRecommendation)
            .filter(
                ContractRecommendation.id == recommendation_id,
                ContractRecommendation.analysis_id == analysis.id,
                ContractRecommendation.contract_id == contract_id,
            )
            .first()
        )
        if not recommendation:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Recommendation not found')

        payload = _recommendation_workflow_payload(analysis)
        workflow = payload['workflow']
        workflow[str(recommendation_id)] = {
            'decision': request_data.decision,
            'updated_at': datetime.now(ZoneInfo('Europe/Moscow')).isoformat(),
            'updated_by': current_user.id,
        }

        recommendation_ids = [
            rec_id for (rec_id,) in db.query(ContractRecommendation.id).filter(
                ContractRecommendation.analysis_id == analysis.id
            ).all()
        ]
        summary = _workflow_summary(workflow, recommendation_ids)
        payload['summary'] = summary

        analysis.recommendations = payload
        flag_modified(analysis, 'recommendations')
        db.commit()

        return RecommendationDecisionResponse(
            contract_id=contract_id,
            recommendation_id=recommendation_id,
            decision=request_data.decision,
            summary=summary,
            message='Решение по рекомендации сохранено.',
        )

    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f'Failed to update recommendation decision: {exc}', exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail='Internal server error'
        )


@router.post("/{contract_id}/analyze/cancel")
async def cancel_analysis(
    contract_id: str,
    contract: Contract = Depends(get_contract_with_access_sync),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):

    if contract.status not in ('analyzing', 'parsing'):
        raise HTTPException(status_code=409, detail="Анализ не запущен")

    contract.status = 'uploaded'
    meta = _load_meta(contract.meta_info)
    meta['_progress'] = 0
    meta['_progress_msg'] = 'Анализ остановлен'
    contract.meta_info = meta
    flag_modified(contract, 'meta_info')
    db.commit()
    logger.info(f"Analysis cancelled for contract {contract_id} by user {current_user.id}")
    return {"ok": True, "message": "Анализ остановлен"}


@router.post("/{contract_id}/analyze/stream")
async def analyze_contract_stream(
    contract_id: str,
    contract: Contract = Depends(get_contract_with_access_sync),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Streaming contract analysis via Server-Sent Events (SSE).
    Sends incremental analysis results as they are generated.
    """
    import json as json_mod

    parsed_xml = (contract.meta_info or {}).get('xml')
    if not parsed_xml:
        # Parse on the fly
        parser = ExtendedDocumentParser()
        try:
            parsed_xml = parser.parse(contract.file_path)
        except Exception as e:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Document parse error")

    async def event_generator():
        try:
            yield {"event": "status", "data": json_mod.dumps({"status": "started", "contract_id": contract_id})}

            llm = LLMGateway(model=settings.llm_quick_model)
            system_prompt = (
                "You are a contract analysis expert specializing in Russian contract law. "
                "Analyze the following contract clauses and provide risk assessment in Russian."
            )

            yield {"event": "status", "data": json_mod.dumps({"status": "analyzing"})}

            collected = []
            async for chunk in llm.stream(
                prompt=f"Проанализируй договор и выяви риски:\n\n{parsed_xml[:8000]}",
                system_prompt=system_prompt,
            ):
                collected.append(chunk)
                yield {"event": "chunk", "data": json_mod.dumps({"text": chunk})}

            full_text = "".join(collected)
            yield {"event": "done", "data": json_mod.dumps({"status": "completed", "full_text": full_text})}

        except Exception as e:
            logger.error(f"Streaming analysis error: {e}", exc_info=True)
            yield {"event": "error", "data": json_mod.dumps({"error": "Ошибка анализа. Попробуйте снова."})}

    return EventSourceResponse(event_generator())


@router.post("/analyze/batch", response_model=BatchAnalysisResponse)
async def batch_analyze_contracts(
    request_data: BatchAnalysisRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Start batch analysis of multiple contracts.
    Progress is reported via WebSocket at /ws/batch/{task_id}.
    """
    # Validate all contracts exist and belong to user
    contract_ids = request_data.contract_ids
    contracts = db.query(Contract).filter(Contract.id.in_(contract_ids)).all()

    if len(contracts) != len(contract_ids):
        found = {c.id for c in contracts}
        missing = [cid for cid in contract_ids if cid not in found]
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Contracts not found: {missing}"
        )

    for c in contracts:
        if c.assigned_to != current_user.id and current_user.role not in ['admin']:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"No permission for contract {c.id}")

    task_id = str(uuid.uuid4())

    # Launch background batch processing
    async def run_batch():
        try:
            import asyncio
            tasks = []
            for cid in contract_ids:
                tasks.append(
                    asyncio.to_thread(
                        _analyze_single_sync,
                        cid,
                        current_user.id,
                        request_data.check_counterparty,
                    )
                )
            # Process in parallel with concurrency limit
            sem = asyncio.Semaphore(settings.max_concurrent_batches if hasattr(settings, 'max_concurrent_batches') else 3)

            async def bounded(t):
                async with sem:
                    return await t

            await asyncio.gather(*(bounded(t) for t in tasks), return_exceptions=True)
        except Exception as e:
            logger.error(f"Batch analysis error: {e}", exc_info=True)

    background_tasks.add_task(run_batch)

    return BatchAnalysisResponse(
        task_id=task_id,
        total=len(contract_ids),
        status="started",
        message=f"Batch analysis started for {len(contract_ids)} contracts. Track via /ws/batch/{task_id}"
    )


def _analyze_single_sync(contract_id: str, user_id: str, check_counterparty: bool):
    """Synchronous single contract analysis for use in thread pool"""
    from src.models.database import SessionLocal
    db = SessionLocal()
    try:
        analyze_contract_background(contract_id, user_id, check_counterparty, None)
    finally:
        db.close()
