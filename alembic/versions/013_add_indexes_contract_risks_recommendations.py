"""M8: Add indexes on ContractRisk and ContractRecommendation for efficient search

Добавляет индексы на contract_risks.risk_type, contract_risks.severity
и contract_recommendations.priority для эффективного поиска.
JSON-поля в AnalysisResult НЕ удаляются (backward compatibility).

Revision ID: 013_indexes_risks_recs
Revises: 012_core_ai_collaborative
Create Date: 2026-03-18 12:00:00.000000

"""
from alembic import op

# revision identifiers, used by Alembic.
revision = '013_indexes_risks_recs'
down_revision = '012_core_ai_collaborative'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add indexes on ContractRisk columns for efficient filtering/search
    op.create_index(
        'ix_contract_risks_risk_type',
        'contract_risks',
        ['risk_type'],
        unique=False,
        if_not_exists=True,
    )
    op.create_index(
        'ix_contract_risks_severity',
        'contract_risks',
        ['severity'],
        unique=False,
        if_not_exists=True,
    )

    # Composite index for common query pattern: filter by type + severity
    op.create_index(
        'ix_contract_risks_type_severity',
        'contract_risks',
        ['risk_type', 'severity'],
        unique=False,
        if_not_exists=True,
    )

    # Add index on ContractRecommendation.priority
    op.create_index(
        'ix_contract_recommendations_priority',
        'contract_recommendations',
        ['priority'],
        unique=False,
        if_not_exists=True,
    )


def downgrade() -> None:
    op.drop_index('ix_contract_recommendations_priority', table_name='contract_recommendations')
    op.drop_index('ix_contract_risks_type_severity', table_name='contract_risks')
    op.drop_index('ix_contract_risks_severity', table_name='contract_risks')
    op.drop_index('ix_contract_risks_risk_type', table_name='contract_risks')
