"""020: добавить onboarding_completed в users

Revision ID: 020_user_onboarding_completed
Revises: 019_tenant_isolation_org_id
Create Date: 2026-04-17
"""
from alembic import op
import sqlalchemy as sa

revision = "020_user_onboarding_completed"
down_revision = "019_tenant_isolation_org_id"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("onboarding_completed", sa.Boolean(), server_default="0", nullable=False),
    )


def downgrade() -> None:
    op.drop_column("users", "onboarding_completed")
