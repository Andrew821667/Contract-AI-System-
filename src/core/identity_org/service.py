"""
Identity & Organization — OrganizationContextService.

Предоставляет контекст текущего пользователя:
- В какой организации состоит
- Какая роль (functional + company)
- Какой tenant mode (standalone / branch)
- Какие AI-policy для него действуют
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from .models import (
    DocumentParticipation,
    Organization,
    OrganizationMembership,
    TenantContext,
    UserAgentPolicyProfile,
)


class OrganizationContextService:
    """Сервис для получения org/tenant контекста пользователя."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def get_organization(self, org_id: str) -> Organization | None:
        """Получить организацию по ID."""
        return (
            self.db.query(Organization)
            .filter(Organization.id == org_id, Organization.active.is_(True))
            .first()
        )

    def get_user_organizations(self, user_id: str) -> list[Organization]:
        """Все активные организации пользователя."""
        memberships = (
            self.db.query(OrganizationMembership)
            .filter(
                OrganizationMembership.user_id == user_id,
                OrganizationMembership.active.is_(True),
            )
            .all()
        )
        org_ids = [m.org_id for m in memberships]
        if not org_ids:
            return []
        return (
            self.db.query(Organization)
            .filter(Organization.id.in_(org_ids), Organization.active.is_(True))
            .all()
        )

    def get_membership(self, user_id: str, org_id: str) -> OrganizationMembership | None:
        """Получить membership пользователя в организации."""
        return (
            self.db.query(OrganizationMembership)
            .filter(
                OrganizationMembership.user_id == user_id,
                OrganizationMembership.org_id == org_id,
                OrganizationMembership.active.is_(True),
            )
            .first()
        )

    def get_tenant_context(self, org_id: str) -> TenantContext | None:
        """Получить tenant context организации."""
        return (
            self.db.query(TenantContext)
            .filter(TenantContext.org_id == org_id)
            .first()
        )

    def get_document_roles(self, user_id: str, document_id: str) -> list[str]:
        """Список ролей пользователя для конкретного документа."""
        participations = (
            self.db.query(DocumentParticipation)
            .filter(
                DocumentParticipation.user_id == user_id,
                DocumentParticipation.document_id == document_id,
            )
            .all()
        )
        return [p.role for p in participations]

    def get_agent_policy_profile(
        self, user_id: str, org_id: str | None = None
    ) -> UserAgentPolicyProfile | None:
        """AI-policy профиль пользователя (org-specific или глобальный)."""
        query = self.db.query(UserAgentPolicyProfile).filter(
            UserAgentPolicyProfile.user_id == user_id,
        )
        if org_id:
            # Сначала ищем org-specific
            profile = query.filter(UserAgentPolicyProfile.org_id == org_id).first()
            if profile:
                return profile
        # Fallback на глобальный (org_id IS NULL)
        return query.filter(UserAgentPolicyProfile.org_id.is_(None)).first()

    def add_membership(
        self,
        user_id: str,
        org_id: str,
        functional_role: str = "member",
        company_role: str | None = None,
        unit_id: str | None = None,
    ) -> OrganizationMembership:
        """Добавить пользователя в организацию."""
        membership = OrganizationMembership(
            user_id=user_id,
            org_id=org_id,
            unit_id=unit_id,
            company_role=company_role,
            functional_role=functional_role,
        )
        self.db.add(membership)
        self.db.flush()
        return membership

    def add_document_participation(
        self,
        user_id: str,
        document_id: str,
        role: str,
        assigned_by: str | None = None,
    ) -> DocumentParticipation:
        """Назначить роль пользователю на документе."""
        participation = DocumentParticipation(
            user_id=user_id,
            document_id=document_id,
            role=role,
            assigned_by=assigned_by,
        )
        self.db.add(participation)
        self.db.flush()
        return participation
