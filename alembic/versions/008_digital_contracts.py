"""
Digital Contracts — Hash-chain & DAG verification

Creates digital_contracts table for cryptographic integrity tracking:
- SHA-256 content hashing
- HMAC-SHA256 server signatures
- Hash-chain (parent_id) and DAG (parent_ids) support
- Version tracking per contract

Revision ID: 008
Revises: 007
Create Date: 2026-03-03
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = '008'
down_revision = '007'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'digital_contracts',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('contract_id', sa.String(36), sa.ForeignKey('contracts.id', ondelete='CASCADE'), nullable=False),
        sa.Column('version', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('content_hash', sa.String(64), nullable=False),
        sa.Column('signature', sa.String(128), nullable=False),
        sa.Column('parent_id', sa.String(36), sa.ForeignKey('digital_contracts.id'), nullable=True),
        sa.Column('parent_ids', sa.Text(), nullable=True),
        sa.Column('status', sa.String(20), server_default='active'),
        sa.Column('metadata_json', sa.Text(), nullable=True),
        sa.Column('created_by', sa.String(36), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
    )

    # Indexes
    op.create_index('idx_digital_contract_id', 'digital_contracts', ['contract_id'])
    op.create_index('idx_digital_content_hash', 'digital_contracts', ['content_hash'])
    op.create_index('idx_digital_parent', 'digital_contracts', ['parent_id'])
    op.create_index('idx_digital_status', 'digital_contracts', ['contract_id', 'status'])

    # Unique constraint: one version number per contract
    op.create_unique_constraint('uq_digital_contract_version', 'digital_contracts', ['contract_id', 'version'])


def downgrade():
    op.drop_table('digital_contracts')
