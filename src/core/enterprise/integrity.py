"""
Integrity Service — tracking hashes, verification, version linkage.

Обеспечивает целостность данных: хеширование документов,
верификация целостности цепочки версий, tamper detection.

Records хранятся в БД (таблица integrity_records) для persistence
между перезапусками.
"""
from __future__ import annotations
import hashlib
import json
from datetime import datetime, timezone
from typing import Any
from loguru import logger
from sqlalchemy import Column, DateTime, Index, JSON, String, Text
from sqlalchemy.orm import Session

from src.models.database import Base, generate_uuid


class IntegrityRecord(Base):
    """Запись целостности (persistent в БД)."""

    __tablename__ = "integrity_records"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    entity_type = Column(String(100), nullable=False, index=True)
    entity_id = Column(String(100), nullable=False, index=True)
    hash_value = Column(String(128), nullable=False)
    algorithm = Column(String(20), nullable=False, default="sha256")
    metadata_ = Column("metadata", JSON, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        Index("idx_integrity_entity", "entity_type", "entity_id", unique=True),
    )

    def __repr__(self) -> str:
        return f"<IntegrityRecord({self.entity_type}:{self.entity_id}, hash={self.hash_value[:16]}...)>"


class IntegrityService:
    """Сервис отслеживания целостности данных (DB-backed)."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def compute_hash(self, content: str | bytes, algorithm: str = "sha256") -> str:
        """Вычислить hash содержимого."""
        if isinstance(content, str):
            content = content.encode("utf-8")
        h = hashlib.new(algorithm)
        h.update(content)
        return h.hexdigest()

    def compute_document_hash(self, document_data: dict[str, Any]) -> str:
        """Вычислить hash документа (стабильная сериализация)."""
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
        """Зарегистрировать запись целостности (upsert в БД)."""
        if isinstance(content, dict):
            hash_value = self.compute_document_hash(content)
        else:
            hash_value = self.compute_hash(content, algorithm)

        # Upsert: обновить если существует, создать если нет
        record = (
            self.db.query(IntegrityRecord)
            .filter(
                IntegrityRecord.entity_type == entity_type,
                IntegrityRecord.entity_id == entity_id,
            )
            .first()
        )
        if record:
            record.hash_value = hash_value
            record.algorithm = algorithm
            record.metadata_ = metadata
            record.created_at = datetime.now(timezone.utc)
        else:
            record = IntegrityRecord(
                entity_type=entity_type,
                entity_id=entity_id,
                hash_value=hash_value,
                algorithm=algorithm,
                metadata_=metadata,
            )
            self.db.add(record)

        self.db.flush()

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
        record = (
            self.db.query(IntegrityRecord)
            .filter(
                IntegrityRecord.entity_type == entity_type,
                IntegrityRecord.entity_id == entity_id,
            )
            .first()
        )
        if record is None:
            return False, f"Запись целостности не найдена: {entity_type}:{entity_id}"

        if isinstance(content, dict):
            current_hash = self.compute_document_hash(content)
        else:
            current_hash = self.compute_hash(content, record.algorithm)

        if current_hash == record.hash_value:
            return True, "Целостность подтверждена"
        else:
            logger.warning(
                f"Integrity violation: {entity_type}:{entity_id}, "
                f"expected={record.hash_value[:16]}, got={current_hash[:16]}"
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
        from sqlalchemy import func

        total = self.db.query(func.count(IntegrityRecord.id)).scalar() or 0
        type_counts = (
            self.db.query(IntegrityRecord.entity_type, func.count(IntegrityRecord.id))
            .group_by(IntegrityRecord.entity_type)
            .all()
        )
        return {
            "total_records": total,
            "by_type": {t: c for t, c in type_counts},
        }
