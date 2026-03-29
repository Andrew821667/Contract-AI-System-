"""Company conditions — стандартные условия компании

Новая таблица company_conditions для хранения пользовательских
стандартных условий, которые влияют на анализ договоров.

Revision ID: 016_company_conditions
Revises: 015_graph_rag_tables
Create Date: 2026-03-29 18:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '016_company_conditions'
down_revision = '015_graph_rag_tables'
branch_labels = None
depends_on = None


def upgrade():
    """Create company_conditions table."""
    op.create_table(
        'company_conditions',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('user_id', sa.String(36), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('category', sa.String(50), nullable=False, server_default='other'),
        sa.Column('title', sa.String(500), nullable=False),
        sa.Column('description', sa.Text, nullable=True),
        sa.Column('condition_text', sa.Text, nullable=False),
        sa.Column('priority', sa.Integer, nullable=False, server_default='1'),
        sa.Column('is_active', sa.Boolean, nullable=False, server_default=sa.text('true')),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index('idx_condition_user_id', 'company_conditions', ['user_id'])
    op.create_index('idx_condition_category', 'company_conditions', ['category'])
    op.create_index('idx_condition_active', 'company_conditions', ['is_active'])


def downgrade():
    """Drop company_conditions table."""
    op.drop_index('idx_condition_active', table_name='company_conditions')
    op.drop_index('idx_condition_category', table_name='company_conditions')
    op.drop_index('idx_condition_user_id', table_name='company_conditions')
    op.drop_table('company_conditions')
