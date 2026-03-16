"""Add KB management fields to legal_documents

Revision ID: 011_legal_document_kb_fields
Revises: 010_contract_versions
Create Date: 2026-03-11 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '011_legal_document_kb_fields'
down_revision = '010_contract_versions'
branch_labels = None
depends_on = None


def upgrade():
    """Add file_hash, file_name, file_path, chunks_count, source to legal_documents"""

    op.add_column('legal_documents', sa.Column('file_hash', sa.String(64), nullable=True))
    op.add_column('legal_documents', sa.Column('file_name', sa.String(255), nullable=True))
    op.add_column('legal_documents', sa.Column('file_path', sa.String(512), nullable=True))
    op.add_column('legal_documents', sa.Column('chunks_count', sa.Integer, server_default='0', nullable=False))
    op.add_column('legal_documents', sa.Column('source', sa.String(50), server_default='manual', nullable=False))

    op.create_index('idx_legal_doc_file_hash', 'legal_documents', ['file_hash'])

    # Update status check constraint to allow new statuses
    op.drop_constraint('check_legal_doc_status', 'legal_documents', type_='check')
    op.create_check_constraint(
        'check_legal_doc_status',
        'legal_documents',
        "status IN ('active', 'inactive', 'pending', 'processing', 'error')"
    )

    print("✅ legal_documents KB fields added")


def downgrade():
    """Remove KB fields from legal_documents"""
    op.drop_constraint('check_legal_doc_status', 'legal_documents', type_='check')
    op.create_check_constraint(
        'check_legal_doc_status',
        'legal_documents',
        "status IN ('active', 'inactive')"
    )

    op.drop_index('idx_legal_doc_file_hash', 'legal_documents')
    op.drop_column('legal_documents', 'source')
    op.drop_column('legal_documents', 'chunks_count')
    op.drop_column('legal_documents', 'file_path')
    op.drop_column('legal_documents', 'file_name')
    op.drop_column('legal_documents', 'file_hash')
