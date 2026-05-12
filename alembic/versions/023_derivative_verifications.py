"""023: derivative_verifications — отчёты о сверке производный↔основной

Хранит результаты трёхэтапной сверки производного документа с основным:
- requisites: rule-based проверка реквизитов
- contradictions: LLM-анализ противоречий условий
- diff: сравнение текстов (DocumentDiffService)

Revision ID: 023_derivative_verifications
Revises: 022_contract_relations
Create Date: 2026-04-30
"""

from alembic import op
import sqlalchemy as sa


revision = "023_derivative_verifications"
down_revision = "022_contract_relations"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "derivative_verifications",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "relation_id",
            sa.String(36),
            sa.ForeignKey("contract_relations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "parent_contract_id",
            sa.String(36),
            sa.ForeignKey("contracts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "child_contract_id",
            sa.String(36),
            sa.ForeignKey("contracts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("overall_assessment", sa.String(20), nullable=False),
        sa.Column("requisites", sa.JSON, nullable=True),
        sa.Column("contradictions", sa.JSON, nullable=True),
        sa.Column("diff", sa.JSON, nullable=True),
        sa.Column("llm_model", sa.String(100), nullable=True),
        sa.Column("duration_ms", sa.Integer, nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="completed"),
        sa.Column("error", sa.Text, nullable=True),
        sa.Column(
            "created_by",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime,
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "overall_assessment IN ('ok', 'warnings', 'critical', 'error')",
            name="check_dv_overall_assessment",
        ),
        sa.CheckConstraint(
            "status IN ('completed', 'partial', 'failed', 'in_progress')",
            name="check_dv_status",
        ),
    )
    op.create_index(
        "ix_dv_relation", "derivative_verifications", ["relation_id"]
    )
    op.create_index(
        "ix_dv_child", "derivative_verifications", ["child_contract_id"]
    )
    op.create_index(
        "ix_dv_parent", "derivative_verifications", ["parent_contract_id"]
    )
    op.create_index(
        "ix_dv_created_at", "derivative_verifications", ["created_at"]
    )


def downgrade() -> None:
    op.drop_index("ix_dv_created_at", table_name="derivative_verifications")
    op.drop_index("ix_dv_parent", table_name="derivative_verifications")
    op.drop_index("ix_dv_child", table_name="derivative_verifications")
    op.drop_index("ix_dv_relation", table_name="derivative_verifications")
    op.drop_table("derivative_verifications")
