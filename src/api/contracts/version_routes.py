# -*- coding: utf-8 -*-
"""
Contract Version Routes
"""
import os
import hashlib
from typing import Dict, List

from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from sqlalchemy.orm import Session
from sqlalchemy import func
from loguru import logger

from src.models.database import get_db
from src.models import Contract
from src.models.auth_models import User
from src.models.changes_models import ContractVersion, ContractChange, ChangeAnalysisResult
from src.services.document_parser_extended import ExtendedDocumentParser
from src.services.document_diff_service import DocumentDiffService
from src.utils.file_validator import save_uploaded_file_securely, FileValidationError
from src.api.dependencies import get_current_user

from .schemas import (
    ContractVersionResponse,
    CompareRequest,
    CompareChangeItem,
    CompareResultResponse,
)


router = APIRouter()


@router.post("/{contract_id}/versions", response_model=ContractVersionResponse)
async def upload_version(
    contract_id: str,
    file: UploadFile = File(...),
    source: str = Form("unknown"),
    description: str = Form(""),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Upload a new version of a contract file"""
    try:
        # Check contract exists
        contract = db.query(Contract).filter(Contract.id == contract_id).first()
        if not contract:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Contract not found")

        # Check ownership
        if contract.assigned_to != current_user.id and current_user.role not in ['admin']:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No permission")

        # Read and save file
        file_data = await file.read()

        try:
            file_path, safe_filename, file_size = save_uploaded_file_securely(
                file_data=file_data,
                filename=file.filename,
                upload_dir="data/contracts/versions"
            )
        except FileValidationError as e:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="File validation failed")

        # Compute SHA-256 hash
        file_hash = hashlib.sha256(file_data).hexdigest()

        # Determine next version number
        max_version = db.query(func.max(ContractVersion.version_number)).filter(
            ContractVersion.contract_id == contract_id
        ).scalar() or 0
        next_version = max_version + 1

        # Mark previous versions as not current
        db.query(ContractVersion).filter(
            ContractVersion.contract_id == contract_id,
            ContractVersion.is_current == True
        ).update({'is_current': False})

        # Create new version
        version = ContractVersion(
            contract_id=contract_id,
            version_number=next_version,
            file_path=file_path,
            file_hash=file_hash,
            uploaded_by=current_user.id,
            source=source if source in ('initial', 'counterparty_response', 'internal_revision', 'final', 'unknown') else 'unknown',
            description=description or None,
            is_current=True
        )
        db.add(version)
        db.commit()
        db.refresh(version)

        logger.info(f"Version {next_version} uploaded for contract {contract_id}")

        return ContractVersionResponse(
            id=version.id,
            contract_id=version.contract_id,
            version_number=version.version_number,
            file_hash=version.file_hash,
            source=version.source,
            description=version.description,
            is_current=version.is_current,
            uploaded_at=version.uploaded_at.isoformat() if version.uploaded_at else None
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error uploading version: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error")


@router.get("/{contract_id}/versions")
async def list_versions(
    contract_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List all versions of a contract"""
    try:
        # Check contract exists
        contract = db.query(Contract).filter(Contract.id == contract_id).first()
        if not contract:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Contract not found")

        if contract.assigned_to != current_user.id and current_user.role not in ['admin']:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No permission")

        versions = db.query(ContractVersion).filter(
            ContractVersion.contract_id == contract_id
        ).order_by(ContractVersion.version_number.desc()).all()

        versions_data = []
        for v in versions:
            versions_data.append({
                'id': v.id,
                'contract_id': v.contract_id,
                'version_number': v.version_number,
                'file_hash': v.file_hash,
                'source': v.source,
                'description': v.description,
                'is_current': v.is_current,
                'uploaded_at': v.uploaded_at.isoformat() if v.uploaded_at else None
            })

        return {
            'versions': versions_data,
            'total': len(versions_data)
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing versions: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error")


@router.post("/{contract_id}/compare", response_model=CompareResultResponse)
async def compare_versions(
    contract_id: str,
    request_data: CompareRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Compare two versions of a contract"""
    try:
        # Check contract exists
        contract = db.query(Contract).filter(Contract.id == contract_id).first()
        if not contract:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Contract not found")

        if contract.assigned_to != current_user.id and current_user.role not in ['admin']:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No permission")

        # Load both versions
        from_version = db.query(ContractVersion).filter(
            ContractVersion.id == request_data.from_version_id,
            ContractVersion.contract_id == contract_id
        ).first()
        to_version = db.query(ContractVersion).filter(
            ContractVersion.id == request_data.to_version_id,
            ContractVersion.contract_id == contract_id
        ).first()

        if not from_version or not to_version:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Version not found")

        # Check files exist
        if not os.path.exists(from_version.file_path):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Source version file not found on disk")
        if not os.path.exists(to_version.file_path):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Target version file not found on disk")

        # Parse both files
        parser = ExtendedDocumentParser()
        old_xml = parser.parse(from_version.file_path)
        new_xml = parser.parse(to_version.file_path)

        if not old_xml or not new_xml:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Failed to parse one or both files")

        # Run diff
        diff_service = DocumentDiffService()

        # Use text mode if XML parsing might fail (non-XML content)
        try:
            changes_raw = diff_service.compare_documents(old_xml, new_xml, mode='combined')
        except (ValueError, KeyError, AttributeError):
            changes_raw = diff_service.compare_documents(old_xml, new_xml, mode='text')

        # Build statistics
        by_type: Dict[str, int] = {}
        by_category: Dict[str, int] = {}
        changes_list: List[CompareChangeItem] = []

        for ch in changes_raw:
            ct = ch.get('change_type', 'modification')
            cc = ch.get('change_category', 'textual')
            by_type[ct] = by_type.get(ct, 0) + 1
            by_category[cc] = by_category.get(cc, 0) + 1

            # Extract clause number
            clause_num = diff_service.extract_clause_number(
                ch.get('old_content') or ch.get('new_content') or '',
                ch.get('xpath_location')
            )

            changes_list.append(CompareChangeItem(
                change_type=ct,
                change_category=cc,
                section_name=ch.get('section_name'),
                clause_number=clause_num,
                old_content=ch.get('old_content'),
                new_content=ch.get('new_content'),
                xpath_location=ch.get('xpath_location')
            ))

        total_changes = len(changes_list)

        # Determine overall assessment
        additions = by_type.get('addition', 0)
        deletions = by_type.get('deletion', 0)
        if total_changes == 0:
            assessment = 'neutral'
        elif deletions > additions * 2:
            assessment = 'unfavorable'
        elif additions > deletions * 2:
            assessment = 'favorable'
        else:
            assessment = 'mixed'

        summary = f"Обнаружено {total_changes} изменений: {by_type.get('addition', 0)} добавлений, {by_type.get('deletion', 0)} удалений, {by_type.get('modification', 0)} модификаций."

        # Save changes to DB
        for ch_item in changes_list:
            db_change = ContractChange(
                from_version_id=from_version.id,
                to_version_id=to_version.id,
                change_type=ch_item.change_type,
                change_category=ch_item.change_category,
                xpath_location=ch_item.xpath_location,
                section_name=ch_item.section_name,
                clause_number=ch_item.clause_number,
                old_content=ch_item.old_content,
                new_content=ch_item.new_content,
                detected_by='DocumentDiffService',
                confidence_score=1.0
            )
            db.add(db_change)

        # Save analysis result
        analysis_result = ChangeAnalysisResult(
            from_version_id=from_version.id,
            to_version_id=to_version.id,
            total_changes=total_changes,
            by_type=by_type,
            by_category=by_category,
            overall_assessment=assessment,
            executive_summary=summary,
            analyzed_by='DocumentDiffService'
        )
        db.add(analysis_result)
        db.commit()

        logger.info(f"Compared versions {from_version.version_number} vs {to_version.version_number} for contract {contract_id}: {total_changes} changes")

        return CompareResultResponse(
            total_changes=total_changes,
            by_type=by_type,
            by_category=by_category,
            overall_assessment=assessment,
            changes=changes_list,
            executive_summary=summary
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error comparing versions: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error")
