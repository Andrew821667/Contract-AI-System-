"""M9: ReviewTask.history Text -> JSON column

Изменяет тип колонки history в review_tasks с Text на JSON.
Backward-compatible: существующие текстовые данные (JSON-строки)
автоматически совместимы с JSON-колонкой.

Для SQLite: пересоздаём колонку через batch_alter_table.
Для PostgreSQL: ALTER COLUMN TYPE с USING для конвертации.

Revision ID: 014_history_text_to_json
Revises: 013_indexes_risks_recs
Create Date: 2026-03-18 12:01:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '014_history_text_to_json'
down_revision = '013_indexes_risks_recs'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Use batch mode for SQLite compatibility
    # For PostgreSQL, this generates ALTER COLUMN TYPE
    # Existing text data containing JSON strings is preserved —
    # PostgreSQL will cast text->json via USING, SQLite stores JSON as text anyway
    with op.batch_alter_table('review_tasks', schema=None) as batch_op:
        batch_op.alter_column(
            'history',
            existing_type=sa.Text(),
            type_=sa.JSON(),
            existing_nullable=True,
            postgresql_using='history::json',
        )


def downgrade() -> None:
    with op.batch_alter_table('review_tasks', schema=None) as batch_op:
        batch_op.alter_column(
            'history',
            existing_type=sa.JSON(),
            type_=sa.Text(),
            existing_nullable=True,
            postgresql_using='history::text',
        )
