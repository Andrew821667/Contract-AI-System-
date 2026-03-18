# -*- coding: utf-8 -*-
"""
Contract Listing Routes
"""
import os
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from loguru import logger

from src.models.database import get_db
from src.models import Contract, AnalysisResult
from src.models.auth_models import User
from src.api.dependencies import get_current_user

from .schemas import ContractListResponse


router = APIRouter()


@router.get("", response_model=ContractListResponse)
async def list_contracts(
    page: int = 1,
    page_size: int = 20,
    status: Optional[str] = None,
    contract_type: Optional[str] = None,
    search: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    List contracts for current user

    **Filters:**
    - status: uploaded, analyzing, completed, error
    - contract_type: supply, service, lease, etc.

    **Returns:** Paginated list of contracts
    """
    try:
        # Cap page_size
        if page_size > 100:
            page_size = 100
        if page < 1:
            page = 1

        query = db.query(Contract)

        # Filter by user (non-admins can only see their own contracts)
        if current_user.role not in ['admin']:
            query = query.filter(Contract.assigned_to == current_user.id)

        # Apply filters
        if status:
            query = query.filter(Contract.status == status)
        if contract_type:
            query = query.filter(Contract.contract_type == contract_type)
        if search:
            safe_search = search.replace('%', r'\%').replace('_', r'\_')
            query = query.filter(
                Contract.file_name.ilike(f'%{safe_search}%', escape='\\')
            )

        # Get total count
        total = query.count()

        # Paginate
        contracts = query.order_by(Contract.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()

        # Format response
        contracts_data = []
        for contract in contracts:
            contracts_data.append({
                'id': contract.id,
                'file_name': contract.file_name,
                'status': contract.status,
                'contract_type': contract.contract_type,
                'created_at': contract.created_at.isoformat() if contract.created_at else None,
                'updated_at': contract.updated_at.isoformat() if contract.updated_at else None
            })

        return ContractListResponse(
            contracts=contracts_data,
            total=total,
            page=page,
            page_size=page_size
        )

    except Exception as e:
        logger.error(f"Error listing contracts: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


@router.get("/{contract_id}")
async def get_contract_details(
    contract_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get contract details including analysis results"""
    try:
        contract = db.query(Contract).filter(Contract.id == contract_id).first()
        if not contract:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Contract not found"
            )

        # Check ownership
        if contract.assigned_to != current_user.id and current_user.role not in ['admin']:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have permission to view this contract"
            )

        # Get analysis results if available
        analysis = db.query(AnalysisResult).filter(AnalysisResult.contract_id == contract_id).first()

        return {
            'contract': {
                'id': contract.id,
                'file_name': contract.file_name,
                'status': contract.status,
                'contract_type': contract.contract_type,
                'created_at': contract.created_at.isoformat() if contract.created_at else None,
                'updated_at': contract.updated_at.isoformat() if contract.updated_at else None,
            },
            'analysis': {
                'id': analysis.id if analysis else None,
                'risks': analysis.risks_by_category if analysis else [],
                'recommendations': analysis.recommendations if analysis else [],
                'status': analysis.status if analysis else None
            } if analysis else None
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting contract details: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )


@router.get("/{contract_id}/download")
async def download_contract(
    contract_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Download original contract file"""
    try:
        contract = db.query(Contract).filter(Contract.id == contract_id).first()
        if not contract:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Contract not found"
            )

        # Check ownership
        if contract.assigned_to != current_user.id and current_user.role not in ['admin']:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have permission to download this contract"
            )

        if not os.path.exists(contract.file_path):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Contract file not found on disk"
            )

        return FileResponse(
            path=contract.file_path,
            filename=contract.file_name,
            media_type='application/octet-stream'
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error downloading contract: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )
