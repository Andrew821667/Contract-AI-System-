# -*- coding: utf-8 -*-
"""
Contract Export Routes
"""
from io import BytesIO

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
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
        if contract.assigned_to != current_user.id and current_user.role not in ['admin']:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No permission to export this contract")

        llm_gateway = LLMGateway(model=settings.llm_quick_model)
        agent = QuickExportAgent(llm_gateway=llm_gateway, db_session=db)

        result = agent.execute({
            'contract_id': request_data.contract_id,
            'export_format': request_data.export_format,
            'include_analysis': request_data.include_analysis,
            'user_id': current_user.id
        })

        if result.success:
            logger.info(f"Contract exported: {request_data.contract_id} to {request_data.export_format}")
            return result.data
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Export failed: {result.error}"
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error exporting contract: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
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
        service = AnnotatedDocxService()
        docx_bytes = service.create_annotated_docx(contract, analysis, db)

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
