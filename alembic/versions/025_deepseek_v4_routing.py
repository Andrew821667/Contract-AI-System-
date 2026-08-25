"""025: migrate the persisted default route to DeepSeek V4 Flash

Revision ID: 025_deepseek_v4_routing
Revises: 024_demo_access_requests
Create Date: 2026-08-25
"""

from alembic import op


revision = "025_deepseek_v4_routing"
down_revision = "024_demo_access_requests"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE system_config
        SET config_value = jsonb_set(
                config_value,
                '{default_model}',
                '"deepseek-v4-flash"'::jsonb,
                true
            ),
            updated_at = NOW()
        WHERE config_key = 'router_config'
          AND COALESCE(config_value->>'default_model', '') IN (
              'deepseek',
              'deepseek-chat',
              'deepseek-v3',
              'deepseek-v3.2',
              'deepseek-reasoner',
              'deepseek-v4-flash',
              'deepseek-v4-pro'
          )
        """
    )
    op.execute(
        """
        UPDATE policies
        SET rules = jsonb_set(
                rules::jsonb,
                '{default_model}',
                '"deepseek-v4-flash"'::jsonb,
                true
            )::json,
            updated_at = NOW()
        WHERE policy_type = 'llm_routing'
          AND COALESCE(rules->>'default_model', '') IN (
              'deepseek',
              'deepseek-chat',
              'deepseek-v3',
              'deepseek-v3.2',
              'deepseek-reasoner',
              'deepseek-v4-flash',
              'deepseek-v4-pro'
          )
        """
    )
    op.execute(
        """
        UPDATE policies
        SET rules = jsonb_set(
                rules::jsonb,
                '{high_sensitivity_model}',
                '"deepseek-v4-pro"'::jsonb,
                true
            )::json,
            updated_at = NOW()
        WHERE policy_type = 'llm_routing'
          AND COALESCE(rules->>'high_sensitivity_model', '') IN (
              'deepseek',
              'deepseek-chat',
              'deepseek-v3',
              'deepseek-v3.2',
              'deepseek-reasoner',
              'deepseek-v4-flash',
              'deepseek-v4-pro'
          )
        """
    )


def downgrade() -> None:
    op.execute(
        """
        UPDATE policies
        SET rules = jsonb_set(
                rules::jsonb,
                '{high_sensitivity_model}',
                '"deepseek-reasoner"'::jsonb,
                true
            )::json,
            updated_at = NOW()
        WHERE policy_type = 'llm_routing'
          AND rules->>'high_sensitivity_model' = 'deepseek-v4-pro'
        """
    )
    op.execute(
        """
        UPDATE policies
        SET rules = jsonb_set(
                rules::jsonb,
                '{default_model}',
                '"deepseek-v3"'::jsonb,
                true
            )::json,
            updated_at = NOW()
        WHERE policy_type = 'llm_routing'
          AND rules->>'default_model' = 'deepseek-v4-flash'
        """
    )
    op.execute(
        """
        UPDATE system_config
        SET config_value = jsonb_set(
                config_value,
                '{default_model}',
                '"deepseek-v3"'::jsonb,
                true
            ),
            updated_at = NOW()
        WHERE config_key = 'router_config'
          AND config_value->>'default_model' = 'deepseek-v4-flash'
        """
    )
