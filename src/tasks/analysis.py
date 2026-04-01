# -*- coding: utf-8 -*-
"""
Contract Analysis RQ Task

Runs in a separate rq-worker process, not inside gunicorn.
Progress is written to contract.meta_info — WebSocket reads it from DB.
"""
import os
import json
from typing import Optional

from loguru import logger


def run_analysis(
    contract_id: str,
    user_id: str,
    check_counterparty: bool,
    counterparty_tin: Optional[str] = None,
    analysis_perspective: Optional[str] = None,
    analysis_date: Optional[str] = None,
):
    """
    RQ task: full contract analysis pipeline.

    Synchronous — RQ worker runs this in its own process,
    no need for asyncio.to_thread or event loop tricks.
    """
    from src.models.database import SessionLocal
    from src.models import Contract
    from src.services.document_parser import DocumentParser
    from src.agents.contract_analyzer_agent import ContractAnalyzerAgent
    from src.services.llm_gateway import LLMGateway
    from src.services.digital_service import DigitalContractService
    from src.services.clause_library_service import ClauseLibraryService
    from src.services.clause_extractor import ClauseExtractor
    from config.settings import settings

    db = SessionLocal()
    try:
        contract = db.query(Contract).filter(Contract.id == contract_id).first()
        if not contract:
            logger.error(f"Contract {contract_id} not found for RQ analysis")
            return {"status": "error", "reason": "contract_not_found"}

        def _set_progress(pct: int, msg: str = ""):
            """Update progress in meta_info for WebSocket polling."""
            try:
                meta = contract.meta_info or {}
                if not isinstance(meta, dict):
                    meta = json.loads(meta) if meta else {}
                meta["_progress"] = pct
                meta["_progress_msg"] = msg
                contract.meta_info = meta
                db.commit()
            except Exception:
                pass

        # --- Parse ---
        contract.status = "parsing"
        _set_progress(5, "Загрузка документа...")
        db.commit()

        parser = DocumentParser()
        _set_progress(10, "Парсинг документа...")
        parsed_xml = parser.parse(contract.file_path)

        if not parsed_xml:
            contract.status = "error"
            db.commit()
            logger.error(f"Failed to parse contract {contract_id}")
            return {"status": "error", "reason": "parse_failed"}

        _set_progress(20, "Документ распознан, подготовка к анализу...")

        # Store XML
        meta = contract.meta_info or {}
        if not isinstance(meta, dict):
            meta = json.loads(meta) if meta else {}
        meta["xml"] = parsed_xml
        if analysis_perspective:
            meta["analysis_perspective"] = analysis_perspective
        if analysis_date:
            meta["analysis_date"] = analysis_date
        contract.meta_info = meta
        contract.status = "analyzing"
        db.commit()

        # --- Analyze ---
        _set_progress(30, "AI анализ: выявление рисков...")

        llm_gateway = LLMGateway(model=settings.llm_quick_model)
        agent = ContractAnalyzerAgent(llm_gateway=llm_gateway, db_session=db)

        # Direct synchronous call — no asyncio needed in RQ worker
        result = agent.execute({
            "contract_id": contract_id,
            "parsed_xml": parsed_xml,
            "check_counterparty": check_counterparty,
            "metadata": {
                "counterparty_tin": counterparty_tin,
                "uploaded_by": user_id,
                "analysis_perspective": analysis_perspective,
                "analysis_date": analysis_date,
            },
        })

        if result.success:
            _set_progress(70, "Анализ завершён, извлечение клауз...")
            logger.info(f"Contract {contract_id} analyzed successfully")

            # Auto-save extracted clauses
            try:
                xml_content = parsed_xml if isinstance(parsed_xml, str) else str(parsed_xml)
                extractor = ClauseExtractor()
                clauses = extractor.extract_clauses(xml_content)

                analyses = []
                if result.data and isinstance(result.data, dict):
                    analyses = result.data.get("clause_analyses", [])

                if clauses:
                    clause_service = ClauseLibraryService(db)
                    clause_service.save_clauses(contract_id, clauses, analyses)
                    logger.info(f"Contract {contract_id}: {len(clauses)} clauses saved to library")
            except Exception as clause_err:
                logger.warning(f"Auto clause extraction failed for {contract_id}: {clause_err}")

            _set_progress(85, "Цифровизация документа...")

            # Auto-digitalize
            try:
                if contract.file_path and os.path.exists(contract.file_path):
                    with open(contract.file_path, "rb") as f:
                        file_content = f.read()
                    digital_service = DigitalContractService(db)
                    digital_service.digitalize(contract_id, file_content, user_id)
                    logger.info(f"Contract {contract_id} auto-digitalized")
            except Exception as dig_err:
                logger.warning(f"Auto-digitalization failed for {contract_id}: {dig_err}")

            contract.status = "completed"
            _set_progress(100, "Анализ завершён!")
        else:
            contract.status = "error"
            logger.error(f"Contract {contract_id} analysis failed: {result.error}")

        db.commit()
        return {"status": contract.status, "contract_id": contract_id}

    except Exception as e:
        logger.error(f"RQ analysis error for contract {contract_id}: {e}", exc_info=True)
        try:
            contract = db.query(Contract).filter(Contract.id == contract_id).first()
            if contract:
                contract.status = "error"
                db.commit()
        except Exception as update_err:
            logger.error(f"Failed to update contract {contract_id} status to error: {update_err}")
        return {"status": "error", "reason": str(e)}
    finally:
        db.close()


def run_batch_analysis(
    contract_ids: list,
    user_id: str,
    check_counterparty: bool,
    analysis_perspective: Optional[str] = None,
    analysis_date: Optional[str] = None,
):
    """
    RQ task: batch analysis — enqueues individual analysis jobs.
    Each contract gets its own RQ job for independent retry/monitoring.
    """
    from redis import Redis
    from rq import Queue
    from config.settings import settings

    redis_conn = Redis.from_url(settings.redis_url)
    q = Queue("analysis", connection=redis_conn)

    jobs = []
    for cid in contract_ids:
        job = q.enqueue(
            run_analysis,
            contract_id=cid,
            user_id=user_id,
            check_counterparty=check_counterparty,
            analysis_perspective=analysis_perspective,
            analysis_date=analysis_date,
            job_timeout="30m",
        )
        jobs.append({"contract_id": cid, "job_id": job.id})
        logger.info(f"Batch: enqueued analysis for contract {cid} as job {job.id}")

    return {"enqueued": len(jobs), "jobs": jobs}
