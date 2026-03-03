# -*- coding: utf-8 -*-
"""
Digital Contract Verification API Routes
Hash-chain, DAG, and integrity verification endpoints
"""
import os
from typing import List, Dict, Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from loguru import logger

from src.models.database import get_db, Contract
from src.models.auth_models import User
from src.services.digital_service import DigitalContractService
from src.api.contracts.routes import get_current_user


router = APIRouter()


# ==================== DIGITALIZE ====================

@router.post("/{contract_id}/digitalize")
async def digitalize_contract(
    contract_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Create a digital version of a contract with SHA-256 hash and HMAC signature.
    Reads the contract file from disk, computes hash, signs, and stores in DB.
    """
    try:
        # Get contract and read file
        contract = db.query(Contract).filter(Contract.id == contract_id).first()
        if not contract:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Contract not found")

        if not contract.file_path or not os.path.exists(contract.file_path):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Contract file not found on disk")

        with open(contract.file_path, "rb") as f:
            file_content = f.read()

        service = DigitalContractService(db)
        digital = service.digitalize(
            contract_id=contract_id,
            file_content=file_content,
            user_id=current_user.id,
        )

        return {
            "id": digital.id,
            "contract_id": digital.contract_id,
            "version": digital.version,
            "content_hash": digital.content_hash,
            "signature": digital.signature,
            "parent_id": digital.parent_id,
            "status": digital.status,
            "created_at": digital.created_at.isoformat() if digital.created_at else None,
        }

    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error digitalizing contract {contract_id}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


# ==================== LIST DIGITAL VERSIONS ====================

@router.get("/{contract_id}/digital")
async def get_digital_versions(
    contract_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get all digital versions for a contract"""
    try:
        service = DigitalContractService(db)
        versions = service.get_versions(contract_id)
        return {"versions": versions, "total": len(versions)}
    except Exception as e:
        logger.error(f"Error getting digital versions for {contract_id}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


# ==================== VERIFY ====================

@router.get("/{contract_id}/digital/{digital_id}/verify")
async def verify_digital_contract(
    contract_id: str,
    digital_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Verify integrity of a specific digital contract version"""
    try:
        service = DigitalContractService(db)
        result = service.verify(digital_id)
        return result
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        logger.error(f"Error verifying digital contract {digital_id}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


# ==================== HASH CHAIN ====================

@router.get("/{contract_id}/digital/chain")
async def get_hash_chain(
    contract_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get the linear hash-chain of all digital versions"""
    try:
        service = DigitalContractService(db)
        chain = service.get_chain(contract_id)
        return {"chain": chain, "length": len(chain)}
    except Exception as e:
        logger.error(f"Error getting hash chain for {contract_id}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


# ==================== DAG ====================

@router.get("/{contract_id}/digital/dag")
async def get_dag(
    contract_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get the DAG structure (nodes + edges) for merge scenarios"""
    try:
        service = DigitalContractService(db)
        dag = service.get_dag(contract_id)
        return dag
    except Exception as e:
        logger.error(f"Error getting DAG for {contract_id}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
