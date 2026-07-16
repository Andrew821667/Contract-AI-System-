"""024: personal demo access requests and enforceable demo usage

Revision ID: 024_demo_access_requests
Revises: 023_derivative_verifications
Create Date: 2026-07-16
"""

from alembic import op
import sqlalchemy as sa


revision = "024_demo_access_requests"
down_revision = "023_derivative_verifications"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("llm_requests_total", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "demo_tokens",
        sa.Column("recipient_email", sa.String(length=255), nullable=True),
    )
    op.create_index("ix_demo_tokens_recipient_email", "demo_tokens", ["recipient_email"])

    op.create_table(
        "demo_access_requests",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("contact", sa.String(length=255), nullable=False),
        sa.Column("company", sa.String(length=255), nullable=True),
        sa.Column("task", sa.Text(), nullable=False),
        sa.Column("source", sa.String(length=50), nullable=False, server_default="website"),
        sa.Column("consent_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("consent_version", sa.String(length=20), nullable=False, server_default="2026-07-16"),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("decision_note", sa.Text(), nullable=True),
        sa.Column("ip_address", sa.String(length=45), nullable=True),
        sa.Column("user_agent", sa.Text(), nullable=True),
        sa.Column(
            "demo_token_id",
            sa.String(length=36),
            sa.ForeignKey("demo_tokens.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "decided_by",
            sa.String(length=36),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("decided_at", sa.DateTime(), nullable=True),
        sa.CheckConstraint(
            "status IN ('pending', 'approved', 'rejected')",
            name="check_demo_access_request_status",
        ),
    )
    op.create_index("ix_demo_access_requests_email", "demo_access_requests", ["email"])
    op.create_index("ix_demo_access_requests_status", "demo_access_requests", ["status"])
    op.create_index("ix_demo_access_requests_demo_token_id", "demo_access_requests", ["demo_token_id"])
    op.create_index("ix_demo_access_requests_decided_by", "demo_access_requests", ["decided_by"])
    op.create_index("ix_demo_access_requests_created_at", "demo_access_requests", ["created_at"])
    op.create_index(
        "idx_demo_request_email_status",
        "demo_access_requests",
        ["email", "status"],
    )


def downgrade() -> None:
    op.drop_table("demo_access_requests")
    op.drop_index("ix_demo_tokens_recipient_email", table_name="demo_tokens")
    op.drop_column("demo_tokens", "recipient_email")
    op.drop_column("users", "llm_requests_total")
