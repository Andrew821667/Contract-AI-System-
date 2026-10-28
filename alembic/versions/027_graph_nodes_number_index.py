"""027: индекс номера узла для поиска статьи по всей базе НПА.

Revision ID: 027_graph_nodes_number_index
Revises: 026_deepseek_v41_flash
Create Date: 2026-10-27

Ретривер ищет узел по номеру статьи по всей базе (graph_retriever.
_find_by_number: number=? AND is_archived=0 [AND layer IN ('npa')]). Индекса
по number не было: на проде (374 тыс. узлов с текстами) «ст. 506 по всем
НПА» шла индексом слоя и при холодном кэше занимала 18,7 с.

Создание индекса читает всю таблицу и держит блокировку записи SQLite —
при деплое это минуты. Если индекс уже есть (база из create_all) — пропуск.
"""

from alembic import op
import sqlalchemy as sa


revision = "027_graph_nodes_number_index"
down_revision = "026_deepseek_v41_flash"
branch_labels = None
depends_on = None


def upgrade() -> None:
    indexes = sa.inspect(op.get_bind()).get_indexes("graph_nodes")
    if not any(idx["name"] == "ix_graph_nodes_number" for idx in indexes):
        op.create_index("ix_graph_nodes_number", "graph_nodes", ["number"])


def downgrade() -> None:
    op.drop_index("ix_graph_nodes_number", table_name="graph_nodes")
