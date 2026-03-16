"""Template Governance — управление версиями шаблонов."""

from __future__ import annotations

from sqlalchemy.orm import Session

from .models import TemplateVersion


class TemplateGovernanceService:
    """Сервис управления версиями шаблонов."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def get_active_version(self, template_id: str) -> TemplateVersion | None:
        """Получить активную версию шаблона."""
        return (
            self.db.query(TemplateVersion)
            .filter(
                TemplateVersion.template_id == template_id,
                TemplateVersion.status == "active",
            )
            .first()
        )

    def create_version(
        self,
        template_id: str,
        content: dict,
        variables: list | None = None,
        validation_rules: dict | None = None,
        created_by: str | None = None,
    ) -> TemplateVersion:
        """Создать новую версию шаблона."""
        # Найти максимальную версию
        max_ver = (
            self.db.query(TemplateVersion.version)
            .filter(TemplateVersion.template_id == template_id)
            .order_by(TemplateVersion.version.desc())
            .first()
        )
        next_version = (max_ver[0] + 1) if max_ver else 1

        version = TemplateVersion(
            template_id=template_id,
            version=next_version,
            content=content,
            variables=variables,
            validation_rules=validation_rules,
            status="draft",
            created_by=created_by,
        )
        self.db.add(version)
        self.db.flush()
        return version

    def activate_version(self, version_id: str) -> TemplateVersion | None:
        """Активировать версию (деактивировать предыдущую)."""
        version = self.db.query(TemplateVersion).filter(TemplateVersion.id == version_id).first()
        if not version:
            return None

        # Деактивировать текущую активную
        self.db.query(TemplateVersion).filter(
            TemplateVersion.template_id == version.template_id,
            TemplateVersion.status == "active",
        ).update({"status": "deprecated"})

        version.status = "active"
        self.db.flush()
        return version
