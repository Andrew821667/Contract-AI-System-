"""
RBAC Service — Role-Based Access Control.

Roles -> Permissions -> Actions.
Проверка доступа для API endpoints и AI actions.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any
from loguru import logger
from sqlalchemy.orm import Session


@dataclass(frozen=True)
class Permission:
    """Описание разрешения."""
    name: str
    description: str
    resource: str  # contract, workflow, ai_session, policy, organization, ...
    action: str    # read, write, execute, admin, ...


# ── Каталог разрешений ──────────────────────────
PERMISSIONS: dict[str, Permission] = {}

def _p(name: str, description: str, resource: str, action: str) -> Permission:
    perm = Permission(name=name, description=description, resource=resource, action=action)
    PERMISSIONS[name] = perm
    return perm

# Contract
CONTRACT_READ = _p("contract.read", "Просмотр документов", "contract", "read")
CONTRACT_WRITE = _p("contract.write", "Создание/редактирование документов", "contract", "write")
CONTRACT_DELETE = _p("contract.delete", "Удаление документов", "contract", "delete")
CONTRACT_APPROVE = _p("contract.approve", "Одобрение документов", "contract", "approve")
CONTRACT_EXPORT = _p("contract.export", "Экспорт документов", "contract", "export")

# AI
AI_SESSION_CREATE = _p("ai.session.create", "Создание AI сессий", "ai_session", "write")
AI_SESSION_READ = _p("ai.session.read", "Просмотр AI сессий", "ai_session", "read")
AI_ACTION_EXECUTE = _p("ai.action.execute", "Выполнение AI действий", "ai_action", "execute")
AI_ACTION_APPROVE = _p("ai.action.approve", "Одобрение AI действий", "ai_action", "approve")

# Workflow
WORKFLOW_READ = _p("workflow.read", "Просмотр процессов", "workflow", "read")
WORKFLOW_MANAGE = _p("workflow.manage", "Управление процессами", "workflow", "admin")
WORKFLOW_TASK_COMPLETE = _p("workflow.task.complete", "Завершение задач", "workflow", "execute")

# Negotiation
NEGOTIATION_CREATE = _p("negotiation.create", "Создание переговоров", "negotiation", "write")
NEGOTIATION_READ = _p("negotiation.read", "Просмотр переговоров", "negotiation", "read")

# Policy
POLICY_READ = _p("policy.read", "Просмотр политик", "policy", "read")
POLICY_MANAGE = _p("policy.manage", "Управление политиками", "policy", "admin")

# Organization
ORG_READ = _p("org.read", "Просмотр организации", "organization", "read")
ORG_MANAGE = _p("org.manage", "Управление организацией", "organization", "admin")
ORG_MEMBERS = _p("org.members", "Управление участниками", "organization", "write")

# Integration
INTEGRATION_READ = _p("integration.read", "Просмотр интеграций", "integration", "read")
INTEGRATION_MANAGE = _p("integration.manage", "Управление интеграциями", "integration", "admin")

# Admin
ADMIN_FULL = _p("admin.full", "Полный доступ администратора", "system", "admin")


# ── Role -> Permissions маппинг ──────────────────
ROLE_PERMISSIONS: dict[str, list[str]] = {
    "viewer": [
        "contract.read", "ai.session.read", "workflow.read",
        "negotiation.read", "org.read", "integration.read",
    ],
    "editor": [
        "contract.read", "contract.write", "contract.export",
        "ai.session.create", "ai.session.read", "ai.action.execute",
        "workflow.read", "workflow.task.complete",
        "negotiation.create", "negotiation.read",
        "org.read", "integration.read",
    ],
    "reviewer": [
        "contract.read", "contract.write", "contract.approve",
        "ai.session.create", "ai.session.read", "ai.action.execute", "ai.action.approve",
        "workflow.read", "workflow.task.complete", "workflow.manage",
        "negotiation.create", "negotiation.read",
        "org.read", "integration.read",
    ],
    "org_admin": [
        "contract.read", "contract.write", "contract.delete", "contract.approve", "contract.export",
        "ai.session.create", "ai.session.read", "ai.action.execute", "ai.action.approve",
        "workflow.read", "workflow.task.complete", "workflow.manage",
        "negotiation.create", "negotiation.read",
        "policy.read", "policy.manage",
        "org.read", "org.manage", "org.members",
        "integration.read", "integration.manage",
    ],
    "platform_admin": [
        "admin.full",  # Everything
    ],
}


# ── Legacy role mapping (v1 User.role → v2 RBAC role) ────
LEGACY_ROLE_MAP: dict[str, str] = {
    "admin": "platform_admin",
    "senior_lawyer": "reviewer",
    "user": "editor",
    "demo": "viewer",
}


class RBACService:
    """Сервис проверки ролей и разрешений."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def get_user_permissions(self, user_id: str, org_id: str | None = None) -> list[str]:
        """Получить все разрешения пользователя (из ролей)."""
        roles = self._get_user_roles(user_id, org_id)
        permissions: set[str] = set()
        for role in roles:
            role_perms = ROLE_PERMISSIONS.get(role, [])
            permissions.update(role_perms)
        # admin.full means everything
        if "admin.full" in permissions:
            permissions = set(PERMISSIONS.keys())
        return sorted(permissions)

    def has_permission(self, user_id: str, permission: str, org_id: str | None = None) -> bool:
        """Проверить, есть ли у пользователя разрешение."""
        perms = self.get_user_permissions(user_id, org_id)
        return permission in perms

    def check_permission(self, user_id: str, permission: str, org_id: str | None = None) -> None:
        """Проверить разрешение, выбросить PermissionError если нет."""
        if not self.has_permission(user_id, permission, org_id):
            raise PermissionError(
                f"Недостаточно прав: требуется '{permission}' для пользователя {user_id}"
            )

    def get_role_permissions(self, role: str) -> list[str]:
        """Получить все разрешения роли."""
        perms = ROLE_PERMISSIONS.get(role, [])
        if "admin.full" in perms:
            return sorted(PERMISSIONS.keys())
        return sorted(perms)

    def _get_user_roles(self, user_id: str, org_id: str | None = None) -> list[str]:
        """Получить роли пользователя из DB."""
        roles: list[str] = []
        # 1. Check OrganizationMembership
        if org_id:
            try:
                from src.core.identity_org.models import OrganizationMembership
                membership = self.db.query(OrganizationMembership).filter(
                    OrganizationMembership.user_id == user_id,
                    OrganizationMembership.organization_id == org_id,
                    OrganizationMembership.active.is_(True),
                ).first()
                if membership:
                    roles.append(membership.functional_role or "viewer")
            except Exception as exc:
                from loguru import logger
                logger.error(f"RBAC: failed to load org membership for user={user_id}, org={org_id}: {exc}")
        # 2. Check User.role
        try:
            from src.models.auth_models import User
            user = self.db.query(User).filter(User.id == user_id).first()
            if user and hasattr(user, "role"):
                role_name = getattr(user, "role", None)
                if role_name:
                    # Map legacy v1 roles to v2 RBAC roles
                    mapped = LEGACY_ROLE_MAP.get(role_name, role_name)
                    if mapped not in roles:
                        roles.append(mapped)
        except Exception as exc:
            from loguru import logger
            logger.error(f"RBAC: failed to load user role for user={user_id}: {exc}")
        return roles or ["viewer"]  # Default to viewer
