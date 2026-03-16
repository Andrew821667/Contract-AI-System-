# -*- coding: utf-8 -*-
"""
Seed Data — инициализация платформенных политик, тестовых организаций и пользователей.

Idempotent: безопасно вызвать повторно — перед созданием проверяет существование записей.

Запуск:
    source venv/bin/activate && python -m src.core.seed
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.orm import Session

from src.models.database import SessionLocal
from src.models.auth_models import User
from src.core.identity_org.models import (
    Organization,
    OrganizationMembership,
    TenantContext,
    UserAgentPolicyProfile,
)
from src.core.policies.models import ApprovalRule, Policy

logger = logging.getLogger(__name__)


# ── Helpers ──────────────────────────────────────────────────────────────────

def _get_or_create_policy(
    db: Session,
    *,
    name: str,
    level: str,
    policy_type: str,
    rules: dict[str, Any],
    scope_id: str | None = None,
    priority: int = 0,
    description: str | None = None,
) -> tuple[Policy, bool]:
    """Вернуть (policy, created). created=True если создана заново."""
    existing = (
        db.query(Policy)
        .filter(Policy.name == name, Policy.level == level, Policy.policy_type == policy_type)
        .first()
    )
    if existing:
        return existing, False

    policy = Policy(
        name=name,
        description=description,
        level=level,
        scope_id=scope_id,
        policy_type=policy_type,
        rules=rules,
        priority=priority,
    )
    db.add(policy)
    db.flush()
    return policy, True


def _get_or_create_approval_rule(
    db: Session,
    *,
    policy_id: str,
    action_pattern: str,
    required_approvers: int = 1,
) -> tuple[ApprovalRule, bool]:
    existing = (
        db.query(ApprovalRule)
        .filter(
            ApprovalRule.policy_id == policy_id,
            ApprovalRule.action_pattern == action_pattern,
        )
        .first()
    )
    if existing:
        return existing, False

    rule = ApprovalRule(
        policy_id=policy_id,
        action_pattern=action_pattern,
        required_approvers=required_approvers,
    )
    db.add(rule)
    db.flush()
    return rule, True


# ── Main seed function ───────────────────────────────────────────────────────

def seed_initial_data(db: Session) -> dict[str, Any]:
    """
    Создаёт начальные данные платформы (idempotent).

    Возвращает dict с созданными/найденными entity для логирования.
    """
    result: dict[str, Any] = {
        "policies": [],
        "approval_rules": [],
        "organization": None,
        "tenant_context": None,
        "memberships": [],
        "agent_policy_profiles": [],
    }

    # ── 1. Platform-level policies ───────────────────────────────────────

    # 1a. Базовая AI-автономность
    p1, created = _get_or_create_policy(
        db,
        name="Базовая AI-автономность",
        level="platform",
        policy_type="ai_autonomy",
        rules={"max_autonomy_level": "copilot", "auto_approve_confidence_above": 0.9},
        description="Платформенная политика автономности AI — режим copilot по умолчанию",
    )
    result["policies"].append({"name": p1.name, "id": p1.id, "created": created})
    logger.info("Policy '%s': %s", p1.name, "created" if created else "already exists")

    # 1b. Базовый доступ к инструментам
    p2, created = _get_or_create_policy(
        db,
        name="Базовый доступ к инструментам",
        level="platform",
        policy_type="tool_access",
        rules={
            "allowed_tools": ["document_parser", "risk_scorer", "clause_extractor", "rag_search"],
            "denied_tools": ["contract_generator"],
        },
        description="Платформенная политика доступа к инструментам — генератор контрактов запрещён по умолчанию",
    )
    result["policies"].append({"name": p2.name, "id": p2.id, "created": created})
    logger.info("Policy '%s': %s", p2.name, "created" if created else "already exists")

    # 1c. Действия, требующие одобрения
    p3, created = _get_or_create_policy(
        db,
        name="Действия, требующие одобрения",
        level="platform",
        policy_type="action_approval",
        rules={
            "approval_required_patterns": [
                "action.modify_clause",
                "action.create_comment",
                "tool.contract_generator.*",
            ],
        },
        description="Платформенная политика одобрения — критичные действия требуют human approval",
    )
    result["policies"].append({"name": p3.name, "id": p3.id, "created": created})
    logger.info("Policy '%s': %s", p3.name, "created" if created else "already exists")

    # ApprovalRule для contract_generator
    ar1, ar_created = _get_or_create_approval_rule(
        db,
        policy_id=p3.id,
        action_pattern="tool.contract_generator.*",
        required_approvers=1,
    )
    result["approval_rules"].append({
        "pattern": ar1.action_pattern,
        "id": ar1.id,
        "created": ar_created,
    })
    logger.info(
        "ApprovalRule '%s': %s", ar1.action_pattern, "created" if ar_created else "already exists"
    )

    # ── 2. Тестовая организация ──────────────────────────────────────────

    org = db.query(Organization).filter(Organization.slug == "test-law-firm").first()
    org_created = False
    if not org:
        org = Organization(
            name="Тестовая юрфирма",
            slug="test-law-firm",
            description="Тестовая организация для разработки и демонстрации",
        )
        db.add(org)
        db.flush()
        org_created = True

    result["organization"] = {"name": org.name, "slug": org.slug, "id": org.id, "created": org_created}
    logger.info("Organization '%s': %s", org.slug, "created" if org_created else "already exists")

    # ── 3. TenantContext ─────────────────────────────────────────────────

    tc = db.query(TenantContext).filter(TenantContext.org_id == org.id).first()
    tc_created = False
    if not tc:
        tc = TenantContext(org_id=org.id, mode="standalone")
        db.add(tc)
        db.flush()
        tc_created = True

    result["tenant_context"] = {"org_id": org.id, "mode": tc.mode, "id": tc.id, "created": tc_created}
    logger.info("TenantContext for '%s': %s", org.slug, "created" if tc_created else "already exists")

    # ── 4. Привязка пользователей ────────────────────────────────────────

    user_role_map = {
        "admin@contractai.ru": "org_admin",
        "vip@contractai.ru": "manager",
        "lawyer@contractai.ru": "member",
    }

    for email, functional_role in user_role_map.items():
        user = db.query(User).filter(User.email == email).first()
        if not user:
            logger.warning("User '%s' not found — skipping membership", email)
            result["memberships"].append({"email": email, "status": "user_not_found"})
            continue

        membership = (
            db.query(OrganizationMembership)
            .filter(
                OrganizationMembership.user_id == user.id,
                OrganizationMembership.org_id == org.id,
            )
            .first()
        )
        m_created = False
        if not membership:
            membership = OrganizationMembership(
                user_id=user.id,
                org_id=org.id,
                functional_role=functional_role,
            )
            db.add(membership)
            db.flush()
            m_created = True

        result["memberships"].append({
            "email": email,
            "functional_role": functional_role,
            "id": membership.id,
            "created": m_created,
        })
        logger.info(
            "Membership %s → %s (%s): %s",
            email, org.slug, functional_role, "created" if m_created else "already exists",
        )

    # ── 5. UserAgentPolicyProfile для admin ──────────────────────────────

    admin_user = db.query(User).filter(User.email == "admin@contractai.ru").first()
    if admin_user:
        profile = (
            db.query(UserAgentPolicyProfile)
            .filter(
                UserAgentPolicyProfile.user_id == admin_user.id,
                UserAgentPolicyProfile.org_id == org.id,
            )
            .first()
        )
        prof_created = False
        if not profile:
            profile = UserAgentPolicyProfile(
                user_id=admin_user.id,
                org_id=org.id,
                allowed_ai_modes=["advisor", "copilot", "processor"],
                allowed_actions=None,  # null = не ограничено (ALL)
            )
            db.add(profile)
            db.flush()
            prof_created = True

        result["agent_policy_profiles"].append({
            "user_email": "admin@contractai.ru",
            "id": profile.id,
            "created": prof_created,
        })
        logger.info(
            "AgentPolicyProfile for admin: %s", "created" if prof_created else "already exists"
        )
    else:
        logger.warning("admin@contractai.ru not found — skipping agent policy profile")
        result["agent_policy_profiles"].append({
            "user_email": "admin@contractai.ru",
            "status": "user_not_found",
        })

    # ── 6. Организационная policy — расширенный доступ ───────────────────

    p_org, p_org_created = _get_or_create_policy(
        db,
        name="Юрфирма — расширенный доступ",
        level="organization",
        scope_id=org.id,
        policy_type="tool_access",
        rules={
            "allowed_tools": [
                "document_parser",
                "risk_scorer",
                "clause_extractor",
                "rag_search",
                "contract_generator",
            ],
        },
        description="Организационная политика — разрешает contract_generator для тестовой юрфирмы",
    )
    result["policies"].append({
        "name": p_org.name,
        "id": p_org.id,
        "created": p_org_created,
    })
    logger.info("Policy '%s': %s", p_org.name, "created" if p_org_created else "already exists")

    # ── Commit ───────────────────────────────────────────────────────────

    db.commit()
    logger.info("Seed data committed successfully")

    return result


# ── CLI entrypoint ───────────────────────────────────────────────────────────

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    db = SessionLocal()
    try:
        data = seed_initial_data(db)
        print("\n=== Seed результат ===")
        for key, value in data.items():
            print(f"\n{key}:")
            if isinstance(value, list):
                for item in value:
                    print(f"  - {item}")
            else:
                print(f"  {value}")
        print("\nГотово!")
    except Exception as e:
        db.rollback()
        logger.error("Seed failed: %s", e)
        raise
    finally:
        db.close()
