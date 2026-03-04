"""
Contract Versions & Changes — Version comparison support

Creates tables for contract versioning and change tracking:
- contract_versions: file versions with hashing
- contract_changes: individual diff items between versions
- change_analysis_results: aggregated comparison statistics
- change_review_feedback: lawyer feedback on changes

Revision ID: 010
Revises: 009
Create Date: 2026-03-04
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = '010'
down_revision = '009'
branch_labels = None
depends_on = None


def upgrade():
    # --- contract_versions ---
    op.create_table(
        'contract_versions',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('contract_id', sa.String(36), sa.ForeignKey('contracts.id', ondelete='CASCADE'), nullable=False),
        sa.Column('version_number', sa.Integer(), nullable=False),
        sa.Column('file_path', sa.Text(), nullable=False),
        sa.Column('file_hash', sa.String(64), nullable=True),
        sa.Column('uploaded_by', sa.String(36), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('uploaded_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('source', sa.String(50), server_default='unknown'),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('parent_version_id', sa.Integer(), sa.ForeignKey('contract_versions.id'), nullable=True),
        sa.Column('is_current', sa.Boolean(), server_default='1'),
        sa.Column('version_metadata', sa.Text(), nullable=True),  # JSON stored as text for SQLite
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index('idx_cv_contract_id', 'contract_versions', ['contract_id'])
    op.create_index('idx_cv_is_current', 'contract_versions', ['is_current'])
    op.create_unique_constraint('uq_contract_version', 'contract_versions', ['contract_id', 'version_number'])

    # --- contract_changes ---
    op.create_table(
        'contract_changes',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('from_version_id', sa.Integer(), sa.ForeignKey('contract_versions.id', ondelete='CASCADE'), nullable=False),
        sa.Column('to_version_id', sa.Integer(), sa.ForeignKey('contract_versions.id', ondelete='CASCADE'), nullable=False),
        sa.Column('change_type', sa.String(50), nullable=False),
        sa.Column('change_category', sa.String(50), nullable=False),
        sa.Column('xpath_location', sa.Text(), nullable=True),
        sa.Column('section_name', sa.String(255), nullable=True),
        sa.Column('clause_number', sa.String(50), nullable=True),
        sa.Column('old_content', sa.Text(), nullable=True),
        sa.Column('new_content', sa.Text(), nullable=True),
        sa.Column('semantic_description', sa.Text(), nullable=True),
        sa.Column('is_substantive', sa.Boolean(), server_default='1'),
        sa.Column('legal_implications', sa.Text(), nullable=True),
        sa.Column('impact_assessment', sa.Text(), nullable=True),  # JSON
        sa.Column('related_disagreement_objection_id', sa.Integer(), nullable=True),
        sa.Column('objection_status', sa.String(20), nullable=True),
        sa.Column('requires_lawyer_review', sa.Boolean(), server_default='0'),
        sa.Column('reviewed_by', sa.String(36), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('reviewed_at', sa.DateTime(), nullable=True),
        sa.Column('lawyer_decision', sa.String(20), nullable=True),
        sa.Column('lawyer_comments', sa.Text(), nullable=True),
        sa.Column('detected_by', sa.String(50), server_default='ChangesAnalyzerAgent'),
        sa.Column('confidence_score', sa.Float(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index('idx_cc_from_version', 'contract_changes', ['from_version_id'])
    op.create_index('idx_cc_to_version', 'contract_changes', ['to_version_id'])
    op.create_index('idx_cc_change_type', 'contract_changes', ['change_type'])
    op.create_index('idx_cc_change_category', 'contract_changes', ['change_category'])
    op.create_index('idx_cc_requires_review', 'contract_changes', ['requires_lawyer_review'])

    # --- change_analysis_results ---
    op.create_table(
        'change_analysis_results',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('from_version_id', sa.Integer(), sa.ForeignKey('contract_versions.id', ondelete='CASCADE'), nullable=False),
        sa.Column('to_version_id', sa.Integer(), sa.ForeignKey('contract_versions.id', ondelete='CASCADE'), nullable=False),
        sa.Column('total_changes', sa.Integer(), server_default='0'),
        sa.Column('by_type', sa.Text(), nullable=True),  # JSON
        sa.Column('by_category', sa.Text(), nullable=True),  # JSON
        sa.Column('by_impact', sa.Text(), nullable=True),  # JSON
        sa.Column('overall_assessment', sa.String(20), nullable=True),
        sa.Column('overall_risk_change', sa.String(20), nullable=True),
        sa.Column('critical_changes', sa.Text(), nullable=True),  # JSON
        sa.Column('accepted_objections', sa.Integer(), server_default='0'),
        sa.Column('rejected_objections', sa.Integer(), server_default='0'),
        sa.Column('partial_objections', sa.Integer(), server_default='0'),
        sa.Column('recommendations', sa.Text(), nullable=True),
        sa.Column('executive_summary', sa.Text(), nullable=True),
        sa.Column('report_pdf_path', sa.Text(), nullable=True),
        sa.Column('report_generated_at', sa.DateTime(), nullable=True),
        sa.Column('analyzed_at', sa.DateTime(), server_default=sa.func.now()),
        sa.Column('analyzed_by', sa.String(50), server_default='ChangesAnalyzerAgent'),
        sa.Column('analysis_duration_ms', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index('idx_car_from_version', 'change_analysis_results', ['from_version_id'])
    op.create_index('idx_car_to_version', 'change_analysis_results', ['to_version_id'])
    op.create_index('idx_car_assessment', 'change_analysis_results', ['overall_assessment'])
    op.create_unique_constraint('uq_change_analysis', 'change_analysis_results', ['from_version_id', 'to_version_id'])

    # --- change_review_feedback ---
    op.create_table(
        'change_review_feedback',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('change_id', sa.Integer(), sa.ForeignKey('contract_changes.id', ondelete='CASCADE'), nullable=False),
        sa.Column('user_id', sa.String(36), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('decision', sa.String(20), nullable=False),
        sa.Column('reasoning', sa.Text(), nullable=True),
        sa.Column('analysis_accuracy', sa.Integer(), nullable=True),
        sa.Column('impact_assessment_quality', sa.Integer(), nullable=True),
        sa.Column('recommendation_usefulness', sa.Integer(), nullable=True),
        sa.Column('what_happened', sa.String(20), nullable=True),
        sa.Column('outcome_notes', sa.Text(), nullable=True),
        sa.Column('was_correct_recommendation', sa.Boolean(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
    )
    op.create_index('idx_crf_change_id', 'change_review_feedback', ['change_id'])
    op.create_index('idx_crf_user_id', 'change_review_feedback', ['user_id'])
    op.create_index('idx_crf_decision', 'change_review_feedback', ['decision'])


def downgrade():
    op.drop_table('change_review_feedback')
    op.drop_table('change_analysis_results')
    op.drop_table('contract_changes')
    op.drop_table('contract_versions')
