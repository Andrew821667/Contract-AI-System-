# -*- coding: utf-8 -*-
"""
Contract Export Routes
"""
from io import BytesIO
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy.orm import Session
from loguru import logger

from src.models.database import get_db
from src.models import Contract, AnalysisResult
from src.models.auth_models import User
from src.agents.quick_export_agent import QuickExportAgent
from src.services.llm_gateway import LLMGateway
from config.settings import settings
from src.api.dependencies import get_current_user

from .schemas import ExportRequest


router = APIRouter()


_MEDIA_TYPES = {
    'docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    'pdf': 'application/pdf',
    'txt': 'text/plain; charset=utf-8',
    'json': 'application/json',
    'xml': 'application/xml',
}


def _ensure_contract_access(contract: Contract, current_user: User) -> None:
    if contract.assigned_to != current_user.id and current_user.role not in ['admin']:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No permission to export this contract")


def _build_export_agent(db: Session) -> QuickExportAgent:
    llm_gateway = LLMGateway(model=settings.llm_quick_model)
    return QuickExportAgent(llm_gateway=llm_gateway, db_session=db)


def _run_single_export(
    contract_id: str,
    export_format: str,
    include_analysis: bool,
    allow_lossy_conversion: bool,
    user_id: str,
    db: Session,
) -> str:
    agent = _build_export_agent(db)
    result = agent.execute({
        'contract_id': contract_id,
        'export_format': export_format,
        'include_analysis': include_analysis,
        'allow_lossy_conversion': allow_lossy_conversion,
        'user_id': user_id,
    })

    if not result.success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Export failed: {result.error}",
        )

    file_path = (result.data.get('file_paths') or {}).get(export_format)
    if not file_path:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Экспорт в формат {export_format.upper()} недоступен для этого документа",
        )
    if not Path(file_path).exists():
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Export file was not created",
        )
    return file_path


@router.post("/export")
async def export_contract(
    request_data: ExportRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Export contract to various formats

    **Formats:**
    - docx: Microsoft Word
    - pdf: PDF document
    - txt: Plain text
    - json: JSON data
    - xml: XML format
    - all: All formats

    **Returns:** Download links for requested formats
    """
    try:
        # Ownership check
        contract = db.query(Contract).filter(Contract.id == request_data.contract_id).first()
        if not contract:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Contract not found")
        _ensure_contract_access(contract, current_user)

        import asyncio

        if request_data.export_format == 'all':
            def _run_all():
                agent = _build_export_agent(db)
                return agent.execute({
                    'contract_id': request_data.contract_id,
                    'export_format': request_data.export_format,
                    'include_analysis': request_data.include_analysis,
                    'allow_lossy_conversion': request_data.allow_lossy_conversion,
                    'user_id': current_user.id,
                })
            result = await asyncio.to_thread(_run_all)
            if result.success:
                logger.info(f"Contract exported: {request_data.contract_id} to {request_data.export_format}")
                return result.data
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Export failed: {result.error}",
            )

        file_path = await asyncio.to_thread(
            _run_single_export,
            contract_id=request_data.contract_id,
            export_format=request_data.export_format,
            include_analysis=request_data.include_analysis,
            allow_lossy_conversion=request_data.allow_lossy_conversion,
            user_id=current_user.id,
            db=db,
        )
        return {
            'contract_id': request_data.contract_id,
            'file_path': file_path,
            'format': request_data.export_format,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error exporting contract: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


@router.get("/{contract_id}/export")
async def download_exported_contract(
    contract_id: str,
    format: str = Query(..., pattern='^(docx|pdf|txt|json|xml)$'),
    include_analysis: bool = Query(False),
    allow_lossy_conversion: bool = Query(False),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Stream exported file for the frontend download flow."""
    try:
        contract = db.query(Contract).filter(Contract.id == contract_id).first()
        if not contract:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Contract not found")
        _ensure_contract_access(contract, current_user)

        import asyncio
        file_path = await asyncio.to_thread(
            _run_single_export,
            contract_id=contract_id,
            export_format=format,
            include_analysis=include_analysis,
            allow_lossy_conversion=allow_lossy_conversion,
            user_id=current_user.id,
            db=db,
        )

        download_name = f"{Path(contract.file_name or contract_id).stem}.{format}"
        return FileResponse(
            path=file_path,
            media_type=_MEDIA_TYPES.get(format, 'application/octet-stream'),
            filename=download_name,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error streaming export for {contract_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.get("/{contract_id}/export/annotated-docx")
async def export_annotated_docx(
    contract_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Export contract as annotated DOCX with highlighted risks.
    - Red background for critical risks
    - Yellow background for medium risks
    - Comments with risk descriptions
    """
    from src.services.annotated_docx_service import AnnotatedDocxService

    contract = db.query(Contract).filter(Contract.id == contract_id).first()
    if not contract:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Contract not found")

    if contract.assigned_to != current_user.id and current_user.role not in ['admin']:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No permission")

    # Get analysis results
    analysis = db.query(AnalysisResult).filter(AnalysisResult.contract_id == contract_id).first()
    if not analysis:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No analysis results found. Analyze the contract first."
        )

    try:
        import asyncio
        service = AnnotatedDocxService()
        docx_bytes = await asyncio.to_thread(service.create_annotated_docx, contract, analysis, db)

        return StreamingResponse(
            BytesIO(docx_bytes),
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            headers={
                "Content-Disposition": f'attachment; filename="annotated_{contract.file_name or contract_id}.docx"'
            }
        )
    except Exception as e:
        logger.error(f"Annotated DOCX export error: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Export error")
