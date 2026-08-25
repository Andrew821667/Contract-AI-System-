"""025: migrate persisted routes to DeepSeek V4 Flash and Pro

Revision ID: 025_deepseek_v4_routing
Revises: 024_demo_access_requests
Create Date: 2026-08-25
"""

import json
from typing import Any

from alembic import op
import sqlalchemy as sa


revision = "025_deepseek_v4_routing"
down_revision = "024_demo_access_requests"
branch_labels = None
depends_on = None


DEEPSEEK_MODELS = {
    "deepseek",
    "deepseek-chat",
    "deepseek-v3",
    "deepseek-v3.2",
    "deepseek-reasoner",
    "deepseek-v4-flash",
    "deepseek-v4-pro",
}


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


def _update_system_default(target: str, accepted: set[str]) -> None:
    bind = op.get_bind()
    if "system_config" not in sa.inspect(bind).get_table_names():
        return

    row = bind.execute(
        sa.select(system_config.c.config_value).where(
            system_config.c.config_key == "router_config"
        )
    ).mappings().first()
    if not row:
        return

    config = _as_dict(row["config_value"])
    if config.get("default_model") not in accepted:
        return

    config["default_model"] = target
    bind.execute(
        sa.update(system_config)
        .where(system_config.c.config_key == "router_config")
        .values(config_value=config, updated_at=sa.func.now())
    )


def _update_policy_models(
    default_target: str,
    high_target: str,
    accepted_defaults: set[str],
    accepted_high: set[str],
) -> None:
    bind = op.get_bind()
    if "policies" not in sa.inspect(bind).get_table_names():
        return

    rows = bind.execute(
        sa.select(policies.c.id, policies.c.rules).where(
            policies.c.policy_type == "llm_routing"
        )
    ).mappings().all()

    for row in rows:
        rules = _as_dict(row["rules"])
        changed = False
        if rules.get("default_model") in accepted_defaults:
            rules["default_model"] = default_target
            changed = True
        if rules.get("high_sensitivity_model") in accepted_high:
            rules["high_sensitivity_model"] = high_target
            changed = True
        if changed:
            bind.execute(
                sa.update(policies)
                .where(policies.c.id == row["id"])
                .values(rules=rules, updated_at=sa.func.now())
            )


def upgrade() -> None:
    _update_system_default("deepseek-v4-flash", DEEPSEEK_MODELS)
    _update_policy_models(
        default_target="deepseek-v4-flash",
        high_target="deepseek-v4-pro",
        accepted_defaults=DEEPSEEK_MODELS,
        accepted_high=DEEPSEEK_MODELS,
    )


def downgrade() -> None:
    _update_system_default("deepseek-v3", {"deepseek-v4-flash"})
    _update_policy_models(
        default_target="deepseek-v3",
        high_target="deepseek-reasoner",
        accepted_defaults={"deepseek-v4-flash"},
        accepted_high={"deepseek-v4-pro"},
    )
