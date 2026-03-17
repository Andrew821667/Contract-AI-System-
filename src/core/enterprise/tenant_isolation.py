"""
Tenant Isolation Service — изоляция данных между tenant'ами.

Гарантирует, что запросы к данным фильтруются по tenant/org.
Обеспечивает sensitive field masking.
"""
from __future__ import annotations
from typing import Any
from loguru import logger
from sqlalchemy.orm import Session, Query


# Fields that should be masked in responses based on sensitivity level
SENSITIVE_FIELDS: dict[str, list[str]] = {
    "standard": [],  # No masking
    "confidential": [
        "counterparty_inn",
        "counterparty_kpp",
        "bank_account",
        "signatory_passport",
    ],
    "restricted": [
        "counterparty_inn",
        "counterparty_kpp",
        "bank_account",
        "signatory_passport",
        "contract_amount",
        "payment_schedule",
        "penalty_details",
        "signatory_name",
        "signatory_position",
    ],
}


class TenantIsolationService:
    """Сервис изоляции данных tenant'ов."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def apply_tenant_filter(
        self,
        query: Query,
        model_class: Any,
        org_id: str | None = None,
        user_id: str | None = None,
    ) -> Query:
        """Применить фильтр tenant isolation к запросу."""
        # Filter by org_id if model has it
        if org_id and hasattr(model_class, "organization_id"):
            query = query.filter(model_class.organization_id == org_id)
        elif org_id and hasattr(model_class, "org_id"):
            query = query.filter(model_class.org_id == org_id)
        # Filter by user_id if needed (personal data)
        if user_id and hasattr(model_class, "user_id"):
            query = query.filter(model_class.user_id == user_id)
        return query

    def mask_sensitive_fields(
        self,
        data: dict[str, Any],
        sensitivity_level: str = "standard",
    ) -> dict[str, Any]:
        """Замаскировать чувствительные поля."""
        fields_to_mask = SENSITIVE_FIELDS.get(sensitivity_level, [])
        if not fields_to_mask:
            return data
        masked = dict(data)
        for field in fields_to_mask:
            if field in masked and masked[field] is not None:
                value = str(masked[field])
                if len(value) <= 4:
                    masked[field] = "***"
                else:
                    masked[field] = value[:2] + "*" * (len(value) - 4) + value[-2:]
        return masked

    def check_cross_tenant_access(
        self,
        requesting_org_id: str,
        target_org_id: str,
    ) -> bool:
        """Проверить, разрешён ли cross-tenant доступ."""
        if requesting_org_id == target_org_id:
            return True
        # Cross-tenant access not allowed by default
        logger.warning(
            f"Cross-tenant access denied: {requesting_org_id} → {target_org_id}"
        )
        return False

    def get_masked_fields_for_level(self, sensitivity_level: str) -> list[str]:
        """Получить список полей, маскируемых на данном уровне."""
        return SENSITIVE_FIELDS.get(sensitivity_level, [])
