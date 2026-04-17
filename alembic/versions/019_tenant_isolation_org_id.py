"""019: tenant isolation — organization_id в contracts, negotiations, orchestrator_runs

Добавляет organization_id (nullable) в три таблицы для multi-tenancy.
Бэкфилл: для каждой записи берём первую активную запись из
organization_memberships соответствующего пользователя.

Нюансы:
- Колонка nullable=True чтобы миграция была безопасной для записей, чьи
  пользователи не имеют ни одной активной организации.
- verify_* helpers должны проверять: если org_id заполнен — требовать
  совпадения с OrganizationContext; если NULL (legacy) — fallback на user_id.
- Позже (после полного бэкфилла и пока все пути создания проставляют org_id)
  отдельной миграцией сделаем NOT NULL.

Revision ID: 019_tenant_isolation_org_id
Revises: 018_hash_access_tokens
Create Date: 2026-04-16
"""

from alembic import op
import sqlalchemy as sa


revision = "019_tenant_isolation_org_id"
down_revision = "018_hash_access_tokens"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── contracts.organization_id ────────────────────────────────────────────
    op.add_column(
        "contracts",
        sa.Column(
            "organization_id",
            sa.String(36),
            sa.ForeignKey("organizations.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_contracts_organization_id", "contracts", ["organization_id"]
    )

    # ── negotiations.organization_id ────────────────────────────────────────
    op.add_column(
        "negotiations",
        sa.Column(
            "organization_id",
            sa.String(36),
            sa.ForeignKey("organizations.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_negotiations_organization_id", "negotiations", ["organization_id"]
    )

    # ── orchestrator_runs.organization_id ───────────────────────────────────
    op.add_column(
        "orchestrator_runs",
        sa.Column(
            "organization_id",
            sa.String(36),
            sa.ForeignKey("organizations.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_orch_runs_organization_id", "orchestrator_runs", ["organization_id"]
    )

    # ── Backfill из organization_memberships (первая активная org юзера) ────
    # SQLite 3.33+ и PostgreSQL оба поддерживают коррелированный UPDATE.
    bind = op.get_bind()
    dialect = bind.dialect.name

    # Общий CTE-less корреляционный UPDATE совместим с Postgres и SQLite 3.33+
    op.execute(
        """
        UPDATE contracts
        SET organization_id = (
            SELECT om.org_id
            FROM organization_memberships om
            WHERE om.user_id = contracts.assigned_to
              AND om.active = 1
            ORDER BY om.joined_at ASC
            LIMIT 1
        )
        WHERE contracts.organization_id IS NULL
          AND contracts.assigned_to IS NOT NULL
        """
    )
    op.execute(
        """
        UPDATE negotiations
        SET organization_id = (
            SELECT om.org_id
            FROM organization_memberships om
            WHERE om.user_id = negotiations.user_id
              AND om.active = 1
            ORDER BY om.joined_at ASC
            LIMIT 1
        )
        WHERE negotiations.organization_id IS NULL
          AND negotiations.user_id IS NOT NULL
        """
    )
    op.execute(
        """
        UPDATE orchestrator_runs
        SET organization_id = (
            SELECT om.org_id
            FROM organization_memberships om
            WHERE om.user_id = orchestrator_runs.initiated_by
              AND om.active = 1
            ORDER BY om.joined_at ASC
            LIMIT 1
        )
        WHERE orchestrator_runs.organization_id IS NULL
          AND orchestrator_runs.initiated_by IS NOT NULL
        """
    )


def downgrade() -> None:
    op.drop_index("ix_orch_runs_organization_id", table_name="orchestrator_runs")
    op.drop_column("orchestrator_runs", "organization_id")

    op.drop_index("ix_negotiations_organization_id", table_name="negotiations")
    op.drop_column("negotiations", "organization_id")

    op.drop_index("ix_contracts_organization_id", table_name="contracts")
    op.drop_column("contracts", "organization_id")
