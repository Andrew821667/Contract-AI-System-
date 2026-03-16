"""Clause Policy Service — управление политиками использования клауз."""

from __future__ import annotations

from sqlalchemy.orm import Session

from .models import ClausePolicy


class ClausePolicyService:
    """Сервис политик клауз."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def get_policy(self, org_id: str | None, clause_type: str) -> ClausePolicy | None:
        """Получить политику для типа клаузы (org-specific → platform fallback)."""
        if org_id:
            policy = self.db.query(ClausePolicy).filter(
                ClausePolicy.org_id == org_id,
                ClausePolicy.clause_type == clause_type,
            ).first()
            if policy:
                return policy

        # Fallback на platform-level (org_id IS NULL)
        return self.db.query(ClausePolicy).filter(
            ClausePolicy.org_id.is_(None),
            ClausePolicy.clause_type == clause_type,
        ).first()

    def is_clause_allowed(self, org_id: str | None, clause_type: str) -> bool:
        """Проверить, разрешена ли клауза."""
        policy = self.get_policy(org_id, clause_type)
        if not policy:
            return True  # Нет политики — разрешено
        return policy.status in ("approved", "fallback")

    def get_prohibited_clauses(self, org_id: str | None) -> list[ClausePolicy]:
        """Список запрещённых клауз для организации."""
        query = self.db.query(ClausePolicy).filter(ClausePolicy.status == "prohibited")
        if org_id:
            from sqlalchemy import or_
            query = query.filter(or_(
                ClausePolicy.org_id == org_id,
                ClausePolicy.org_id.is_(None),
            ))
        else:
            query = query.filter(ClausePolicy.org_id.is_(None))
        return query.all()
