"""Graph-RAG tables — графовая модель документов

Создание таблиц для структурного представления договоров и НПА:
- graph_documents — документы-источники
- graph_nodes — узлы (пункты, статьи, таблицы, ...)
- node_versions — история изменений узлов
- graph_edges — связи между узлами (verified)
- candidate_edges — кандидаты на связи (от LLM, требуют ревью)
- graph_entities — нормализованные сущности (ссылки на НПА, суммы, даты)
- rag_audit_log — аудит всех изменений графа

Backward-compatible: только CREATE TABLE, без ALTER на существующие таблицы.

Revision ID: 015_graph_rag_tables
Revises: 014_history_text_to_json
Create Date: 2026-03-27 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '015_graph_rag_tables'
down_revision = '014_history_text_to_json'
branch_labels = None
depends_on = None


def upgrade():
    """Create Graph-RAG tables."""

    # ═══════════════════════════════════════════════════
    # 1. graph_documents — документы-источники
    # ═══════════════════════════════════════════════════

    op.create_table(
        'graph_documents',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('contract_id', sa.String(36),
                  sa.ForeignKey('contracts.id', ondelete='SET NULL'), nullable=True),
        sa.Column('legal_document_id', sa.String(36),
                  sa.ForeignKey('legal_documents.id', ondelete='SET NULL'), nullable=True),
        sa.Column('layer', sa.String(20), nullable=False),
        sa.Column('title', sa.Text, nullable=False),
        sa.Column('document_date', sa.DateTime, nullable=True),
        sa.Column('edition_date', sa.DateTime, nullable=True),
        sa.Column('document_type', sa.String(50), nullable=True),
        sa.Column('source_file', sa.Text, nullable=True),
        sa.Column('source_format', sa.String(20), nullable=True),
        sa.Column('parse_status', sa.String(20), nullable=False, server_default='fully_parsed'),
        sa.Column('parse_errors', sa.JSON, nullable=True),
        sa.Column('status', sa.String(20), nullable=False, server_default='active'),
        sa.Column('nodes_count', sa.Integer, server_default='0'),
        sa.Column('edges_count', sa.Integer, server_default='0'),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, server_default=sa.func.now()),
        sa.CheckConstraint(
            "layer IN ('contract', 'npa', 'court', 'internal')",
            name='check_graph_doc_layer'
        ),
        sa.CheckConstraint(
            "parse_status IN ('fully_parsed', 'partial_parse', 'needs_review', 'failed')",
            name='check_graph_doc_parse_status'
        ),
        sa.CheckConstraint(
            "status IN ('active', 'archived', 'superseded')",
            name='check_graph_doc_status'
        ),
    )
    op.create_index('ix_graph_documents_layer', 'graph_documents', ['layer'])
    op.create_index('ix_graph_documents_contract_id', 'graph_documents', ['contract_id'])
    op.create_index('ix_graph_documents_legal_document_id', 'graph_documents', ['legal_document_id'])
    op.create_index('ix_graph_documents_status', 'graph_documents', ['status'])
    op.create_index('ix_graph_documents_parse_status', 'graph_documents', ['parse_status'])
    op.create_index('ix_graph_documents_created_at', 'graph_documents', ['created_at'])

    # ═══════════════════════════════════════════════════
    # 2. graph_nodes — узлы графа
    # ═══════════════════════════════════════════════════

    op.create_table(
        'graph_nodes',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('document_id', sa.String(36),
                  sa.ForeignKey('graph_documents.id', ondelete='CASCADE'), nullable=False),
        sa.Column('layer', sa.String(20), nullable=False),
        sa.Column('node_type', sa.String(30), nullable=False),
        sa.Column('title', sa.Text, nullable=True),
        sa.Column('number', sa.String(50), nullable=True),
        sa.Column('text', sa.Text, nullable=False),
        sa.Column('parent_id', sa.String(36),
                  sa.ForeignKey('graph_nodes.id', ondelete='CASCADE'), nullable=True),
        sa.Column('level', sa.Integer, nullable=False, server_default='0'),
        sa.Column('position', sa.Integer, nullable=False, server_default='0'),
        sa.Column('meta_info', sa.JSON, nullable=True),
        sa.Column('is_archived', sa.Boolean, server_default='0'),
        sa.Column('archived_at', sa.DateTime, nullable=True),
        sa.Column('archived_reason', sa.Text, nullable=True),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, server_default=sa.func.now()),
        sa.CheckConstraint(
            "layer IN ('contract', 'npa', 'court', 'internal')",
            name='check_graph_node_layer'
        ),
        sa.CheckConstraint(
            "node_type IN ('document', 'section', 'clause', 'subclause', 'paragraph', "
            "'table', 'table_row', 'list_item', 'appendix', 'term', 'header', "
            "'preamble', 'signature_block', 'article', 'part', 'chapter', 'title', 'note')",
            name='check_graph_node_type'
        ),
    )
    op.create_index('ix_graph_nodes_document_id', 'graph_nodes', ['document_id'])
    op.create_index('ix_graph_nodes_layer', 'graph_nodes', ['layer'])
    op.create_index('ix_graph_nodes_node_type', 'graph_nodes', ['node_type'])
    op.create_index('ix_graph_nodes_parent_id', 'graph_nodes', ['parent_id'])
    op.create_index('ix_graph_nodes_is_archived', 'graph_nodes', ['is_archived'])
    op.create_index('ix_graph_nodes_created_at', 'graph_nodes', ['created_at'])
    op.create_index('ix_graph_nodes_parent_position', 'graph_nodes', ['parent_id', 'position'])
    op.create_index('ix_graph_nodes_doc_level', 'graph_nodes', ['document_id', 'level'])

    # ═══════════════════════════════════════════════════
    # 3. node_versions — версии узлов
    # ═══════════════════════════════════════════════════

    op.create_table(
        'node_versions',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('node_id', sa.String(36),
                  sa.ForeignKey('graph_nodes.id', ondelete='CASCADE'), nullable=False),
        sa.Column('version_number', sa.Integer, nullable=False),
        sa.Column('text', sa.Text, nullable=False),
        sa.Column('meta_info', sa.JSON, nullable=True),
        sa.Column('valid_from', sa.DateTime, nullable=True),
        sa.Column('valid_to', sa.DateTime, nullable=True),
        sa.Column('change_reason', sa.Text, nullable=True),
        sa.Column('changed_by', sa.String(20), nullable=False),
        sa.Column('change_type', sa.String(20), nullable=False),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        sa.CheckConstraint(
            "changed_by IN ('user', 'agent', 'system')",
            name='check_version_changed_by'
        ),
        sa.CheckConstraint(
            "change_type IN ('new', 'correction', 'new_edition', 'archive')",
            name='check_version_change_type'
        ),
    )
    op.create_index('ix_node_versions_node_id', 'node_versions', ['node_id'])
    op.create_index('ix_node_versions_created_at', 'node_versions', ['created_at'])
    op.create_index('ix_node_versions_node_version', 'node_versions',
                    ['node_id', 'version_number'], unique=True)

    # ═══════════════════════════════════════════════════
    # 4. graph_edges — связи (verified)
    # ═══════════════════════════════════════════════════

    op.create_table(
        'graph_edges',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('source_id', sa.String(36),
                  sa.ForeignKey('graph_nodes.id', ondelete='CASCADE'), nullable=False),
        sa.Column('target_id', sa.String(36),
                  sa.ForeignKey('graph_nodes.id', ondelete='CASCADE'), nullable=False),
        sa.Column('edge_type', sa.String(50), nullable=False),
        sa.Column('edge_class', sa.String(20), nullable=False),
        sa.Column('status', sa.String(25), nullable=False, server_default='verified'),
        sa.Column('evidence', sa.Text, nullable=True),
        sa.Column('rationale', sa.Text, nullable=True),
        sa.Column('confidence', sa.Float, server_default='1.0'),
        sa.Column('extracted_by', sa.String(20), nullable=False),
        sa.Column('valid_from', sa.DateTime, nullable=True),
        sa.Column('valid_to', sa.DateTime, nullable=True),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, server_default=sa.func.now()),
        sa.CheckConstraint(
            "edge_class IN ('structural', 'fact', 'analytical', 'risk_signal')",
            name='check_edge_class'
        ),
        sa.CheckConstraint(
            "status IN ('verified', 'machine_extracted', 'hypothesis', 'deprecated')",
            name='check_edge_status'
        ),
        sa.CheckConstraint(
            "extracted_by IN ('parser', 'rule', 'llm', 'manual')",
            name='check_edge_extracted_by'
        ),
        sa.CheckConstraint(
            'confidence >= 0.0 AND confidence <= 1.0',
            name='check_edge_confidence'
        ),
    )
    op.create_index('ix_graph_edges_source_id', 'graph_edges', ['source_id'])
    op.create_index('ix_graph_edges_target_id', 'graph_edges', ['target_id'])
    op.create_index('ix_graph_edges_edge_type', 'graph_edges', ['edge_type'])
    op.create_index('ix_graph_edges_edge_class', 'graph_edges', ['edge_class'])
    op.create_index('ix_graph_edges_status', 'graph_edges', ['status'])
    op.create_index('ix_graph_edges_created_at', 'graph_edges', ['created_at'])
    op.create_index('ix_graph_edges_source_type', 'graph_edges', ['source_id', 'edge_type'])
    op.create_index('ix_graph_edges_target_type', 'graph_edges', ['target_id', 'edge_type'])

    # ═══════════════════════════════════════════════════
    # 5. candidate_edges — кандидаты (отдельно от verified!)
    # ═══════════════════════════════════════════════════

    op.create_table(
        'candidate_edges',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('source_id', sa.String(36),
                  sa.ForeignKey('graph_nodes.id', ondelete='CASCADE'), nullable=False),
        sa.Column('target_id', sa.String(36),
                  sa.ForeignKey('graph_nodes.id', ondelete='CASCADE'), nullable=False),
        sa.Column('proposed_type', sa.String(50), nullable=False),
        sa.Column('proposed_class', sa.String(20), nullable=False),
        sa.Column('rationale', sa.Text, nullable=False),
        sa.Column('evidence', sa.Text, nullable=True),
        sa.Column('confidence', sa.Float, server_default='0.5'),
        sa.Column('requires_review', sa.Boolean, server_default='1'),
        sa.Column('reviewed', sa.Boolean, server_default='0'),
        sa.Column('review_result', sa.String(20), nullable=True),
        sa.Column('reviewed_by', sa.String(36),
                  sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('review_comment', sa.Text, nullable=True),
        sa.Column('accepted_edge_id', sa.String(36),
                  sa.ForeignKey('graph_edges.id', ondelete='SET NULL'), nullable=True),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        sa.Column('reviewed_at', sa.DateTime, nullable=True),
        sa.CheckConstraint(
            "proposed_class IN ('analytical', 'risk_signal')",
            name='check_candidate_proposed_class'
        ),
        sa.CheckConstraint(
            "review_result IN ('accepted', 'rejected', 'modified') OR review_result IS NULL",
            name='check_candidate_review_result'
        ),
        sa.CheckConstraint(
            'confidence >= 0.0 AND confidence <= 1.0',
            name='check_candidate_confidence'
        ),
    )
    op.create_index('ix_candidate_edges_source_id', 'candidate_edges', ['source_id'])
    op.create_index('ix_candidate_edges_target_id', 'candidate_edges', ['target_id'])
    op.create_index('ix_candidate_edges_reviewed', 'candidate_edges', ['reviewed'])
    op.create_index('ix_candidate_edges_created_at', 'candidate_edges', ['created_at'])
    op.create_index('ix_candidate_edges_pending', 'candidate_edges', ['reviewed', 'requires_review'])

    # ═══════════════════════════════════════════════════
    # 6. graph_entities — нормализованные сущности
    # ═══════════════════════════════════════════════════

    op.create_table(
        'graph_entities',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('node_id', sa.String(36),
                  sa.ForeignKey('graph_nodes.id', ondelete='CASCADE'), nullable=False),
        sa.Column('entity_type', sa.String(30), nullable=False),
        sa.Column('entity_value', sa.Text, nullable=False),
        sa.Column('raw_text', sa.Text, nullable=False),
        sa.Column('norm_code', sa.String(100), nullable=True),
        sa.Column('norm_article', sa.String(50), nullable=True),
        sa.Column('norm_part', sa.String(50), nullable=True),
        sa.Column('amount', sa.Float, nullable=True),
        sa.Column('currency', sa.String(10), nullable=True),
        sa.Column('date_value', sa.DateTime, nullable=True),
        sa.Column('date_type', sa.String(20), nullable=True),
        sa.Column('extracted_by', sa.String(20), nullable=False, server_default='parser'),
        sa.Column('confidence', sa.Float, server_default='1.0'),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        sa.CheckConstraint(
            "entity_type IN ('norm_ref', 'monetary', 'date_ref', 'clause_type', "
            "'contract_type', 'document_edition')",
            name='check_entity_type'
        ),
        sa.CheckConstraint(
            "extracted_by IN ('parser', 'rule', 'llm', 'manual')",
            name='check_entity_extracted_by'
        ),
    )
    op.create_index('ix_graph_entities_node_id', 'graph_entities', ['node_id'])
    op.create_index('ix_graph_entities_entity_type', 'graph_entities', ['entity_type'])
    op.create_index('ix_graph_entities_type_value', 'graph_entities',
                    ['entity_type', 'entity_value'])

    # ═══════════════════════════════════════════════════
    # 7. rag_audit_log — аудит изменений графа
    # ═══════════════════════════════════════════════════

    op.create_table(
        'rag_audit_log',
        sa.Column('id', sa.Integer, primary_key=True, autoincrement=True),
        sa.Column('action', sa.String(30), nullable=False),
        sa.Column('entity_type', sa.String(30), nullable=False),
        sa.Column('entity_id', sa.String(36), nullable=False),
        sa.Column('actor', sa.String(20), nullable=False),
        sa.Column('user_id', sa.String(36),
                  sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('changes', sa.JSON, nullable=True),
        sa.Column('reason', sa.Text, nullable=True),
        sa.Column('context', sa.JSON, nullable=True),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index('ix_rag_audit_log_action', 'rag_audit_log', ['action'])
    op.create_index('ix_rag_audit_log_entity_id', 'rag_audit_log', ['entity_id'])
    op.create_index('ix_rag_audit_log_created_at', 'rag_audit_log', ['created_at'])
    op.create_index('ix_rag_audit_entity', 'rag_audit_log', ['entity_type', 'entity_id'])
    op.create_index('ix_rag_audit_action_time', 'rag_audit_log', ['action', 'created_at'])


def downgrade():
    """Drop Graph-RAG tables in reverse order."""
    op.drop_table('rag_audit_log')
    op.drop_table('graph_entities')
    op.drop_table('candidate_edges')
    op.drop_table('graph_edges')
    op.drop_table('node_versions')
    op.drop_table('graph_nodes')
    op.drop_table('graph_documents')
