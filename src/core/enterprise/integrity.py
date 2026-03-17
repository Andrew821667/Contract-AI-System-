"""
Integrity Service — tracking hashes, verification, version linkage.

Обеспечивает целостность данных: хеширование документов,
верификация целостности цепочки версий, tamper detection.
"""
from __future__ import annotations
import hashlib
import json
from datetime import datetime, timezone
from typing import Any
from loguru import logger
from sqlalchemy.orm import Session


class IntegrityRecord:
    """Запись целостности."""
    def __init__(
        self,
        entity_type: str,
        entity_id: str,
        hash_value: str,
        algorithm: str = "sha256",
        metadata: dict[str, Any] | None = None,
    ):
        self.entity_type = entity_type
        self.entity_id = entity_id
        self.hash_value = hash_value
        self.algorithm = algorithm
        self.metadata = metadata or {}
        self.created_at = datetime.now(timezone.utc)


class IntegrityService:
    """Сервис отслеживания целостности данных."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self._records: dict[str, IntegrityRecord] = {}

    def compute_hash(self, content: str | bytes, algorithm: str = "sha256") -> str:
        """Вычислить hash содержимого."""
        if isinstance(content, str):
            content = content.encode("utf-8")
        h = hashlib.new(algorithm)
        h.update(content)
        return h.hexdigest()

    def compute_document_hash(self, document_data: dict[str, Any]) -> str:
        """Вычислить hash документа (стабильная сериализация)."""
        # Stable JSON serialization
        canonical = json.dumps(document_data, sort_keys=True, ensure_ascii=False, default=str)
        return self.compute_hash(canonical)

    def register_integrity(
        self,
        entity_type: str,
        entity_id: str,
        content: str | bytes | dict[str, Any],
        algorithm: str = "sha256",
        metadata: dict[str, Any] | None = None,
    ) -> IntegrityRecord:
        """Зарегистрировать запись целостности."""
        if isinstance(content, dict):
            hash_value = self.compute_document_hash(content)
        else:
            hash_value = self.compute_hash(content, algorithm)

        record = IntegrityRecord(
            entity_type=entity_type,
            entity_id=entity_id,
            hash_value=hash_value,
            algorithm=algorithm,
            metadata=metadata,
        )
        key = f"{entity_type}:{entity_id}"
        self._records[key] = record

        logger.info(
            f"Integrity registered: {entity_type}:{entity_id} → {hash_value[:16]}..."
        )
        return record

    def verify_integrity(
        self,
        entity_type: str,
        entity_id: str,
        content: str | bytes | dict[str, Any],
    ) -> tuple[bool, str]:
        """
        Верифицировать целостность.

        Returns:
            (is_valid, message)
        """
        key = f"{entity_type}:{entity_id}"
        record = self._records.get(key)
        if record is None:
            return False, f"Запись целостности не найдена: {key}"

        if isinstance(content, dict):
            current_hash = self.compute_document_hash(content)
        else:
            current_hash = self.compute_hash(content, record.algorithm)

        if current_hash == record.hash_value:
            return True, "Целостность подтверждена"
        else:
            logger.warning(
                f"Integrity violation: {key}, expected={record.hash_value[:16]}, "
                f"got={current_hash[:16]}"
            )
            return False, (
                f"Нарушение целостности: ожидалось {record.hash_value[:16]}..., "
                f"получено {current_hash[:16]}..."
            )

    def verify_version_chain(
        self,
        document_id: str,
    ) -> dict[str, Any]:
        """
        Проверить целостность цепочки версий документа.
        """
        from src.models.changes_models import ContractVersion

        versions = (
            self.db.query(ContractVersion)
            .filter(ContractVersion.contract_id == document_id)
            .order_by(ContractVersion.version_number)
            .all()
        )

        if not versions:
            return {"valid": True, "message": "Версии не найдены", "versions": 0}

        issues: list[str] = []
        for v in versions:
            # Check hash exists
            if not v.file_hash:
                issues.append(f"v{v.version_number}: отсутствует hash")
            # Check parent linkage
            if v.parent_version_id:
                parent = next(
                    (p for p in versions if p.id == v.parent_version_id), None
                )
                if parent is None:
                    issues.append(
                        f"v{v.version_number}: parent_version_id не найден"
                    )

        return {
            "valid": len(issues) == 0,
            "versions": len(versions),
            "issues": issues,
            "message": "Цепочка версий целостна" if not issues else f"Найдено {len(issues)} проблем",
        }

    def get_integrity_status(self) -> dict[str, Any]:
        """Статус всех записей целостности."""
        return {
            "total_records": len(self._records),
            "by_type": {},
        }
