"""
Clause Library — Extracted clauses storage

Creates extracted_clauses table for persisting clause analysis results:
- Clause text, type, and location
- LLM analysis JSON
- Risk level and severity scoring
- Tags for categorization

Revision ID: 009
Revises: 008
Create Date: 2026-03-04
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = '009'
down_revision = '008'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'extracted_clauses',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('contract_id', sa.String(36), sa.ForeignKey('contracts.id', ondelete='CASCADE'), nullable=False),
        sa.Column('clause_number', sa.Integer(), nullable=False),
        sa.Column('clause_type', sa.String(50), nullable=False),
        sa.Column('title', sa.String(500), nullable=False),
        sa.Column('text', sa.Text(), nullable=False),
        sa.Column('xpath_location', sa.Text(), nullable=True),
        sa.Column('analysis_json', sa.Text(), nullable=True),
        sa.Column('risk_level', sa.String(20), nullable=True),
        sa.Column('severity_score', sa.Float(), nullable=True),
        sa.Column('tags', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
    )

    # Indexes
    op.create_index('idx_clause_contract_id', 'extracted_clauses', ['contract_id'])
    op.create_index('idx_clause_type', 'extracted_clauses', ['clause_type'])
    op.create_index('idx_clause_risk_level', 'extracted_clauses', ['risk_level'])

    # Unique constraint: one clause number per contract
    op.create_unique_constraint('uq_clause_contract_number', 'extracted_clauses', ['contract_id', 'clause_number'])


def downgrade():
    op.drop_table('extracted_clauses')
