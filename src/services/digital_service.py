# -*- coding: utf-8 -*-
"""
Digital Contract Service
SHA-256 hashing, HMAC signing, hash-chain & DAG verification
"""
import hashlib
import hmac
import json
import os
from datetime import datetime
from typing import Optional, List, Dict, Any

from sqlalchemy.orm import Session
from loguru import logger

from src.models.digital_models import DigitalContract
from src.models.database import Contract, generate_uuid
from src.models.auth_models import AuditLog
from config.settings import settings


class DigitalContractService:
    """Service for digital contract integrity operations"""

    def __init__(self, db: Session):
        self.db = db

    @staticmethod
    def _compute_hash(content: bytes) -> str:
        """Compute SHA-256 hash of content"""
        return hashlib.sha256(content).hexdigest()

    @staticmethod
    def _compute_signature(content_hash: str) -> str:
        """Compute HMAC-SHA256 signature using server secret key"""
        key = settings.secret_key.encode() if settings.secret_key else b"dev-fallback-key"
        return hmac.new(key, content_hash.encode(), hashlib.sha256).hexdigest()

    @staticmethod
    def _verify_signature(content_hash: str, signature: str) -> bool:
        """Verify HMAC signature"""
        expected = DigitalContractService._compute_signature(content_hash)
        return hmac.compare_digest(expected, signature)

    def digitalize(
        self,
        contract_id: str,
        file_content: bytes,
        user_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> DigitalContract:
        """
        Create a digital version of a contract.
        Computes SHA-256 hash, signs with HMAC, links to parent version.
        """
        # Verify contract exists
        contract = self.db.query(Contract).filter(Contract.id == contract_id).first()
        if not contract:
            raise ValueError(f"Contract {contract_id} not found")

        # Compute hash and signature
        content_hash = self._compute_hash(file_content)
        signature = self._compute_signature(content_hash)

        # Determine version number and parent
        latest = (
            self.db.query(DigitalContract)
            .filter(
                DigitalContract.contract_id == contract_id,
                DigitalContract.status == "active",
            )
            .order_by(DigitalContract.version.desc())
            .first()
        )

        version = (latest.version + 1) if latest else 1
        parent_id = latest.id if latest else None

        # Mark previous version as superseded
        if latest:
            latest.status = "superseded"

        # Create digital contract record
        digital = DigitalContract(
            id=generate_uuid(),
            contract_id=contract_id,
            version=version,
            content_hash=content_hash,
            signature=signature,
            parent_id=parent_id,
            status="active",
            metadata_json=json.dumps(metadata) if metadata else None,
            created_by=user_id,
        )
        self.db.add(digital)

        # Audit log
        audit = AuditLog(
            user_id=user_id,
            action="digital_contract_created",
            resource_type="digital_contract",
            resource_id=digital.id,
            status="success",
            details={"contract_id": contract_id, "version": version, "content_hash": content_hash[:16] + "..."},
            severity="info",
        )
        self.db.add(audit)

        self.db.commit()
        self.db.refresh(digital)

        logger.info(f"Digitalized contract {contract_id} → v{version} (hash={content_hash[:16]}...)")
        return digital

    def verify(self, digital_id: str) -> Dict[str, Any]:
        """
        Verify the integrity of a digital contract.
        Checks HMAC signature and optionally re-hashes the file from disk.
        """
        digital = self.db.query(DigitalContract).filter(DigitalContract.id == digital_id).first()
        if not digital:
            raise ValueError(f"Digital contract {digital_id} not found")

        # Verify HMAC signature
        signature_valid = self._verify_signature(digital.content_hash, digital.signature)

        # Try to verify content hash from file on disk
        content_hash_match = None
        contract = self.db.query(Contract).filter(Contract.id == digital.contract_id).first()
        if contract and contract.file_path and os.path.exists(contract.file_path):
            with open(contract.file_path, "rb") as f:
                file_content = f.read()
            actual_hash = self._compute_hash(file_content)
            content_hash_match = actual_hash == digital.content_hash

        # Verify chain integrity (parent signature)
        chain_valid = True
        if digital.parent_id:
            parent = self.db.query(DigitalContract).filter(DigitalContract.id == digital.parent_id).first()
            if parent:
                chain_valid = self._verify_signature(parent.content_hash, parent.signature)

        valid = signature_valid and (content_hash_match is not False) and chain_valid

        return {
            "valid": valid,
            "digital_id": digital.id,
            "version": digital.version,
            "content_hash": digital.content_hash,
            "content_hash_match": content_hash_match,
            "signature_valid": signature_valid,
            "chain_valid": chain_valid,
            "status": digital.status,
            "created_at": digital.created_at.isoformat() if digital.created_at else None,
        }

    def get_chain(self, contract_id: str) -> List[Dict[str, Any]]:
        """Return linear hash-chain of all digital versions for a contract"""
        versions = (
            self.db.query(DigitalContract)
            .filter(DigitalContract.contract_id == contract_id)
            .order_by(DigitalContract.version.asc())
            .all()
        )

        chain = []
        for v in versions:
            chain.append({
                "id": v.id,
                "version": v.version,
                "content_hash": v.content_hash,
                "signature": v.signature,
                "parent_id": v.parent_id,
                "status": v.status,
                "created_by": v.created_by,
                "created_at": v.created_at.isoformat() if v.created_at else None,
            })

        return chain

    def get_dag(self, contract_id: str) -> Dict[str, Any]:
        """Return DAG structure for contracts with merge scenarios"""
        versions = (
            self.db.query(DigitalContract)
            .filter(DigitalContract.contract_id == contract_id)
            .order_by(DigitalContract.version.asc())
            .all()
        )

        nodes = []
        edges = []
        for v in versions:
            nodes.append({
                "id": v.id,
                "version": v.version,
                "content_hash": v.content_hash,
                "status": v.status,
                "created_at": v.created_at.isoformat() if v.created_at else None,
            })

            # Linear chain edge
            if v.parent_id:
                edges.append({"from": v.parent_id, "to": v.id, "type": "chain"})

            # DAG edges from parent_ids (merge)
            if v.parent_ids:
                try:
                    parent_list = json.loads(v.parent_ids)
                    for pid in parent_list:
                        edges.append({"from": pid, "to": v.id, "type": "merge"})
                except (json.JSONDecodeError, TypeError):
                    pass

        return {"nodes": nodes, "edges": edges}

    def revoke(self, digital_id: str, user_id: Optional[str] = None) -> DigitalContract:
        """Revoke a digital contract version"""
        digital = self.db.query(DigitalContract).filter(DigitalContract.id == digital_id).first()
        if not digital:
            raise ValueError(f"Digital contract {digital_id} not found")

        digital.status = "revoked"

        # Audit log
        audit = AuditLog(
            user_id=user_id,
            action="digital_contract_revoked",
            resource_type="digital_contract",
            resource_id=digital.id,
            status="success",
            details={"contract_id": digital.contract_id, "version": digital.version},
            severity="warning",
        )
        self.db.add(audit)

        self.db.commit()
        self.db.refresh(digital)

        logger.info(f"Revoked digital contract {digital_id} (contract={digital.contract_id}, v={digital.version})")
        return digital

    def get_versions(self, contract_id: str) -> List[Dict[str, Any]]:
        """Get all digital versions for a contract"""
        versions = (
            self.db.query(DigitalContract)
            .filter(DigitalContract.contract_id == contract_id)
            .order_by(DigitalContract.version.desc())
            .all()
        )

        return [
            {
                "id": v.id,
                "contract_id": v.contract_id,
                "version": v.version,
                "content_hash": v.content_hash,
                "signature": v.signature,
                "parent_id": v.parent_id,
                "status": v.status,
                "metadata": json.loads(v.metadata_json) if v.metadata_json else None,
                "created_by": v.created_by,
                "created_at": v.created_at.isoformat() if v.created_at else None,
            }
            for v in versions
        ]
