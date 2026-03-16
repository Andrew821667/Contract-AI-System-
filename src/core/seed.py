# -*- coding: utf-8 -*-
"""
Seed Data — идемпотентная инициализация платформенных политик и тестовой организации (Phase 1).

Запуск:
    source venv/bin/activate && python -m src.core.seed
"""

from __future__ import annotations

import logging
import uuid

from sqlalchemy.orm import Session

from src.core.policies.models import Policy
from src.core.identity_org.models import Organization
from src.models.database import SessionLocal

logger = logging.getLogger(__name__)


def seed_initial_data(db: Session) -> None:
    """
    Создаёт начальные данные платформы (idempotent).

    Перед каждой вставкой проверяет наличие записи по name.
    """

    # ── 1. Platform-level policies ───────────────────────────────────────

    # 1a. AI-автономность (платформа)
    if not db.query(Policy).filter(Policy.name == "platform_default_ai_autonomy").first():
        db.add(Policy(
            id=str(uuid.uuid4()),
            name="platform_default_ai_autonomy",
            description="Платформенная политика автономности AI по умолчанию",
            policy_type="ai_autonomy",
            level="platform",
            rules={
                "default_autonomy": "suggest_and_wait",
                "max_autonomy": "auto_with_review",
            },
            active=True,
            priority=0,
        ))
        logger.info("Created policy: platform_default_ai_autonomy")
    else:
        logger.info("Policy already exists: platform_default_ai_autonomy")

    # 1b. Пороги рисков (платформа)
    if not db.query(Policy).filter(Policy.name == "platform_risk_thresholds").first():
        db.add(Policy(
            id=str(uuid.uuid4()),
            name="platform_risk_thresholds",
            description="Платформенная политика порогов риска",
            policy_type="risk_threshold",
            level="platform",
            rules={
                "high_risk_requires_approval": True,
                "critical_risk_blocked": True,
            },
            active=True,
            priority=0,
        ))
        logger.info("Created policy: platform_risk_thresholds")
    else:
        logger.info("Policy already exists: platform_risk_thresholds")

    # 1c. Требования аудита (платформа)
    if not db.query(Policy).filter(Policy.name == "platform_audit_requirements").first():
        db.add(Policy(
            id=str(uuid.uuid4()),
            name="platform_audit_requirements",
            description="Платформенная политика аудита",
            policy_type="audit",
            level="platform",
            rules={
                "log_all_ai_actions": True,
                "log_tool_invocations": True,
            },
            active=True,
            priority=0,
        ))
        logger.info("Created policy: platform_audit_requirements")
    else:
        logger.info("Policy already exists: platform_audit_requirements")

    # ── 2. Тестовая организация ──────────────────────────────────────────

    org = db.query(Organization).filter(Organization.name == "Тестовая юрфирма").first()
    if not org:
        org = Organization(
            id=str(uuid.uuid4()),
            name="Тестовая юрфирма",
            slug="test-law-firm",
            settings={"industry": "legal", "locale": "ru"},
            active=True,
        )
        db.add(org)
        db.flush()  # flush чтобы получить org.id для следующей политики
        logger.info("Created organization: Тестовая юрфирма (slug=test-law-firm)")
    else:
        logger.info("Organization already exists: Тестовая юрфирма")

    # ── 3. Org-level policy override ─────────────────────────────────────

    if not db.query(Policy).filter(Policy.name == "org_autonomy_override").first():
        db.add(Policy(
            id=str(uuid.uuid4()),
            name="org_autonomy_override",
            description="Переопределение автономности AI для тестовой юрфирмы",
            policy_type="ai_autonomy",
            level="organization",
            scope_id=org.id,
            rules={
                "default_autonomy": "auto_with_review",
            },
            active=True,
            priority=0,
        ))
        logger.info("Created policy: org_autonomy_override (org_id=%s)", org.id)
    else:
        logger.info("Policy already exists: org_autonomy_override")

    # ── Commit ───────────────────────────────────────────────────────────

    db.commit()
    logger.info("Seed data committed successfully")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    db = SessionLocal()
    try:
        seed_initial_data(db)
        print("Готово!")
    except Exception as e:
        db.rollback()
        logger.error("Seed failed: %s", e)
        raise
    finally:
        db.close()
