# -*- coding: utf-8 -*-
"""
Contract Upload Routes

Performance: Uses streaming upload (shutil.copyfileobj) to avoid loading
entire file into memory. Validates extension/magic bytes after streaming to disk.
"""
import os
import tempfile

from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from sqlalchemy import update as sql_update
from sqlalchemy.orm import Session
from loguru import logger

from src.models.database import get_db
from src.models import Contract
from src.models.auth_models import User
from src.utils.file_validator import (
    FileValidationError,
    sanitize_filename,
    validate_file_extension,
    validate_file_size,
    validate_mime_type,
    MAX_FILE_SIZE,
)
from src.api.dependencies import get_current_user

from .schemas import ContractUploadResponse


router = APIRouter()

UPLOAD_DIR = "data/contracts"


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
    **Max size:** 50 MB

    **Performance:** Streams file to disk in 64KB chunks instead of loading entirely into memory.

    **Returns:** Contract ID and status
    """
    VALID_DOCUMENT_TYPES = {"contract", "disagreement", "tracked_changes"}
    if document_type not in VALID_DOCUMENT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid document_type. Allowed: {', '.join(sorted(VALID_DOCUMENT_TYPES))}"
        )

    tmp_path = None
    try:
        # Reset daily limits if new day
        current_user.reset_daily_limits()

        # Check usage limits
        if current_user.contracts_today >= current_user.max_contracts_per_day:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Дневной лимит загрузки ({current_user.max_contracts_per_day}) исчерпан. Попробуйте завтра."
            )

        # Validate filename and extension before streaming
        try:
            safe_filename = sanitize_filename(file.filename)
            ext = validate_file_extension(safe_filename)
        except FileValidationError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"File validation failed: {e}"
            )

        # Stream file to a temporary file (64KB chunks — avoids memory spike)
        os.makedirs(UPLOAD_DIR, exist_ok=True)
        fd, tmp_path = tempfile.mkstemp(dir=UPLOAD_DIR, suffix=ext)
        try:
            file_size = 0
            magic_bytes = b""
            with os.fdopen(fd, "wb") as tmp_file:
                while True:
                    chunk = await file.read(65536)  # 64KB chunks
                    if not chunk:
                        break
                    file_size += len(chunk)
                    if file_size > MAX_FILE_SIZE:
                        raise FileValidationError(
                            f"File too large (>{MAX_FILE_SIZE // (1024*1024)} MB)"
                        )
                    if len(magic_bytes) < 100:
                        magic_bytes += chunk
                        magic_bytes = magic_bytes[:100]
                    tmp_file.write(chunk)
        except FileValidationError:
            # Clean up temp file on validation failure
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
            raise

        # Validate size and magic bytes after streaming
        try:
            validate_file_size(file_size)
            if len(magic_bytes) >= 10:
                validate_mime_type(magic_bytes, ext)
        except FileValidationError as e:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"File validation failed: {e}"
            )

        # Rename temp file to final safe name
        # Add collision-safe suffix if needed
        final_path = os.path.join(UPLOAD_DIR, safe_filename)
        if not os.path.abspath(final_path).startswith(os.path.abspath(UPLOAD_DIR)):
            os.unlink(tmp_path)
            raise HTTPException(status_code=400, detail="Path traversal detected")

        if os.path.exists(final_path):
            name, fext = os.path.splitext(safe_filename)
            safe_filename = f"{name}_{os.urandom(8).hex()[:8]}{fext}"
            final_path = os.path.join(UPLOAD_DIR, safe_filename)

        os.rename(tmp_path, final_path)
        tmp_path = None  # Prevent cleanup in finally

        # Create contract record in database
        contract = Contract(
            file_name=safe_filename,
            file_path=final_path,
            document_type=document_type,
            contract_type='unknown',  # Will be determined during analysis
            status='uploaded',
            assigned_to=current_user.id,
            meta_info={}
        )
        db.add(contract)
        db.commit()
        db.refresh(contract)

        # Atomic increment with limit re-check (prevents race condition)
        result = db.execute(
            sql_update(User)
            .where(User.id == current_user.id)
            .where(User.contracts_today < User.max_contracts_per_day)
            .values(contracts_today=User.contracts_today + 1)
        )
        if result.rowcount == 0:
            db.delete(contract)
        db.commit()
        if result.rowcount == 0:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Дневной лимит загрузки ({current_user.max_contracts_per_day}) исчерпан. Попробуйте завтра."
            )

        logger.info(f"Contract uploaded: {contract.id} by user {current_user.id} ({file_size} bytes, streamed)")

        return ContractUploadResponse(
            contract_id=contract.id,
            file_name=safe_filename,
            file_size=file_size,
            status='uploaded',
            message='Contract uploaded successfully'
        )

    except (HTTPException, FileValidationError):
        raise
    except Exception as e:
        logger.error(f"Error uploading contract: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error uploading contract"
        )
    finally:
        # Clean up temp file if still exists (error path)
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
