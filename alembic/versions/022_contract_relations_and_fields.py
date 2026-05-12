"""022: contract relations, parties и расширение полей contracts

Изменения схемы:
- contracts: новые поля contract_number, contract_date, effective_from/to,
  total_amount, currency, parsed_text, primary_relation_type, parties_summary
- contracts.document_type CHECK расширен: добавлен 'derivative'
- contract_parties: m2m договор↔контрагент с ролью (counterparty/guarantor/...)
- contract_relations: связь parent↔child с типом
  (supplementary_agreement / specification / annex / act / addendum / termination / custom)
- derivative_generation_history: история промптов для регенерации custom-производных

Revision ID: 022_contract_relations
Revises: 021_counterparties
Create Date: 2026-04-29
"""

from alembic import op
import sqlalchemy as sa


revision = "022_contract_relations"
down_revision = "021_counterparties"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── 1. Расширяем contracts ─────────────────────────────────────────────
    op.add_column("contracts", sa.Column("contract_number", sa.String(100), nullable=True))
    op.add_column("contracts", sa.Column("contract_date", sa.DateTime, nullable=True))
    op.add_column("contracts", sa.Column("effective_from", sa.DateTime, nullable=True))
    op.add_column("contracts", sa.Column("effective_to", sa.DateTime, nullable=True))
    op.add_column("contracts", sa.Column("total_amount", sa.Numeric(18, 2), nullable=True))
    op.add_column("contracts", sa.Column("currency", sa.String(3), nullable=True))
    op.add_column("contracts", sa.Column("parsed_text", sa.Text, nullable=True))
    op.add_column(
        "contracts",
        sa.Column("primary_relation_type", sa.String(50), nullable=True),
    )
    op.add_column("contracts", sa.Column("parties_summary", sa.JSON, nullable=True))

    op.create_index(
        "ix_contracts_contract_number", "contracts", ["contract_number"]
    )
    op.create_index("ix_contracts_contract_date", "contracts", ["contract_date"])
    op.create_index(
        "ix_contracts_primary_relation_type",
        "contracts",
        ["primary_relation_type"],
    )

    # Расширяем CHECK для document_type — добавляем 'derivative'.
    # batch_alter_table даёт SQLite-совместимое recreate-table; PG drops/creates inline.
    with op.batch_alter_table("contracts") as batch_op:
        batch_op.drop_constraint("check_document_type", type_="check")
        batch_op.create_check_constraint(
            "check_document_type",
            "document_type IN ('contract', 'disagreement', 'tracked_changes', 'derivative')",
        )

    # ── 2. contract_parties: m2m договор↔контрагент ─────────────────────────
    op.create_table(
        "contract_parties",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "contract_id",
            sa.String(36),
            sa.ForeignKey("contracts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "counterparty_id",
            sa.String(36),
            sa.ForeignKey("counterparties.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("role", sa.String(30), nullable=False, server_default="counterparty"),
        sa.Column("sequence_number", sa.Integer, nullable=True),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column(
            "created_at", sa.DateTime, nullable=False, server_default=sa.func.now()
        ),
        sa.UniqueConstraint(
            "contract_id", "counterparty_id", "role", name="uq_contract_party_role"
        ),
        sa.CheckConstraint(
            "role IN ('counterparty', 'guarantor', 'third_party', 'other')",
            name="check_contract_party_role",
        ),
    )
    op.create_index(
        "ix_contract_parties_contract_id", "contract_parties", ["contract_id"]
    )
    op.create_index(
        "ix_contract_parties_counterparty_id",
        "contract_parties",
        ["counterparty_id"],
    )
    op.create_index("ix_contract_parties_role", "contract_parties", ["role"])

    # ── 3. contract_relations: parent ↔ child ──────────────────────────────
    op.create_table(
        "contract_relations",
        sa.Column("id", sa.String(36), primary_key=True),
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
        sa.Column("relation_type", sa.String(50), nullable=False),
        sa.Column("custom_label", sa.String(200), nullable=True),
        sa.Column("custom_prompt", sa.Text, nullable=True),
        sa.Column("derived_from_text", sa.Text, nullable=True),
        sa.Column("confidence", sa.Float, nullable=True),
        sa.Column("auto_detected", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column(
            "created_by",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_at", sa.DateTime, nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime, nullable=False, server_default=sa.func.now()
        ),
        sa.UniqueConstraint(
            "parent_contract_id",
            "child_contract_id",
            "relation_type",
            name="uq_contract_relation",
        ),
        sa.CheckConstraint(
            "relation_type IN ('supplementary_agreement', 'specification', 'annex', "
            "'act', 'addendum', 'termination', 'custom')",
            name="check_contract_relation_type",
        ),
        sa.CheckConstraint(
            "parent_contract_id != child_contract_id",
            name="check_no_self_reference",
        ),
        sa.CheckConstraint(
            "confidence IS NULL OR (confidence >= 0.0 AND confidence <= 1.0)",
            name="check_relation_confidence",
        ),
    )
    op.create_index(
        "ix_contract_relations_parent",
        "contract_relations",
        ["parent_contract_id"],
    )
    op.create_index(
        "ix_contract_relations_child",
        "contract_relations",
        ["child_contract_id"],
    )
    op.create_index(
        "ix_contract_relations_type",
        "contract_relations",
        ["relation_type"],
    )
    op.create_index(
        "idx_contract_relations_parent_type",
        "contract_relations",
        ["parent_contract_id", "relation_type"],
    )

    # ── 4. derivative_generation_history: история промптов ──────────────────
    op.create_table(
        "derivative_generation_history",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "relation_id",
            sa.String(36),
            sa.ForeignKey("contract_relations.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column(
            "parent_contract_id",
            sa.String(36),
            sa.ForeignKey("contracts.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column(
            "child_contract_id",
            sa.String(36),
            sa.ForeignKey("contracts.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("relation_type", sa.String(50), nullable=False),
        sa.Column("custom_label", sa.String(200), nullable=True),
        sa.Column("prompt", sa.Text, nullable=False),
        sa.Column("parent_snapshot", sa.JSON, nullable=True),
        sa.Column("llm_model", sa.String(100), nullable=True),
        sa.Column("llm_metadata", sa.JSON, nullable=True),
        sa.Column("status", sa.String(30), nullable=False, server_default="completed"),
        sa.Column("error", sa.Text, nullable=True),
        sa.Column(
            "created_by",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_at", sa.DateTime, nullable=False, server_default=sa.func.now()
        ),
        sa.CheckConstraint(
            "status IN ('completed', 'failed', 'in_progress')",
            name="check_gen_history_status",
        ),
    )
    op.create_index(
        "ix_derivative_gen_history_relation_id",
        "derivative_generation_history",
        ["relation_id"],
    )
    op.create_index(
        "ix_derivative_gen_history_parent",
        "derivative_generation_history",
        ["parent_contract_id"],
    )
    op.create_index(
        "ix_derivative_gen_history_child",
        "derivative_generation_history",
        ["child_contract_id"],
    )
    op.create_index(
        "ix_derivative_gen_history_created_at",
        "derivative_generation_history",
        ["created_at"],
    )


def downgrade() -> None:
    # Reverse order
    op.drop_index(
        "ix_derivative_gen_history_created_at", table_name="derivative_generation_history"
    )
    op.drop_index(
        "ix_derivative_gen_history_child", table_name="derivative_generation_history"
    )
    op.drop_index(
        "ix_derivative_gen_history_parent", table_name="derivative_generation_history"
    )
    op.drop_index(
        "ix_derivative_gen_history_relation_id", table_name="derivative_generation_history"
    )
    op.drop_table("derivative_generation_history")

    op.drop_index(
        "idx_contract_relations_parent_type", table_name="contract_relations"
    )
    op.drop_index("ix_contract_relations_type", table_name="contract_relations")
    op.drop_index("ix_contract_relations_child", table_name="contract_relations")
    op.drop_index("ix_contract_relations_parent", table_name="contract_relations")
    op.drop_table("contract_relations")

    op.drop_index("ix_contract_parties_role", table_name="contract_parties")
    op.drop_index(
        "ix_contract_parties_counterparty_id", table_name="contract_parties"
    )
    op.drop_index("ix_contract_parties_contract_id", table_name="contract_parties")
    op.drop_table("contract_parties")

    # Откатываем CHECK constraint для document_type — обратно к 3 значениям.
    with op.batch_alter_table("contracts") as batch_op:
        batch_op.drop_constraint("check_document_type", type_="check")
        batch_op.create_check_constraint(
            "check_document_type",
            "document_type IN ('contract', 'disagreement', 'tracked_changes')",
        )

    op.drop_index(
        "ix_contracts_primary_relation_type", table_name="contracts"
    )
    op.drop_index("ix_contracts_contract_date", table_name="contracts")
    op.drop_index("ix_contracts_contract_number", table_name="contracts")

    op.drop_column("contracts", "parties_summary")
    op.drop_column("contracts", "primary_relation_type")
    op.drop_column("contracts", "parsed_text")
    op.drop_column("contracts", "currency")
    op.drop_column("contracts", "total_amount")
    op.drop_column("contracts", "effective_to")
    op.drop_column("contracts", "effective_from")
    op.drop_column("contracts", "contract_date")
    op.drop_column("contracts", "contract_number")
