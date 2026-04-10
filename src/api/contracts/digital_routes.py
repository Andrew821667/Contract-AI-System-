# -*- coding: utf-8 -*-
"""
Digital Contract Verification API Routes
Hash-chain, DAG, and integrity verification endpoints
"""
import os
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from loguru import logger

from src.models.database import get_db, Contract
from src.services.digital_service import DigitalContractService
from src.api.dependencies import get_contract_with_access_sync


router = APIRouter()


# ==================== DIGITALIZE ====================

@router.post("/{contract_id}/digitalize")
async def digitalize_contract(
    contract: Contract = Depends(get_contract_with_access_sync),
    db: Session = Depends(get_db),
):
    """
    Create a digital version of a contract with SHA-256 hash and HMAC signature.
    Reads the contract file from disk, computes hash, signs, and stores in DB.
    """
    try:
        if not contract.file_path or not os.path.exists(contract.file_path):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Contract file not found on disk")

        with open(contract.file_path, "rb") as f:
            file_content = f.read()

        service = DigitalContractService(db)
        digital = service.digitalize(
            contract_id=contract.id,
            file_content=file_content,
            user_id=contract.assigned_to,
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

    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid request for digitalization")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error digitalizing contract {contract.id}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error")


# ==================== LIST DIGITAL VERSIONS ====================

@router.get("/{contract_id}/digital")
async def get_digital_versions(
    contract: Contract = Depends(get_contract_with_access_sync),
    db: Session = Depends(get_db),
):
    """Get all digital versions for a contract"""
    try:
        service = DigitalContractService(db)
        versions = service.get_versions(contract.id)
        return {"versions": versions, "total": len(versions)}
    except Exception as e:
        logger.error(f"Error getting digital versions for {contract.id}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error")


# ==================== VERIFY ====================

@router.get("/{contract_id}/digital/{digital_id}/verify")
async def verify_digital_contract(
    digital_id: str,
    contract: Contract = Depends(get_contract_with_access_sync),
    db: Session = Depends(get_db),
):
    """Verify integrity of a specific digital contract version"""
    try:
        service = DigitalContractService(db)
        result = service.verify(digital_id)
        return result
    except ValueError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Digital contract not found")
    except Exception as e:
        logger.error(f"Error verifying digital contract {digital_id}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error")


# ==================== HASH CHAIN ====================

@router.get("/{contract_id}/digital/chain")
async def get_hash_chain(
    contract: Contract = Depends(get_contract_with_access_sync),
    db: Session = Depends(get_db),
):
    """Get the linear hash-chain of all digital versions"""
    try:
        service = DigitalContractService(db)
        chain = service.get_chain(contract.id)
        return {"chain": chain, "length": len(chain)}
    except Exception as e:
        logger.error(f"Error getting hash chain for {contract.id}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error")


# ==================== DAG ====================

@router.get("/{contract_id}/digital/dag")
async def get_dag(
    contract: Contract = Depends(get_contract_with_access_sync),
    db: Session = Depends(get_db),
):
    """Get the DAG structure (nodes + edges) for merge scenarios"""
    try:
        service = DigitalContractService(db)
        dag = service.get_dag(contract.id)
        return dag
    except Exception as e:
        logger.error(f"Error getting DAG for {contract.id}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error")
