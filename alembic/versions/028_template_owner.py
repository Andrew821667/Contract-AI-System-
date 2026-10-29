"""028: владелец приватного шаблона; существующие шаблоны остаются общими.

Revision ID: 028_template_owner
Revises: 027_graph_nodes_number_index
Create Date: 2026-10-29
"""

from alembic import op
import sqlalchemy as sa


revision = "028_template_owner"
down_revision = "027_graph_nodes_number_index"
branch_labels = None
depends_on = None


def upgrade() -> None:
    if op.get_bind().dialect.name == "sqlite":
        # Пересоздание templates через batch может удалить связанные версии
        # при включённых внешних ключах и ON DELETE CASCADE.
        op.execute(
            "ALTER TABLE templates ADD COLUMN owner_id VARCHAR(36) "
            "CONSTRAINT fk_templates_owner_id REFERENCES users (id) ON DELETE CASCADE"
        )
    else:
        op.add_column("templates", sa.Column("owner_id", sa.String(36), nullable=True))
        op.create_foreign_key(
            "fk_templates_owner_id", "templates", "users", ["owner_id"], ["id"],
            ondelete="CASCADE",
        )
    op.create_index("ix_templates_owner_id", "templates", ["owner_id"])

    # До исправления save-as-template копировал в общий шаблон и чужой договор.
    # Такие шаблоны из договоров не-админов становятся приватными у владельца
    # договора; сохранённые админом (образцы организации) остаются общими.
    source = (
        "json_extract(templates.meta_info, '$.source_contract_id')"
        if op.get_bind().dialect.name == "sqlite"
        else "(templates.meta_info ->> 'source_contract_id')"
    )
    op.execute(
        f"UPDATE templates SET owner_id = ("
        f"SELECT contracts.assigned_to FROM contracts JOIN users ON users.id = contracts.assigned_to "
        f"WHERE contracts.id = {source} AND users.role <> 'admin') "
        f"WHERE owner_id IS NULL AND {source} IS NOT NULL"
    )


def downgrade() -> None:
    op.drop_index("ix_templates_owner_id", table_name="templates")
    if op.get_bind().dialect.name != "sqlite":
        op.drop_constraint("fk_templates_owner_id", "templates", type_="foreignkey")
    op.drop_column("templates", "owner_id")
