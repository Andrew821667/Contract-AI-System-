"""Create IDP tables for Hybrid Star Schema

Revision ID: 001_idp_tables
Revises:
Create Date: 2026-01-08 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '001_idp_tables'
down_revision = None  # Root migration — requires 'contracts' and 'users' tables from Base.metadata
branch_labels = None
depends_on = None


def upgrade():
    """Create IDP tables"""

    # ============================================================
    # 1. Центральная таблица contracts_core
    # ============================================================
    op.create_table(
        'contracts_core',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text('gen_random_uuid()')),

        # Стандартные поля
        sa.Column('doc_number', sa.String(100), nullable=False),
        sa.Column('signed_date', sa.Date, nullable=True),
        sa.Column('status', sa.String(20), nullable=False, server_default='active'),
        sa.Column('total_amount', sa.Numeric(15, 2), nullable=True),
        sa.Column('currency', sa.String(3), nullable=False, server_default='RUB'),

        # Гибкие атрибуты (JSONB)
        sa.Column('attributes', postgresql.JSONB, nullable=True),
        sa.Column('raw_data', postgresql.JSONB, nullable=True),

        # Метаданные
        sa.Column('created_at', sa.DateTime, nullable=False,
                  server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.DateTime, nullable=False,
                  server_default=sa.text('NOW()')),
        sa.Column('processed_by', sa.String(50), nullable=True),

        # Foreign key к старой таблице contracts
        sa.Column('source_file_id', sa.String(36), nullable=True),
        sa.ForeignKeyConstraint(['source_file_id'], ['contracts.id'],
                                ondelete='SET NULL'),

        # Constraints
        sa.CheckConstraint('status IN (\'draft\', \'active\', \'closed\', \'dispute\')',
                           name='check_status'),
        sa.CheckConstraint('total_amount >= 0', name='check_amount'),
    )

    # Индексы для contracts_core
    op.create_index('idx_contracts_core_doc_number', 'contracts_core', ['doc_number'])
    op.create_index('idx_contracts_core_signed_date', 'contracts_core', ['signed_date'])
    op.create_index('idx_contracts_core_status', 'contracts_core', ['status'])
    op.create_index('idx_contracts_core_source_file', 'contracts_core', ['source_file_id'])

    # GIN индекс для JSONB
    op.create_index('idx_contracts_core_attributes', 'contracts_core', ['attributes'],
                    postgresql_using='gin')

    # ============================================================
    # 2. Стороны договора
    # ============================================================
    op.create_table(
        'contract_parties',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text('gen_random_uuid()')),
        sa.Column('contract_id', postgresql.UUID(as_uuid=True), nullable=False),

        # Роль и идентификация
        sa.Column('role', sa.String(50), nullable=False),
        sa.Column('entity_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('name', sa.String(500), nullable=False),
        sa.Column('tax_id', sa.String(20), nullable=True),
        sa.Column('registration_number', sa.String(50), nullable=True),

        # Контактные данные
        sa.Column('legal_address', sa.Text, nullable=True),
        sa.Column('actual_address', sa.Text, nullable=True),
        sa.Column('contact_person', sa.String(200), nullable=True),
        sa.Column('email', sa.String(100), nullable=True),
        sa.Column('phone', sa.String(50), nullable=True),

        # Банковские реквизиты
        sa.Column('bank_details', postgresql.JSONB, nullable=True),

        sa.Column('created_at', sa.DateTime, nullable=False,
                  server_default=sa.text('NOW()')),

        # Foreign keys
        sa.ForeignKeyConstraint(['contract_id'], ['contracts_core.id'],
                                ondelete='CASCADE'),

        # Constraints
        sa.CheckConstraint('role IN (\'buyer\', \'seller\', \'guarantor\', \'agent\')',
                           name='check_party_role'),
        sa.UniqueConstraint('contract_id', 'role', 'tax_id',
                           name='uq_contract_party'),
    )

    op.create_index('idx_parties_contract', 'contract_parties', ['contract_id'])
    op.create_index('idx_parties_tax_id', 'contract_parties', ['tax_id'])
    op.create_index('idx_parties_entity', 'contract_parties', ['entity_id'])

    # ============================================================
    # 3. Спецификация (позиции договора)
    # ============================================================
    op.create_table(
        'contract_items',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text('gen_random_uuid()')),
        sa.Column('contract_id', postgresql.UUID(as_uuid=True), nullable=False),

        # Идентификация позиции
        sa.Column('line_number', sa.Integer, nullable=False),
        sa.Column('sku_code', sa.String(100), nullable=True),

        # Описание
        sa.Column('name', sa.Text, nullable=False),
        sa.Column('description', sa.Text, nullable=True),

        # Количество и единицы
        sa.Column('quantity', sa.Numeric(15, 3), nullable=False),
        sa.Column('unit', sa.String(20), nullable=True),

        # Финансы
        sa.Column('price_unit', sa.Numeric(15, 2), nullable=False),
        sa.Column('total_line', sa.Numeric(15, 2), nullable=False),
        sa.Column('vat_rate', sa.Numeric(5, 2), nullable=True),
        sa.Column('vat_amount', sa.Numeric(15, 2), nullable=True),

        # Дополнительные атрибуты
        sa.Column('attributes', postgresql.JSONB, nullable=True),

        sa.Column('created_at', sa.DateTime, nullable=False,
                  server_default=sa.text('NOW()')),

        # Foreign keys
        sa.ForeignKeyConstraint(['contract_id'], ['contracts_core.id'],
                                ondelete='CASCADE'),

        # Constraints
        sa.CheckConstraint('quantity > 0', name='check_quantity'),
        sa.CheckConstraint('price_unit >= 0', name='check_price'),
        sa.UniqueConstraint('contract_id', 'line_number',
                           name='uq_contract_line'),
    )

    op.create_index('idx_items_contract', 'contract_items', ['contract_id'])
    op.create_index('idx_items_sku', 'contract_items', ['sku_code'])
    op.create_index('idx_items_attributes', 'contract_items', ['attributes'],
                    postgresql_using='gin')

    # ============================================================
    # 4. График платежей
    # ============================================================
    op.create_table(
        'payment_schedule',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text('gen_random_uuid()')),
        sa.Column('contract_id', postgresql.UUID(as_uuid=True), nullable=False),

        # Тип платежа
        sa.Column('payment_type', sa.String(50), nullable=False),

        # Сумма
        sa.Column('amount', sa.Numeric(15, 2), nullable=False),
        sa.Column('percentage', sa.Numeric(5, 2), nullable=True),

        # Сроки
        sa.Column('due_date', sa.Date, nullable=True),
        sa.Column('due_condition', sa.Text, nullable=True),
        sa.Column('days_offset', sa.Integer, nullable=True),
        sa.Column('trigger_event', sa.String(100), nullable=True),

        # Статус
        sa.Column('status', sa.String(20), nullable=False, server_default='pending'),
        sa.Column('paid_date', sa.Date, nullable=True),
        sa.Column('paid_amount', sa.Numeric(15, 2), nullable=True),

        sa.Column('created_at', sa.DateTime, nullable=False,
                  server_default=sa.text('NOW()')),

        # Foreign keys
        sa.ForeignKeyConstraint(['contract_id'], ['contracts_core.id'],
                                ondelete='CASCADE'),

        # Constraints
        sa.CheckConstraint(
            'payment_type IN (\'prepayment\', \'postpayment\', \'milestone\', \'recurring\', \'on_delivery\')',
            name='check_payment_type'
        ),
        sa.CheckConstraint(
            'status IN (\'pending\', \'paid\', \'overdue\', \'cancelled\')',
            name='check_payment_status'
        ),
        sa.CheckConstraint('amount >= 0', name='check_payment_amount'),
    )

    op.create_index('idx_payment_contract', 'payment_schedule', ['contract_id'])
    op.create_index('idx_payment_status', 'payment_schedule', ['status'])
    op.create_index('idx_payment_due_date', 'payment_schedule', ['due_date'])

    # ============================================================
    # 5. Правила (Executable Logic) 🔥
    # ============================================================
    op.create_table(
        'contract_rules',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text('gen_random_uuid()')),
        sa.Column('contract_id', postgresql.UUID(as_uuid=True), nullable=False),

        # Тип правила
        sa.Column('section_type', sa.String(50), nullable=False),

        # Правило
        sa.Column('rule_name', sa.String(200), nullable=False),
        sa.Column('trigger_condition', sa.Text, nullable=True),
        sa.Column('formula', postgresql.JSONB, nullable=False),

        # Исходный текст
        sa.Column('original_text', sa.Text, nullable=False),
        sa.Column('clause_location', sa.String(200), nullable=True),

        # Приоритет и активность
        sa.Column('priority', sa.Integer, nullable=False, server_default='0'),
        sa.Column('is_active', sa.Boolean, nullable=False, server_default='true'),

        # Метаданные
        sa.Column('created_at', sa.DateTime, nullable=False,
                  server_default=sa.text('NOW()')),
        sa.Column('extracted_by', sa.String(50), nullable=True),
        sa.Column('confidence_score', sa.Numeric(3, 2), nullable=True),

        # Foreign keys
        sa.ForeignKeyConstraint(['contract_id'], ['contracts_core.id'],
                                ondelete='CASCADE'),

        # Constraints
        sa.CheckConstraint(
            'section_type IN (\'liability\', \'penalty\', \'termination\', \'sla\', \'force_majeure\', \'dispute\', \'confidentiality\')',
            name='check_section_type'
        ),
        sa.CheckConstraint('confidence_score BETWEEN 0 AND 1',
                           name='check_confidence'),
    )

    op.create_index('idx_rules_contract', 'contract_rules', ['contract_id'])
    op.create_index('idx_rules_section_type', 'contract_rules', ['section_type'])
    op.create_index('idx_rules_active', 'contract_rules', ['is_active'])
    op.create_index('idx_rules_formula', 'contract_rules', ['formula'],
                    postgresql_using='gin')

    # ============================================================
    # 6. Лог обработки IDP
    # ============================================================
    op.create_table(
        'idp_extraction_log',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text('gen_random_uuid()')),
        sa.Column('contract_id', postgresql.UUID(as_uuid=True), nullable=True),

        # Этап обработки
        sa.Column('stage', sa.String(50), nullable=False),
        sa.Column('status', sa.String(20), nullable=False),

        # Детали
        sa.Column('input_data', postgresql.JSONB, nullable=True),
        sa.Column('output_data', postgresql.JSONB, nullable=True),
        sa.Column('error_message', sa.Text, nullable=True),

        # Метрики производительности
        sa.Column('duration_ms', sa.Integer, nullable=True),
        sa.Column('tokens_used', sa.Integer, nullable=True),
        sa.Column('cost_usd', sa.Numeric(10, 4), nullable=True),

        # Конфигурация
        sa.Column('processor_type', sa.String(50), nullable=True),
        sa.Column('model_version', sa.String(50), nullable=True),

        sa.Column('created_at', sa.DateTime, nullable=False,
                  server_default=sa.text('NOW()')),

        # Foreign keys
        sa.ForeignKeyConstraint(['contract_id'], ['contracts_core.id'],
                                ondelete='SET NULL'),

        # Constraints
        sa.CheckConstraint(
            'stage IN (\'classification\', \'ocr\', \'layout_analysis\', \'entity_extraction\', \'table_extraction\', \'rule_extraction\', \'validation\')',
            name='check_stage'
        ),
        sa.CheckConstraint(
            'status IN (\'success\', \'partial\', \'failed\')',
            name='check_log_status'
        ),
    )

    op.create_index('idx_idp_log_contract', 'idp_extraction_log', ['contract_id'])
    op.create_index('idx_idp_log_stage', 'idp_extraction_log', ['stage'])
    op.create_index('idx_idp_log_status', 'idp_extraction_log', ['status'])
    op.create_index('idx_idp_log_created', 'idp_extraction_log', ['created_at'])

    # ============================================================
    # 7. Проблемы качества IDP
    # ============================================================
    op.create_table(
        'idp_quality_issues',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text('gen_random_uuid()')),
        sa.Column('contract_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('extraction_log_id', postgresql.UUID(as_uuid=True), nullable=True),

        # Тип проблемы
        sa.Column('issue_type', sa.String(50), nullable=False),
        sa.Column('severity', sa.String(20), nullable=False),

        # Описание
        sa.Column('field_name', sa.String(100), nullable=True),
        sa.Column('expected_value', sa.Text, nullable=True),
        sa.Column('actual_value', sa.Text, nullable=True),
        sa.Column('description', sa.Text, nullable=True),

        # Рекомендации
        sa.Column('suggested_action', sa.String(200), nullable=True),
        sa.Column('requires_manual_review', sa.Boolean, nullable=False,
                  server_default='false'),

        # Статус обработки
        sa.Column('status', sa.String(20), nullable=False, server_default='open'),
        sa.Column('resolved_at', sa.DateTime, nullable=True),
        sa.Column('resolved_by', sa.String(36), nullable=True),

        sa.Column('created_at', sa.DateTime, nullable=False,
                  server_default=sa.text('NOW()')),

        # Foreign keys
        sa.ForeignKeyConstraint(['contract_id'], ['contracts_core.id'],
                                ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['extraction_log_id'], ['idp_extraction_log.id'],
                                ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['resolved_by'], ['users.id'],
                                ondelete='SET NULL'),

        # Constraints
        sa.CheckConstraint(
            'issue_type IN (\'low_ocr_confidence\', \'missing_field\', \'ambiguous_value\', \'validation_error\', \'conflicting_data\')',
            name='check_issue_type'
        ),
        sa.CheckConstraint(
            'severity IN (\'critical\', \'warning\', \'info\')',
            name='check_severity'
        ),
        sa.CheckConstraint(
            'status IN (\'open\', \'resolved\', \'ignored\')',
            name='check_issue_status'
        ),
    )

    op.create_index('idx_quality_contract', 'idp_quality_issues', ['contract_id'])
    op.create_index('idx_quality_severity', 'idp_quality_issues', ['severity'])
    op.create_index('idx_quality_status', 'idp_quality_issues', ['status'])
    op.create_index('idx_quality_manual_review', 'idp_quality_issues',
                    ['requires_manual_review'])


def downgrade():
    """Drop IDP tables"""
    op.drop_table('idp_quality_issues')
    op.drop_table('idp_extraction_log')
    op.drop_table('contract_rules')
    op.drop_table('payment_schedule')
    op.drop_table('contract_items')
    op.drop_table('contract_parties')
    op.drop_table('contracts_core')
