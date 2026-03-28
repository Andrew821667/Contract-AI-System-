# -*- coding: utf-8 -*-
"""
Contract Analysis Routes
"""
import os
import uuid
from typing import Optional, Dict, List

from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sse_starlette.sse import EventSourceResponse
from sqlalchemy.orm import Session
from loguru import logger

from src.models.database import get_db
from src.models import Contract, AnalysisResult
from src.models.auth_models import User
from src.services.document_parser import DocumentParser
from src.agents.contract_analyzer_agent import ContractAnalyzerAgent
from src.services.llm_gateway import LLMGateway
from src.services.digital_service import DigitalContractService
from src.services.clause_library_service import ClauseLibraryService
from src.services.clause_extractor import ClauseExtractor
from config.settings import settings
from src.api.dependencies import get_current_user

from .schemas import (
    AnalysisResultRequest,
    AnalysisResultResponse,
    BatchAnalysisRequest,
    BatchAnalysisResponse,
)


router = APIRouter()


async def analyze_contract_background(
    contract_id: str,
    user_id: str,
    check_counterparty: bool,
    counterparty_tin: Optional[str],
):
    """Background task for contract analysis — creates its own DB session"""
    from src.models.database import SessionLocal
    db = SessionLocal()
    try:
        contract = db.query(Contract).filter(Contract.id == contract_id).first()
        if not contract:
            logger.error(f"Contract {contract_id} not found for background analysis")
            return

        def _set_progress(pct: int, msg: str = ""):
            """Update analysis_progress on contract for WebSocket to pick up."""
            try:
                meta = contract.meta_info or {}
                if not isinstance(meta, dict):
                    import json
                    meta = json.loads(meta) if meta else {}
                meta["_progress"] = pct
                meta["_progress_msg"] = msg
                contract.meta_info = meta
                db.commit()
            except Exception:
                pass

        # Update status to parsing
        contract.status = 'parsing'
        _set_progress(5, "Загрузка документа...")
        db.commit()

        # Parse document
        parser = DocumentParser()
        _set_progress(10, "Парсинг документа...")
        parsed_xml = parser.parse(contract.file_path)

        if not parsed_xml:
            contract.status = 'error'
            db.commit()
            logger.error(f"Failed to parse contract {contract_id}")
            return

        _set_progress(20, "Документ распознан, подготовка к анализу...")

        # Update status — parsed XML is passed directly to the agent, NOT stored in DB
        # (storing multi-MB XML in a JSON column degrades DB performance)
        contract.status = 'analyzing'
        db.commit()

        _set_progress(30, "AI анализ: выявление рисков...")

        llm_gateway = LLMGateway(model=settings.llm_quick_model)
        agent = ContractAnalyzerAgent(llm_gateway=llm_gateway, db_session=db)

        result = agent.execute({
            'contract_id': contract_id,
            'parsed_xml': parsed_xml,
            'check_counterparty': check_counterparty,
            'metadata': {
                'counterparty_tin': counterparty_tin,
                'uploaded_by': user_id
            }
        })

        if result.success:
            _set_progress(70, "Анализ завершён, извлечение клауз...")
            logger.info(f"Contract {contract_id} analyzed successfully")

            # Auto-save extracted clauses to library
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

            _set_progress(85, "Цифровизация документа...")

            # Auto-digitalize after successful analysis
            try:
                if contract.file_path and os.path.exists(contract.file_path):
                    with open(contract.file_path, "rb") as f:
                        file_content = f.read()
                    digital_service = DigitalContractService(db)
                    digital_service.digitalize(contract_id, file_content, user_id)
                    logger.info(f"Contract {contract_id} auto-digitalized")
            except Exception as dig_err:
                logger.warning(f"Auto-digitalization failed for {contract_id}: {dig_err}")

            contract.status = 'completed'
            _set_progress(100, "Анализ завершён!")
        else:
            contract.status = 'error'
            logger.error(f"Contract {contract_id} analysis failed: {result.error}")

        # Single commit for all analysis results + status update
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


@router.post("/analyze", response_model=AnalysisResultResponse)
async def analyze_contract(
    request_data: AnalysisResultRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Analyze an uploaded contract

    **Process:**
    1. Parse document to XML
    2. Extract contract structure
    3. Analyze each clause for risks
    4. Check legal compliance
    5. Generate recommendations
    6. (Optional) Check counterparty via ФНС API

    **Returns:** Analysis ID and initial status
    **Note:** Analysis runs in background. Use WebSocket or polling to get results.
    """
    try:
        # Reset daily limits if new day
        current_user.reset_daily_limits()

        # Check LLM usage limits
        if current_user.llm_requests_today >= current_user.max_llm_requests_per_day:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Дневной лимит LLM-запросов ({current_user.max_llm_requests_per_day}) исчерпан."
            )

        # Get contract
        contract = db.query(Contract).filter(Contract.id == request_data.contract_id).first()
        if not contract:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Contract not found"
            )

        # Check ownership
        if contract.assigned_to != current_user.id and current_user.role not in ['admin']:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have permission to analyze this contract"
            )

        # Prevent duplicate analysis (race condition guard)
        if contract.status == 'analyzing':
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Анализ уже запущен для этого договора"
            )

        # Start background task
        background_tasks.add_task(
            analyze_contract_background,
            contract_id=request_data.contract_id,
            user_id=current_user.id,
            check_counterparty=request_data.check_counterparty,
            counterparty_tin=request_data.counterparty_tin,
        )

        # Increment LLM usage counter
        current_user.llm_requests_today = (current_user.llm_requests_today or 0) + 1
        db.commit()

        logger.info(f"Analysis started for contract {request_data.contract_id} by user {current_user.id}")

        return AnalysisResultResponse(
            analysis_id=request_data.contract_id,  # analysis record is created inside background task
            contract_id=request_data.contract_id,
            status='analyzing',
            risks_count=0,
            recommendations_count=0,
            message='Analysis started. Use WebSocket /ws/analysis/{contract_id} to track progress.'
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error starting analysis: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error starting analysis"
        )


@router.post("/{contract_id}/analyze/stream")
async def analyze_contract_stream(
    contract_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Streaming contract analysis via Server-Sent Events (SSE).
    Sends incremental analysis results as they are generated.
    """
    import asyncio
    import json as json_mod

    contract = db.query(Contract).filter(Contract.id == contract_id).first()
    if not contract:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Contract not found")

    if contract.assigned_to != current_user.id and current_user.role not in ['admin']:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No permission")

    parsed_xml = (contract.meta_info or {}).get('xml')
    if not parsed_xml:
        # Parse on the fly
        parser = DocumentParser()
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
    import asyncio

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
