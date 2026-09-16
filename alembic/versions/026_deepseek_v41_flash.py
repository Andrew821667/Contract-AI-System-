"""026: persisted Flash routes follow DeepSeek V4.1 Flash (`deepseek-flash`)

Revision ID: 026_deepseek_v41_flash
Revises: 025_deepseek_v4_routing
Create Date: 2026-09-16

DeepSeek выпустил V4.1 Flash под именем `deepseek-flash`; старое
`deepseek-v4-flash` обслуживается той же моделью, но в настройках и
политиках должно стоять актуальное имя — иначе админка и отчёты о
стоимости показывают модель, которой больше нет.
"""

import json
from typing import Any

from alembic import op
import sqlalchemy as sa


revision = "026_deepseek_v41_flash"
down_revision = "025_deepseek_v4_routing"
branch_labels = None
depends_on = None


OLD_FLASH_NAMES = {"deepseek-v4-flash", "deepseek-v4-flash-vision-exp", "deepseek-v4.1-flash"}
NEW_FLASH = "deepseek-flash"

system_config = sa.table(
    "system_config",
    sa.column("config_key", sa.String()),
    sa.column("config_value", sa.JSON()),
    sa.column("updated_at", sa.DateTime()),
)

policies = sa.table(
    "policies",
    sa.column("id", sa.String()),
    sa.column("policy_type", sa.String()),
    sa.column("rules", sa.JSON()),
    sa.column("updated_at", sa.DateTime()),
)


def _as_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, str):
        value = json.loads(value)
    return dict(value or {})


def _rename(accepted: set[str], target: str) -> None:
    bind = op.get_bind()
    tables = set(sa.inspect(bind).get_table_names())

    if "system_config" in tables:
        row = bind.execute(
            sa.select(system_config.c.config_value).where(system_config.c.config_key == "router_config")
        ).mappings().first()
        if row:
            config = _as_dict(row["config_value"])
            if config.get("default_model") in accepted:
                config["default_model"] = target
                bind.execute(
                    sa.update(system_config)
                    .where(system_config.c.config_key == "router_config")
                    .values(config_value=config, updated_at=sa.func.now())
                )

    if "policies" in tables:
        rows = bind.execute(
            sa.select(policies.c.id, policies.c.rules).where(policies.c.policy_type == "llm_routing")
        ).mappings().all()
        for row in rows:
            rules = _as_dict(row["rules"])
            changed = False
            if rules.get("default_model") in accepted:
                rules["default_model"] = target
                changed = True
            allowed = rules.get("allowed_models")
            if isinstance(allowed, list) and any(model in accepted for model in allowed):
                deduped: list[str] = []
                for model in allowed:
                    replacement = target if model in accepted else model
                    if replacement not in deduped:
                        deduped.append(replacement)
                rules["allowed_models"] = deduped
                changed = True
            if changed:
                bind.execute(
                    sa.update(policies)
                    .where(policies.c.id == row["id"])
                    .values(rules=rules, updated_at=sa.func.now())
                )


def upgrade() -> None:
    _rename(OLD_FLASH_NAMES, NEW_FLASH)


def downgrade() -> None:
    _rename({NEW_FLASH}, "deepseek-v4-flash")
