# -*- coding: utf-8 -*-
"""
Contract Upload Routes
"""
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from sqlalchemy.orm import Session
from loguru import logger

from src.models.database import get_db
from src.models import Contract
from src.models.auth_models import User
from src.utils.file_validator import save_uploaded_file_securely, FileValidationError
from src.api.dependencies import get_current_user

from .schemas import ContractUploadResponse


router = APIRouter()


@router.post("/upload", response_model=ContractUploadResponse)
async def upload_contract(
    file: UploadFile = File(...),
    document_type: str = Form("contract"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Upload a contract file for analysis

    **Supported formats:** DOCX, PDF, XML, TXT
    **Max size:** 10 MB

    **Returns:** Contract ID and status
    """
    try:
        # Reset daily limits if new day
        current_user.reset_daily_limits()

        # Check usage limits
        if current_user.contracts_today >= current_user.max_contracts_per_day:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Дневной лимит загрузки ({current_user.max_contracts_per_day}) исчерпан. Попробуйте завтра."
            )

        # Read file data
        file_data = await file.read()

        # Validate and save file securely
        try:
            file_path, safe_filename, file_size = save_uploaded_file_securely(
                file_data=file_data,
                filename=file.filename,
                upload_dir="data/contracts"
            )
        except FileValidationError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="File validation failed"
            )

        # Create contract record in database
        contract = Contract(
            file_name=safe_filename,
            file_path=file_path,
            document_type=document_type,
            contract_type='unknown',  # Will be determined during analysis
            status='uploaded',
            assigned_to=current_user.id,
            meta_info={}
        )
        db.add(contract)
        db.commit()
        db.refresh(contract)

        # Increment daily usage counter
        current_user.contracts_today = (current_user.contracts_today or 0) + 1
        db.commit()

        logger.info(f"Contract uploaded: {contract.id} by user {current_user.id}")

        return ContractUploadResponse(
            contract_id=contract.id,
            file_name=safe_filename,
            file_size=file_size,
            status='uploaded',
            message='Contract uploaded successfully'
        )

    except FileValidationError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File validation failed"
        )
    except Exception as e:
        logger.error(f"Error uploading contract: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error uploading contract"
        )
