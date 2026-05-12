"""021: counterparties — контрагенты как сущность БД

Создаёт таблицу counterparties для хранения юрлиц/физлиц/ИП —
внешних сторон договоров. Привязка к организации (тенант) и автору.
Кэш проверок ФНС/Федресурс хранится здесь, чтобы не дублировать в Contract.meta_info.

Revision ID: 021_counterparties
Revises: 020_user_onboarding_completed
Create Date: 2026-04-29
"""

from alembic import op
import sqlalchemy as sa


revision = "021_counterparties"
down_revision = "020_user_onboarding_completed"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "counterparties",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "organization_id",
            sa.String(36),
            sa.ForeignKey("organizations.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_by",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("type", sa.String(30), nullable=False, server_default="legal"),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("name", sa.String(500), nullable=False),
        sa.Column("short_name", sa.String(255), nullable=True),
        sa.Column("inn", sa.String(20), nullable=True),
        sa.Column("kpp", sa.String(20), nullable=True),
        sa.Column("ogrn", sa.String(20), nullable=True),
        sa.Column("legal_address", sa.Text, nullable=True),
        sa.Column("postal_address", sa.Text, nullable=True),
        sa.Column("contact_person", sa.String(255), nullable=True),
        sa.Column("contact_email", sa.String(255), nullable=True),
        sa.Column("contact_phone", sa.String(50), nullable=True),
        sa.Column("bank_details", sa.JSON, nullable=True),
        sa.Column("fns_data", sa.JSON, nullable=True),
        sa.Column("fns_checked_at", sa.DateTime, nullable=True),
        sa.Column("bankruptcy_data", sa.JSON, nullable=True),
        sa.Column("bankruptcy_checked_at", sa.DateTime, nullable=True),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("meta_info", sa.JSON, nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("organization_id", "inn", name="uq_counterparty_org_inn"),
        sa.CheckConstraint(
            "type IN ('legal', 'individual', 'individual_entrepreneur', 'foreign', 'other')",
            name="check_counterparty_type",
        ),
        sa.CheckConstraint(
            "status IN ('active', 'archived')",
            name="check_counterparty_status",
        ),
    )

    op.create_index("ix_counterparties_organization_id", "counterparties", ["organization_id"])
    op.create_index("ix_counterparties_created_by", "counterparties", ["created_by"])
    op.create_index("ix_counterparties_inn", "counterparties", ["inn"])
    op.create_index("ix_counterparties_ogrn", "counterparties", ["ogrn"])
    op.create_index("ix_counterparties_status", "counterparties", ["status"])
    op.create_index("ix_counterparties_created_at", "counterparties", ["created_at"])
    op.create_index(
        "idx_counterparty_org_status", "counterparties", ["organization_id", "status"]
    )
    op.create_index("idx_counterparty_name", "counterparties", ["name"])


def downgrade() -> None:
    op.drop_index("idx_counterparty_name", table_name="counterparties")
    op.drop_index("idx_counterparty_org_status", table_name="counterparties")
    op.drop_index("ix_counterparties_created_at", table_name="counterparties")
    op.drop_index("ix_counterparties_status", table_name="counterparties")
    op.drop_index("ix_counterparties_ogrn", table_name="counterparties")
    op.drop_index("ix_counterparties_inn", table_name="counterparties")
    op.drop_index("ix_counterparties_created_by", table_name="counterparties")
    op.drop_index("ix_counterparties_organization_id", table_name="counterparties")
    op.drop_table("counterparties")
