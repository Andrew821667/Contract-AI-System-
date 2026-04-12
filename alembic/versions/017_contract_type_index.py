"""Add index on contracts.contract_type for faster filtered queries

Revision ID: 017_contract_type_index
Revises: 016_company_conditions
Create Date: 2026-04-11 12:00:00.000000

"""
from alembic import op

# revision identifiers, used by Alembic.
revision = '017_contract_type_index'
down_revision = '016_company_conditions'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        'ix_contracts_contract_type',
        'contracts',
        ['contract_type'],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index('ix_contracts_contract_type', table_name='contracts')
