"""Core AI Collaborative tables — Phase 0

Создание ~30 новых таблиц для AI-collaborative contract OS.
Backward-compatible: только CREATE TABLE, без ALTER на существующие таблицы.

Revision ID: 012_core_ai_collaborative
Revises: 011_legal_document_kb_fields
Create Date: 2026-03-16 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '012_core_ai_collaborative'
down_revision = '011_legal_document_kb_fields'
branch_labels = None
depends_on = None


def upgrade():
    """Create all core AI collaborative tables."""

    # ═══════════════════════════════════════════════════
    # 1. identity_org — организации и участие
    # ═══════════════════════════════════════════════════

    op.create_table(
        'organizations',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('slug', sa.String(100), unique=True, nullable=False),
        sa.Column('description', sa.Text, nullable=True),
        sa.Column('settings', sa.JSON, nullable=True),
        sa.Column('active', sa.Boolean, server_default='1'),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index('ix_organizations_slug', 'organizations', ['slug'])
    op.create_index('ix_organizations_active', 'organizations', ['active'])

    op.create_table(
        'organization_units',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('org_id', sa.String(36), sa.ForeignKey('organizations.id', ondelete='CASCADE'), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('parent_unit_id', sa.String(36), sa.ForeignKey('organization_units.id', ondelete='SET NULL'), nullable=True),
        sa.Column('level', sa.String(50), nullable=False, server_default='department'),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index('ix_org_units_org_id', 'organization_units', ['org_id'])
    op.create_index('ix_org_units_parent', 'organization_units', ['parent_unit_id'])
    op.create_index('idx_unit_org_parent', 'organization_units', ['org_id', 'parent_unit_id'])

    op.create_table(
        'organization_memberships',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('user_id', sa.String(36), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('org_id', sa.String(36), sa.ForeignKey('organizations.id', ondelete='CASCADE'), nullable=False),
        sa.Column('unit_id', sa.String(36), sa.ForeignKey('organization_units.id', ondelete='SET NULL'), nullable=True),
        sa.Column('company_role', sa.String(100), nullable=True),
        sa.Column('functional_role', sa.String(50), nullable=False, server_default='member'),
        sa.Column('active', sa.Boolean, server_default='1'),
        sa.Column('joined_at', sa.DateTime, server_default=sa.func.now()),
        sa.UniqueConstraint('user_id', 'org_id', name='uq_user_org_membership'),
        sa.CheckConstraint(
            "functional_role IN ('org_admin', 'manager', 'member', 'viewer')",
            name='check_functional_role',
        ),
    )
    op.create_index('ix_org_memberships_user_id', 'organization_memberships', ['user_id'])
    op.create_index('ix_org_memberships_org_id', 'organization_memberships', ['org_id'])
    op.create_index('ix_org_memberships_active', 'organization_memberships', ['active'])
    op.create_index('idx_membership_org_active', 'organization_memberships', ['org_id', 'active'])

    op.create_table(
        'document_participations',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('user_id', sa.String(36), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('document_id', sa.String(36), sa.ForeignKey('contracts.id', ondelete='CASCADE'), nullable=False),
        sa.Column('role', sa.String(50), nullable=False),
        sa.Column('assigned_at', sa.DateTime, server_default=sa.func.now()),
        sa.Column('assigned_by', sa.String(36), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.UniqueConstraint('user_id', 'document_id', 'role', name='uq_user_doc_role'),
        sa.CheckConstraint(
            "role IN ('owner', 'reviewer', 'approver', 'observer', 'negotiator', 'signer', 'ai_supervisor')",
            name='check_doc_participation_role',
        ),
    )
    op.create_index('ix_doc_participations_user_id', 'document_participations', ['user_id'])
    op.create_index('ix_doc_participations_doc_id', 'document_participations', ['document_id'])
    op.create_index('idx_doc_participation_doc', 'document_participations', ['document_id', 'role'])

    op.create_table(
        'tenant_contexts',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('org_id', sa.String(36), sa.ForeignKey('organizations.id', ondelete='CASCADE'), unique=True, nullable=False),
        sa.Column('mode', sa.String(20), nullable=False, server_default='standalone'),
        sa.Column('parent_tenant_id', sa.String(36), sa.ForeignKey('tenant_contexts.id', ondelete='SET NULL'), nullable=True),
        sa.Column('config', sa.JSON, nullable=True),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        sa.CheckConstraint("mode IN ('standalone', 'branch')", name='check_tenant_mode'),
    )

    op.create_table(
        'user_agent_policy_profiles',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('user_id', sa.String(36), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('org_id', sa.String(36), sa.ForeignKey('organizations.id', ondelete='CASCADE'), nullable=True),
        sa.Column('allowed_ai_modes', sa.JSON, nullable=True),
        sa.Column('allowed_actions', sa.JSON, nullable=True),
        sa.Column('allowed_agents', sa.JSON, nullable=True),
        sa.Column('allowed_tools', sa.JSON, nullable=True),
        sa.Column('approval_required_for', sa.JSON, nullable=True),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, server_default=sa.func.now()),
        sa.UniqueConstraint('user_id', 'org_id', name='uq_user_org_agent_policy'),
    )
    op.create_index('ix_uapp_user_id', 'user_agent_policy_profiles', ['user_id'])
    op.create_index('ix_uapp_org_id', 'user_agent_policy_profiles', ['org_id'])

    # ═══════════════════════════════════════════════════
    # 2. policies — каскад политик
    # ═══════════════════════════════════════════════════

    op.create_table(
        'policies',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('description', sa.Text, nullable=True),
        sa.Column('level', sa.String(20), nullable=False),
        sa.Column('scope_id', sa.String(36), nullable=True),
        sa.Column('policy_type', sa.String(50), nullable=False),
        sa.Column('rules', sa.JSON, nullable=False),
        sa.Column('priority', sa.Integer, server_default='0'),
        sa.Column('active', sa.Boolean, server_default='1'),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, server_default=sa.func.now()),
        sa.CheckConstraint(
            "level IN ('platform', 'tenant', 'organization', 'branch', 'document', 'user')",
            name='check_policy_level',
        ),
    )
    op.create_index('ix_policies_level', 'policies', ['level'])
    op.create_index('ix_policies_scope_id', 'policies', ['scope_id'])
    op.create_index('ix_policies_policy_type', 'policies', ['policy_type'])
    op.create_index('ix_policies_active', 'policies', ['active'])
    op.create_index('idx_policy_level_scope', 'policies', ['level', 'scope_id', 'active'])
    op.create_index('idx_policy_type_active', 'policies', ['policy_type', 'active'])

    op.create_table(
        'approval_rules',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('policy_id', sa.String(36), sa.ForeignKey('policies.id', ondelete='CASCADE'), nullable=False),
        sa.Column('action_pattern', sa.String(255), nullable=False),
        sa.Column('required_approvers', sa.Integer, server_default='1'),
        sa.Column('escalation_timeout', sa.Integer, server_default='0'),
        sa.Column('escalation_target', sa.String(100), nullable=True),
        sa.Column('active', sa.Boolean, server_default='1'),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index('ix_approval_rules_policy_id', 'approval_rules', ['policy_id'])
    op.create_index('idx_approval_policy_pattern', 'approval_rules', ['policy_id', 'action_pattern'])

    op.create_table(
        'action_permissions',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('policy_id', sa.String(36), sa.ForeignKey('policies.id', ondelete='CASCADE'), nullable=False),
        sa.Column('action_type', sa.String(100), nullable=False),
        sa.Column('allowed_roles', sa.JSON, nullable=False),
        sa.Column('conditions', sa.JSON, nullable=True),
        sa.Column('active', sa.Boolean, server_default='1'),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index('ix_action_perms_policy_id', 'action_permissions', ['policy_id'])
    op.create_index('idx_action_perm_policy_type', 'action_permissions', ['policy_id', 'action_type'])

    # ═══════════════════════════════════════════════════
    # 3. tools — инструменты
    # ═══════════════════════════════════════════════════

    op.create_table(
        'tool_definitions',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('tool_id', sa.String(100), unique=True, nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('description', sa.Text, nullable=True),
        sa.Column('tool_type', sa.String(20), nullable=False, server_default='internal'),
        sa.Column('input_schema', sa.JSON, nullable=True),
        sa.Column('output_schema', sa.JSON, nullable=True),
        sa.Column('permissions', sa.JSON, nullable=True),
        sa.Column('policy_tags', sa.JSON, nullable=True),
        sa.Column('risk_level', sa.String(20), nullable=False, server_default='low'),
        sa.Column('sync_mode', sa.String(10), nullable=False, server_default='sync'),
        sa.Column('active', sa.Boolean, server_default='1'),
        sa.Column('version', sa.String(20), server_default='1.0.0'),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, server_default=sa.func.now()),
        sa.CheckConstraint("risk_level IN ('low', 'medium', 'high', 'critical')", name='check_tool_risk_level'),
        sa.CheckConstraint("sync_mode IN ('sync', 'async')", name='check_tool_sync_mode'),
        sa.CheckConstraint("tool_type IN ('internal', 'external')", name='check_tool_type'),
    )
    op.create_index('ix_tool_definitions_tool_id', 'tool_definitions', ['tool_id'])
    op.create_index('ix_tool_definitions_active', 'tool_definitions', ['active'])

    op.create_table(
        'tool_invocations',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('tool_id', sa.String(100), nullable=False),
        sa.Column('invoked_by', sa.String(100), nullable=False),
        sa.Column('session_id', sa.String(36), nullable=True),
        sa.Column('run_id', sa.String(36), nullable=True),
        sa.Column('correlation_id', sa.String(36), nullable=True),
        sa.Column('input_data', sa.JSON, nullable=True),
        sa.Column('output_data', sa.JSON, nullable=True),
        sa.Column('status', sa.String(20), nullable=False, server_default='pending'),
        sa.Column('error', sa.Text, nullable=True),
        sa.Column('duration_ms', sa.Integer, server_default='0'),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        sa.CheckConstraint(
            "status IN ('pending', 'running', 'completed', 'failed', 'blocked')",
            name='check_tool_invocation_status',
        ),
    )
    op.create_index('ix_tool_inv_tool_id', 'tool_invocations', ['tool_id'])
    op.create_index('ix_tool_inv_session_id', 'tool_invocations', ['session_id'])
    op.create_index('ix_tool_inv_run_id', 'tool_invocations', ['run_id'])
    op.create_index('ix_tool_inv_correlation_id', 'tool_invocations', ['correlation_id'])
    op.create_index('idx_tool_inv_tool_status', 'tool_invocations', ['tool_id', 'status'])
    op.create_index('idx_tool_inv_created', 'tool_invocations', ['created_at'])

    # ═══════════════════════════════════════════════════
    # 4. agents — агенты
    # ═══════════════════════════════════════════════════

    op.create_table(
        'agent_definitions',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('agent_id', sa.String(100), unique=True, nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('description', sa.Text, nullable=True),
        sa.Column('specialization', sa.String(100), nullable=False),
        sa.Column('allowed_tools', sa.JSON, nullable=True),
        sa.Column('task_types', sa.JSON, nullable=True),
        sa.Column('autonomy_level', sa.String(20), nullable=False, server_default='copilot'),
        sa.Column('confidence_threshold', sa.Float, server_default='0.8'),
        sa.Column('model_profile', sa.JSON, nullable=True),
        sa.Column('active', sa.Boolean, server_default='1'),
        sa.Column('version', sa.String(20), server_default='1.0.0'),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, server_default=sa.func.now()),
        sa.CheckConstraint(
            "autonomy_level IN ('advisor', 'copilot', 'processor', 'autonomous')",
            name='check_agent_autonomy_level',
        ),
    )
    op.create_index('ix_agent_def_agent_id', 'agent_definitions', ['agent_id'])
    op.create_index('ix_agent_def_active', 'agent_definitions', ['active'])
    op.create_index('idx_agent_def_spec', 'agent_definitions', ['specialization', 'active'])

    op.create_table(
        'agent_invocations',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('agent_id', sa.String(100), nullable=False),
        sa.Column('task_type', sa.String(100), nullable=True),
        sa.Column('session_id', sa.String(36), nullable=True),
        sa.Column('run_id', sa.String(36), nullable=True),
        sa.Column('correlation_id', sa.String(36), nullable=True),
        sa.Column('task_data', sa.JSON, nullable=True),
        sa.Column('context_data', sa.JSON, nullable=True),
        sa.Column('result_data', sa.JSON, nullable=True),
        sa.Column('tools_used', sa.JSON, nullable=True),
        sa.Column('status', sa.String(20), nullable=False, server_default='pending'),
        sa.Column('confidence', sa.Float, nullable=True),
        sa.Column('duration_ms', sa.Integer, server_default='0'),
        sa.Column('error', sa.Text, nullable=True),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        sa.CheckConstraint(
            "status IN ('pending', 'running', 'completed', 'failed', 'blocked')",
            name='check_agent_invocation_status',
        ),
    )
    op.create_index('ix_agent_inv_agent_id', 'agent_invocations', ['agent_id'])
    op.create_index('ix_agent_inv_task_type', 'agent_invocations', ['task_type'])
    op.create_index('ix_agent_inv_session_id', 'agent_invocations', ['session_id'])
    op.create_index('ix_agent_inv_run_id', 'agent_invocations', ['run_id'])
    op.create_index('ix_agent_inv_correlation_id', 'agent_invocations', ['correlation_id'])
    op.create_index('idx_agent_inv_agent_status', 'agent_invocations', ['agent_id', 'status'])

    op.create_table(
        'agent_delegations',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('from_agent_id', sa.String(100), nullable=False),
        sa.Column('to_agent_id', sa.String(100), nullable=False),
        sa.Column('run_id', sa.String(36), nullable=True),
        sa.Column('task_data', sa.JSON, nullable=True),
        sa.Column('result_data', sa.JSON, nullable=True),
        sa.Column('status', sa.String(20), nullable=False, server_default='pending'),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        sa.Column('completed_at', sa.DateTime, nullable=True),
        sa.CheckConstraint(
            "status IN ('pending', 'running', 'completed', 'failed')",
            name='check_delegation_status',
        ),
    )
    op.create_index('ix_agent_deleg_from', 'agent_delegations', ['from_agent_id'])
    op.create_index('ix_agent_deleg_to', 'agent_delegations', ['to_agent_id'])
    op.create_index('ix_agent_deleg_run', 'agent_delegations', ['run_id'])
    op.create_index('idx_delegation_run', 'agent_delegations', ['run_id', 'status'])

    # ═══════════════════════════════════════════════════
    # 5. ai_collaboration — AI-сессии, сообщения, действия
    # ═══════════════════════════════════════════════════

    op.create_table(
        'ai_sessions',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('document_id', sa.String(36), sa.ForeignKey('contracts.id', ondelete='CASCADE'), nullable=False),
        sa.Column('user_id', sa.String(36), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('organization_id', sa.String(36), sa.ForeignKey('organizations.id', ondelete='SET NULL'), nullable=True),
        sa.Column('stage', sa.String(30), nullable=False, server_default='intake'),
        sa.Column('status', sa.String(20), nullable=False, server_default='active'),
        sa.Column('context_snapshot', sa.JSON, nullable=True),
        sa.Column('total_turns', sa.Integer, server_default='0'),
        sa.Column('total_actions', sa.Integer, server_default='0'),
        sa.Column('total_tokens_used', sa.Integer, server_default='0'),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, server_default=sa.func.now()),
        sa.Column('closed_at', sa.DateTime, nullable=True),
        sa.CheckConstraint(
            "stage IN ('intake', 'classification', 'analysis', 'review', 'negotiation', 'approval', 'generation', 'export')",
            name='check_ai_session_stage',
        ),
        sa.CheckConstraint(
            "status IN ('active', 'paused', 'closed')",
            name='check_ai_session_status',
        ),
    )
    op.create_index('ix_ai_sessions_doc_id', 'ai_sessions', ['document_id'])
    op.create_index('ix_ai_sessions_user_id', 'ai_sessions', ['user_id'])
    op.create_index('ix_ai_sessions_org_id', 'ai_sessions', ['organization_id'])
    op.create_index('idx_ai_session_doc_user', 'ai_sessions', ['document_id', 'user_id'])
    op.create_index('idx_ai_session_status', 'ai_sessions', ['status', 'created_at'])

    op.create_table(
        'ai_conversation_turns',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('session_id', sa.String(36), sa.ForeignKey('ai_sessions.id', ondelete='CASCADE'), nullable=False),
        sa.Column('role', sa.String(20), nullable=False),
        sa.Column('content', sa.Text, nullable=False),
        sa.Column('model_used', sa.String(100), nullable=True),
        sa.Column('tokens_input', sa.Integer, server_default='0'),
        sa.Column('tokens_output', sa.Integer, server_default='0'),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        sa.CheckConstraint("role IN ('user', 'assistant', 'system')", name='check_turn_role'),
    )
    op.create_index('ix_ai_turns_session_id', 'ai_conversation_turns', ['session_id'])
    op.create_index('idx_turn_session_created', 'ai_conversation_turns', ['session_id', 'created_at'])

    op.create_table(
        'ai_actions',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('session_id', sa.String(36), sa.ForeignKey('ai_sessions.id', ondelete='CASCADE'), nullable=False),
        sa.Column('action_type', sa.String(50), nullable=False),
        sa.Column('target_entity_type', sa.String(50), nullable=True),
        sa.Column('target_entity_id', sa.String(36), nullable=True),
        sa.Column('payload', sa.JSON, nullable=True),
        sa.Column('rationale', sa.Text, nullable=True),
        sa.Column('confidence', sa.Float, server_default='0.0'),
        sa.Column('approval_required', sa.Boolean, server_default='1'),
        sa.Column('execution_status', sa.String(20), nullable=False, server_default='pending'),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        sa.Column('executed_at', sa.DateTime, nullable=True),
        sa.CheckConstraint(
            "execution_status IN ('pending', 'approved', 'rejected', 'executed', 'blocked', 'failed')",
            name='check_ai_action_status',
        ),
    )
    op.create_index('ix_ai_actions_session_id', 'ai_actions', ['session_id'])
    op.create_index('ix_ai_actions_action_type', 'ai_actions', ['action_type'])
    op.create_index('idx_ai_action_session_status', 'ai_actions', ['session_id', 'execution_status'])
    op.create_index('idx_ai_action_type', 'ai_actions', ['action_type', 'execution_status'])

    op.create_table(
        'ai_action_approvals',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('action_id', sa.String(36), sa.ForeignKey('ai_actions.id', ondelete='CASCADE'), unique=True, nullable=False),
        sa.Column('approver_id', sa.String(36), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('decision', sa.String(30), nullable=False),
        sa.Column('comment', sa.Text, nullable=True),
        sa.Column('edited_payload', sa.JSON, nullable=True),
        sa.Column('decided_at', sa.DateTime, server_default=sa.func.now()),
        sa.CheckConstraint(
            "decision IN ('approve', 'reject', 'edit_and_approve')",
            name='check_approval_decision',
        ),
    )
    op.create_index('ix_ai_approvals_approver_id', 'ai_action_approvals', ['approver_id'])

    op.create_table(
        'ai_audit_records',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('session_id', sa.String(36), sa.ForeignKey('ai_sessions.id', ondelete='CASCADE'), nullable=True),
        sa.Column('action_id', sa.String(36), sa.ForeignKey('ai_actions.id', ondelete='SET NULL'), nullable=True),
        sa.Column('actor', sa.String(100), nullable=False),
        sa.Column('event_type', sa.String(50), nullable=False),
        sa.Column('details', sa.JSON, nullable=True),
        sa.Column('model_used', sa.String(100), nullable=True),
        sa.Column('context_sent', sa.JSON, nullable=True),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index('ix_ai_audit_session_id', 'ai_audit_records', ['session_id'])
    op.create_index('ix_ai_audit_action_id', 'ai_audit_records', ['action_id'])
    op.create_index('ix_ai_audit_event_type', 'ai_audit_records', ['event_type'])
    op.create_index('idx_ai_audit_session_event', 'ai_audit_records', ['session_id', 'event_type'])
    op.create_index('idx_ai_audit_created', 'ai_audit_records', ['created_at'])

    # ═══════════════════════════════════════════════════
    # 6. orchestrator — оркестрация
    # ═══════════════════════════════════════════════════

    op.create_table(
        'orchestrator_runs',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('goal', sa.Text, nullable=False),
        sa.Column('initiated_by', sa.String(36), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('document_id', sa.String(36), sa.ForeignKey('contracts.id', ondelete='SET NULL'), nullable=True),
        sa.Column('session_id', sa.String(36), sa.ForeignKey('ai_sessions.id', ondelete='SET NULL'), nullable=True),
        sa.Column('status', sa.String(20), nullable=False, server_default='planning'),
        sa.Column('total_steps', sa.Integer, server_default='0'),
        sa.Column('completed_steps', sa.Integer, server_default='0'),
        sa.Column('failed_steps', sa.Integer, server_default='0'),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, server_default=sa.func.now()),
        sa.Column('completed_at', sa.DateTime, nullable=True),
        sa.CheckConstraint(
            "status IN ('planning', 'executing', 'paused', 'completed', 'failed', 'cancelled')",
            name='check_orch_run_status',
        ),
    )
    op.create_index('ix_orch_runs_initiated_by', 'orchestrator_runs', ['initiated_by'])
    op.create_index('ix_orch_runs_document_id', 'orchestrator_runs', ['document_id'])
    op.create_index('ix_orch_runs_session_id', 'orchestrator_runs', ['session_id'])
    op.create_index('idx_orch_run_status', 'orchestrator_runs', ['status', 'created_at'])

    op.create_table(
        'execution_plans',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('run_id', sa.String(36), sa.ForeignKey('orchestrator_runs.id', ondelete='CASCADE'), nullable=False),
        sa.Column('plan_definition', sa.JSON, nullable=False),
        sa.Column('version', sa.Integer, server_default='1'),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index('ix_exec_plans_run_id', 'execution_plans', ['run_id'])
    op.create_index('idx_exec_plan_run_ver', 'execution_plans', ['run_id', 'version'])

    op.create_table(
        'plan_steps',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('plan_id', sa.String(36), sa.ForeignKey('execution_plans.id', ondelete='CASCADE'), nullable=False),
        sa.Column('order', sa.Integer, nullable=False),
        sa.Column('name', sa.String(255), nullable=True),
        sa.Column('step_type', sa.String(30), nullable=False),
        sa.Column('tool_id', sa.String(100), nullable=True),
        sa.Column('agent_id', sa.String(100), nullable=True),
        sa.Column('input_data', sa.JSON, nullable=True),
        sa.Column('output_data', sa.JSON, nullable=True),
        sa.Column('condition', sa.JSON, nullable=True),
        sa.Column('status', sa.String(20), nullable=False, server_default='pending'),
        sa.Column('error', sa.Text, nullable=True),
        sa.Column('started_at', sa.DateTime, nullable=True),
        sa.Column('completed_at', sa.DateTime, nullable=True),
        sa.CheckConstraint(
            "step_type IN ('tool_call', 'agent_delegation', 'approval_checkpoint', 'condition')",
            name='check_plan_step_type',
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'running', 'completed', 'failed', 'blocked', 'skipped')",
            name='check_plan_step_status',
        ),
    )
    op.create_index('ix_plan_steps_plan_id', 'plan_steps', ['plan_id'])
    op.create_index('idx_plan_step_plan_order', 'plan_steps', ['plan_id', 'order'])

    op.create_table(
        'orchestrator_checkpoints',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('run_id', sa.String(36), sa.ForeignKey('orchestrator_runs.id', ondelete='CASCADE'), nullable=False),
        sa.Column('step_id', sa.String(36), sa.ForeignKey('plan_steps.id', ondelete='SET NULL'), nullable=True),
        sa.Column('checkpoint_type', sa.String(30), nullable=False),
        sa.Column('status', sa.String(20), nullable=False, server_default='pending'),
        sa.Column('resolved_by', sa.String(36), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('resolved_at', sa.DateTime, nullable=True),
        sa.Column('comment', sa.Text, nullable=True),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        sa.CheckConstraint(
            "checkpoint_type IN ('approval', 'review', 'escalation')",
            name='check_checkpoint_type',
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'approved', 'rejected', 'escalated')",
            name='check_checkpoint_status',
        ),
    )
    op.create_index('ix_orch_checkpoints_run_id', 'orchestrator_checkpoints', ['run_id'])
    op.create_index('ix_orch_checkpoints_step_id', 'orchestrator_checkpoints', ['step_id'])
    op.create_index('idx_checkpoint_run_status', 'orchestrator_checkpoints', ['run_id', 'status'])

    # ═══════════════════════════════════════════════════
    # 7. workflow — маршруты согласования
    # ═══════════════════════════════════════════════════

    op.create_table(
        'workflow_definitions',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('description', sa.Text, nullable=True),
        sa.Column('document_type', sa.String(50), nullable=True),
        sa.Column('jurisdiction', sa.String(50), nullable=True),
        sa.Column('org_id', sa.String(36), sa.ForeignKey('organizations.id', ondelete='SET NULL'), nullable=True),
        sa.Column('conditions', sa.JSON, nullable=True),
        sa.Column('steps', sa.JSON, nullable=False),
        sa.Column('active', sa.Boolean, server_default='1'),
        sa.Column('version', sa.Integer, server_default='1'),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index('ix_wf_defs_doc_type', 'workflow_definitions', ['document_type'])
    op.create_index('ix_wf_defs_org_id', 'workflow_definitions', ['org_id'])
    op.create_index('ix_wf_defs_active', 'workflow_definitions', ['active'])
    op.create_index('idx_wf_def_doctype', 'workflow_definitions', ['document_type', 'active'])

    op.create_table(
        'workflow_executions',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('definition_id', sa.String(36), sa.ForeignKey('workflow_definitions.id', ondelete='SET NULL'), nullable=True),
        sa.Column('document_id', sa.String(36), sa.ForeignKey('contracts.id', ondelete='CASCADE'), nullable=False),
        sa.Column('current_step', sa.Integer, server_default='0'),
        sa.Column('status', sa.String(20), nullable=False, server_default='active'),
        sa.Column('started_at', sa.DateTime, server_default=sa.func.now()),
        sa.Column('completed_at', sa.DateTime, nullable=True),
        sa.CheckConstraint(
            "status IN ('active', 'completed', 'cancelled', 'failed')",
            name='check_wf_execution_status',
        ),
    )
    op.create_index('ix_wf_execs_definition_id', 'workflow_executions', ['definition_id'])
    op.create_index('ix_wf_execs_document_id', 'workflow_executions', ['document_id'])
    op.create_index('idx_wf_exec_doc', 'workflow_executions', ['document_id', 'status'])

    op.create_table(
        'workflow_tasks',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('execution_id', sa.String(36), sa.ForeignKey('workflow_executions.id', ondelete='CASCADE'), nullable=False),
        sa.Column('step_name', sa.String(255), nullable=False),
        sa.Column('step_order', sa.Integer, nullable=False),
        sa.Column('assignee_id', sa.String(36), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('task_type', sa.String(50), server_default='review'),
        sa.Column('status', sa.String(20), nullable=False, server_default='pending'),
        sa.Column('decision', sa.String(30), nullable=True),
        sa.Column('comment', sa.Text, nullable=True),
        sa.Column('sla_deadline', sa.DateTime, nullable=True),
        sa.Column('sla_breached', sa.Boolean, server_default='0'),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        sa.Column('completed_at', sa.DateTime, nullable=True),
        sa.CheckConstraint(
            "status IN ('pending', 'in_progress', 'completed', 'escalated', 'skipped')",
            name='check_wf_task_status',
        ),
    )
    op.create_index('ix_wf_tasks_execution_id', 'workflow_tasks', ['execution_id'])
    op.create_index('ix_wf_tasks_assignee_id', 'workflow_tasks', ['assignee_id'])
    op.create_index('idx_wf_task_assignee_status', 'workflow_tasks', ['assignee_id', 'status'])
    op.create_index('idx_wf_task_sla', 'workflow_tasks', ['sla_deadline', 'sla_breached'])

    op.create_table(
        'workflow_events',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('execution_id', sa.String(36), sa.ForeignKey('workflow_executions.id', ondelete='CASCADE'), nullable=False),
        sa.Column('event_type', sa.String(50), nullable=False),
        sa.Column('payload', sa.JSON, nullable=True),
        sa.Column('triggered_by', sa.String(100), nullable=True),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index('ix_wf_events_execution_id', 'workflow_events', ['execution_id'])
    op.create_index('ix_wf_events_event_type', 'workflow_events', ['event_type'])
    op.create_index('idx_wf_event_exec_type', 'workflow_events', ['execution_id', 'event_type'])

    # ═══════════════════════════════════════════════════
    # 8. collaboration — комментарии
    # ═══════════════════════════════════════════════════

    op.create_table(
        'comments',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('document_id', sa.String(36), sa.ForeignKey('contracts.id', ondelete='CASCADE'), nullable=False),
        sa.Column('author_id', sa.String(36), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('content', sa.Text, nullable=False),
        sa.Column('anchor_type', sa.String(30), nullable=False, server_default='document'),
        sa.Column('anchor_id', sa.String(36), nullable=True),
        sa.Column('anchor_version', sa.String(20), nullable=True),
        sa.Column('is_ai_generated', sa.Boolean, server_default='0'),
        sa.Column('parent_comment_id', sa.String(36), sa.ForeignKey('comments.id', ondelete='SET NULL'), nullable=True),
        sa.Column('status', sa.String(20), nullable=False, server_default='active'),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, server_default=sa.func.now()),
        sa.CheckConstraint(
            "anchor_type IN ('document', 'section', 'clause', 'finding')",
            name='check_comment_anchor_type',
        ),
        sa.CheckConstraint(
            "status IN ('active', 'resolved', 'deleted')",
            name='check_comment_status',
        ),
    )
    op.create_index('ix_comments_document_id', 'comments', ['document_id'])
    op.create_index('ix_comments_author_id', 'comments', ['author_id'])
    op.create_index('ix_comments_is_ai', 'comments', ['is_ai_generated'])
    op.create_index('ix_comments_parent', 'comments', ['parent_comment_id'])
    op.create_index('idx_comment_doc_anchor', 'comments', ['document_id', 'anchor_type', 'anchor_id'])
    op.create_index('idx_comment_doc_status', 'comments', ['document_id', 'status'])

    op.create_table(
        'comment_threads',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('document_id', sa.String(36), sa.ForeignKey('contracts.id', ondelete='CASCADE'), nullable=False),
        sa.Column('root_comment_id', sa.String(36), sa.ForeignKey('comments.id', ondelete='CASCADE'), unique=True, nullable=False),
        sa.Column('status', sa.String(20), nullable=False, server_default='open'),
        sa.Column('resolved_by', sa.String(36), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('resolved_at', sa.DateTime, nullable=True),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        sa.CheckConstraint("status IN ('open', 'resolved')", name='check_thread_status'),
    )
    op.create_index('ix_threads_document_id', 'comment_threads', ['document_id'])
    op.create_index('idx_thread_doc_status', 'comment_threads', ['document_id', 'status'])

    op.create_table(
        'mentions',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('comment_id', sa.String(36), sa.ForeignKey('comments.id', ondelete='CASCADE'), nullable=False),
        sa.Column('user_id', sa.String(36), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('notified', sa.Boolean, server_default='0'),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index('ix_mentions_comment_id', 'mentions', ['comment_id'])
    op.create_index('ix_mentions_user_id', 'mentions', ['user_id'])
    op.create_index('idx_mention_user_notified', 'mentions', ['user_id', 'notified'])

    op.create_table(
        'comment_assignments',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('comment_id', sa.String(36), sa.ForeignKey('comments.id', ondelete='CASCADE'), unique=True, nullable=False),
        sa.Column('assignee_id', sa.String(36), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('status', sa.String(20), nullable=False, server_default='pending'),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        sa.Column('completed_at', sa.DateTime, nullable=True),
        sa.CheckConstraint("status IN ('pending', 'in_progress', 'done')", name='check_assignment_status'),
    )
    op.create_index('ix_assignments_assignee_id', 'comment_assignments', ['assignee_id'])
    op.create_index('idx_assignment_assignee_status', 'comment_assignments', ['assignee_id', 'status'])

    # ═══════════════════════════════════════════════════
    # 9. templates — template governance
    # ═══════════════════════════════════════════════════

    op.create_table(
        'template_versions',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('template_id', sa.String(36), sa.ForeignKey('templates.id', ondelete='CASCADE'), nullable=False),
        sa.Column('version', sa.Integer, nullable=False),
        sa.Column('content', sa.JSON, nullable=False),
        sa.Column('variables', sa.JSON, nullable=True),
        sa.Column('validation_rules', sa.JSON, nullable=True),
        sa.Column('status', sa.String(20), nullable=False, server_default='draft'),
        sa.Column('created_by', sa.String(36), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        sa.CheckConstraint(
            "status IN ('draft', 'active', 'deprecated')",
            name='check_template_version_status',
        ),
    )
    op.create_index('ix_tpl_versions_template_id', 'template_versions', ['template_id'])
    op.create_index('idx_tpl_ver_template_ver', 'template_versions', ['template_id', 'version'])

    op.create_table(
        'clause_policies',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('org_id', sa.String(36), sa.ForeignKey('organizations.id', ondelete='CASCADE'), nullable=True),
        sa.Column('clause_type', sa.String(50), nullable=False),
        sa.Column('status', sa.String(20), nullable=False),
        sa.Column('alternative_clause_id', sa.String(36), nullable=True),
        sa.Column('risk_explanation', sa.Text, nullable=True),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, server_default=sa.func.now()),
        sa.CheckConstraint(
            "status IN ('approved', 'fallback', 'prohibited', 'risky')",
            name='check_clause_policy_status',
        ),
    )
    op.create_index('ix_clause_policies_org_id', 'clause_policies', ['org_id'])
    op.create_index('ix_clause_policies_clause_type', 'clause_policies', ['clause_type'])
    op.create_index('idx_clause_policy_org_type', 'clause_policies', ['org_id', 'clause_type'])

    op.create_table(
        'generated_document_traces',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('document_id', sa.String(36), sa.ForeignKey('contracts.id', ondelete='CASCADE'), nullable=False),
        sa.Column('template_id', sa.String(36), sa.ForeignKey('templates.id', ondelete='SET NULL'), nullable=True),
        sa.Column('template_version', sa.Integer, nullable=True),
        sa.Column('variables_used', sa.JSON, nullable=True),
        sa.Column('clauses_used', sa.JSON, nullable=True),
        sa.Column('ai_session_id', sa.String(36), sa.ForeignKey('ai_sessions.id', ondelete='SET NULL'), nullable=True),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index('idx_gen_trace_doc', 'generated_document_traces', ['document_id'])

    # ═══════════════════════════════════════════════════
    # 10. integrations — интеграции
    # ═══════════════════════════════════════════════════

    op.create_table(
        'integration_configs',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('org_id', sa.String(36), sa.ForeignKey('organizations.id', ondelete='CASCADE'), nullable=True),
        sa.Column('integration_type', sa.String(30), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('config', sa.JSON, nullable=False),
        sa.Column('active', sa.Boolean, server_default='1'),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, server_default=sa.func.now()),
        sa.CheckConstraint(
            "integration_type IN ('webhook', 'api', 'edo', 'esign')",
            name='check_integration_type',
        ),
    )
    op.create_index('ix_integration_configs_org_id', 'integration_configs', ['org_id'])
    op.create_index('ix_integration_configs_active', 'integration_configs', ['active'])
    op.create_index('idx_integration_org_type', 'integration_configs', ['org_id', 'integration_type'])

    op.create_table(
        'webhook_deliveries',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('config_id', sa.String(36), sa.ForeignKey('integration_configs.id', ondelete='CASCADE'), nullable=False),
        sa.Column('event_type', sa.String(100), nullable=False),
        sa.Column('payload', sa.JSON, nullable=False),
        sa.Column('status', sa.String(20), nullable=False, server_default='pending'),
        sa.Column('response_code', sa.Integer, nullable=True),
        sa.Column('response_body', sa.Text, nullable=True),
        sa.Column('attempts', sa.Integer, server_default='0'),
        sa.Column('max_attempts', sa.Integer, server_default='3'),
        sa.Column('last_attempt_at', sa.DateTime, nullable=True),
        sa.Column('delivered_at', sa.DateTime, nullable=True),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        sa.CheckConstraint(
            "status IN ('pending', 'delivered', 'failed')",
            name='check_webhook_delivery_status',
        ),
    )
    op.create_index('ix_webhook_deliveries_config_id', 'webhook_deliveries', ['config_id'])
    op.create_index('ix_webhook_deliveries_event_type', 'webhook_deliveries', ['event_type'])
    op.create_index('idx_webhook_status_created', 'webhook_deliveries', ['status', 'created_at'])

    op.create_table(
        'domain_events',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('event_type', sa.String(100), nullable=False),
        sa.Column('entity_type', sa.String(50), nullable=False),
        sa.Column('entity_id', sa.String(36), nullable=False),
        sa.Column('payload', sa.JSON, nullable=True),
        sa.Column('emitted_by', sa.String(100), nullable=True),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index('ix_domain_events_event_type', 'domain_events', ['event_type'])
    op.create_index('ix_domain_events_entity_type', 'domain_events', ['entity_type'])
    op.create_index('ix_domain_events_entity_id', 'domain_events', ['entity_id'])
    op.create_index('idx_domain_event_entity', 'domain_events', ['entity_type', 'entity_id'])
    op.create_index('idx_domain_event_type_created', 'domain_events', ['event_type', 'created_at'])

    print("✅ 012: Core AI collaborative tables created (30 tables)")


def downgrade():
    """Drop all core AI collaborative tables in reverse dependency order."""

    # integrations
    op.drop_table('domain_events')
    op.drop_table('webhook_deliveries')
    op.drop_table('integration_configs')

    # templates
    op.drop_table('generated_document_traces')
    op.drop_table('clause_policies')
    op.drop_table('template_versions')

    # collaboration
    op.drop_table('comment_assignments')
    op.drop_table('mentions')
    op.drop_table('comment_threads')
    op.drop_table('comments')

    # workflow
    op.drop_table('workflow_events')
    op.drop_table('workflow_tasks')
    op.drop_table('workflow_executions')
    op.drop_table('workflow_definitions')

    # orchestrator
    op.drop_table('orchestrator_checkpoints')
    op.drop_table('plan_steps')
    op.drop_table('execution_plans')
    op.drop_table('orchestrator_runs')

    # ai_collaboration
    op.drop_table('ai_audit_records')
    op.drop_table('ai_action_approvals')
    op.drop_table('ai_actions')
    op.drop_table('ai_conversation_turns')
    op.drop_table('ai_sessions')

    # agents
    op.drop_table('agent_delegations')
    op.drop_table('agent_invocations')
    op.drop_table('agent_definitions')

    # tools
    op.drop_table('tool_invocations')
    op.drop_table('tool_definitions')

    # policies
    op.drop_table('action_permissions')
    op.drop_table('approval_rules')
    op.drop_table('policies')

    # identity_org
    op.drop_table('user_agent_policy_profiles')
    op.drop_table('tenant_contexts')
    op.drop_table('document_participations')
    op.drop_table('organization_memberships')
    op.drop_table('organization_units')
    op.drop_table('organizations')
