# -*- coding: utf-8 -*-
"""
Application Bootstrap — инициализация всех core-сервисов.

Создаёт и связывает все сервисы Phase 0-7 для dependency injection.
Вызывается из lifespan в main.py или из тестов.
"""

from __future__ import annotations

from typing import Any

from loguru import logger
from sqlalchemy.orm import Session

from src.core.ai_collaboration.action_executor import AIActionExecutionService
from src.core.ai_collaboration.action_parser import AIActionParserService
from src.core.ai_collaboration.approval_service import AIApprovalService
from src.core.ai_collaboration.audit_service import AIAuditService
from src.core.ai_collaboration.context_builder import AIContextBuilderService
from src.core.ai_collaboration.llm_adapter import LLMRouterAdapter
from src.core.ai_collaboration.session_service import AICollaboratorService
from src.core.llm_cascade.routing_policy import LLMRoutingPolicyService
from src.core.llm_cascade.cascade_manager import CascadeManager
from src.core.llm_cascade.fallback import FallbackHandler
from src.core.agents.delegator import AgentDelegationService
from src.core.agents.registry import AgentRegistryService
from src.core.audit.service import AuditQueryService
from src.core.collaboration.service import CommentService
from src.core.integrations.event_bus import EventBusService
from src.core.integrations.webhook_service import WebhookService
from src.core.integrations.dispatcher import EventDispatcher
from src.core.negotiation.service import NegotiationService
from src.core.negotiation.version_service import VersionIntelligenceService
from src.core.orchestrator.orchestrator_service import AgentOrchestratorService
from src.core.orchestrator.planner import ExecutionPlannerService
from src.core.orchestrator.step_executor import StepExecutor
from src.core.policies.resolver import MultiLevelPolicyResolver
from src.core.templates.clause_policy_service import ClausePolicyService
from src.core.templates.governance_service import TemplateGovernanceService
from src.core.tools.invoker import ToolInvocationService
from src.core.tools.registry import ToolRegistryService
from src.core.workflow.engine import WorkflowEngineService

from src.core.enterprise.branch_mode import BranchModeService, BranchConfig
from src.core.enterprise.rbac import RBACService
from src.core.enterprise.tenant_isolation import TenantIsolationService
from src.core.enterprise.integrity import IntegrityService


class CoreServices:
    """Контейнер всех core-сервисов. Создаётся через bootstrap()."""

    def __init__(self) -> None:
        # Registries
        self.tool_registry: ToolRegistryService | None = None
        self.agent_registry: AgentRegistryService | None = None

        # Policies
        self.policy_resolver: MultiLevelPolicyResolver | None = None

        # Tools
        self.tool_invoker: ToolInvocationService | None = None

        # Agents
        self.agent_delegator: AgentDelegationService | None = None

        # AI Collaboration
        self.llm_router: LLMRouterAdapter | None = None
        self.context_builder: AIContextBuilderService | None = None
        self.action_parser: AIActionParserService | None = None
        self.action_executor: AIActionExecutionService | None = None
        self.approval_service: AIApprovalService | None = None
        self.audit_service: AIAuditService | None = None
        self.collaborator: AICollaboratorService | None = None

        # Orchestrator
        self.planner: ExecutionPlannerService | None = None
        self.step_executor: StepExecutor | None = None
        self.orchestrator: AgentOrchestratorService | None = None

        # Workflow
        self.workflow_engine: WorkflowEngineService | None = None

        # Collaboration
        self.comment_service: CommentService | None = None

        # Templates
        self.template_governance: TemplateGovernanceService | None = None
        self.clause_policy: ClausePolicyService | None = None

        # Integrations
        self.event_bus: EventBusService | None = None
        self.webhook_service: WebhookService | None = None
        self.event_dispatcher: EventDispatcher | None = None

        # Negotiation & Version Intelligence (Phase 9)
        self.negotiation_service: NegotiationService | None = None
        self.version_intelligence: VersionIntelligenceService | None = None

        # AI Action Policy
        self.action_policy = None  # AIActionPolicyService, set during bootstrap

        # Audit
        self.audit_query: AuditQueryService | None = None

        # LLM Cascade (Phase 11)
        self.llm_routing_policy: LLMRoutingPolicyService | None = None
        self.cascade_manager: CascadeManager | None = None
        self.fallback_handler: FallbackHandler | None = None

        # Enterprise Hardening (Phase 12)
        self.branch_mode: BranchModeService | None = None
        self.rbac: RBACService | None = None
        self.tenant_isolation: TenantIsolationService | None = None
        self.integrity: IntegrityService | None = None


def bootstrap(db: Session) -> CoreServices:
    """
    Инициализировать все core-сервисы с правильными зависимостями.

    Args:
        db: SQLAlchemy Session.

    Returns:
        CoreServices — контейнер с готовыми сервисами.
    """
    svc = CoreServices()

    # ── 1. Registries ────────────────────────────────────────────────
    svc.tool_registry = ToolRegistryService()
    svc.agent_registry = AgentRegistryService()

    # ── 2. Policies ──────────────────────────────────────────────────
    svc.policy_resolver = MultiLevelPolicyResolver(db)

    # ── 3. Audit ─────────────────────────────────────────────────────
    svc.audit_service = AIAuditService(db)
    svc.audit_query = AuditQueryService(db)

    # ── 4. Tools ─────────────────────────────────────────────────────
    svc.tool_invoker = ToolInvocationService(
        db=db,
        registry=svc.tool_registry,
        audit_logger=svc.audit_service,
        policy_resolver=svc.policy_resolver,
    )

    # ── 5. Agents ────────────────────────────────────────────────────
    svc.agent_delegator = AgentDelegationService(
        db=db,
        registry=svc.agent_registry,
        policy_resolver=svc.policy_resolver,
        audit_logger=svc.audit_service,
    )

    # ── 6. AI Collaboration ──────────────────────────────────────────
    svc.llm_router = LLMRouterAdapter()

    # ── 6a. LLM Cascade (Phase 11) ───────────────────────────────────
    svc.llm_routing_policy = LLMRoutingPolicyService(db)
    svc.fallback_handler = FallbackHandler()
    svc.cascade_manager = CascadeManager(
        routing_policy_service=svc.llm_routing_policy,
        fallback_handler=svc.fallback_handler,
    )

    from src.core.ai_collaboration.action_policy import AIActionPolicyService
    svc.action_policy = AIActionPolicyService(db)
    svc.action_policy.seed_defaults()  # заполнить БД дефолтными политиками

    svc.context_builder = AIContextBuilderService(db)
    svc.action_parser = AIActionParserService(db)
    svc.approval_service = AIApprovalService(db)
    svc.action_executor = AIActionExecutionService(
        db=db,
        tool_invoker=svc.tool_invoker,
        audit_logger=svc.audit_service,
        policy_resolver=svc.policy_resolver,
    )
    svc.collaborator = AICollaboratorService(
        db=db,
        llm_router=svc.llm_router,
        context_builder=svc.context_builder,
        action_parser=svc.action_parser,
        audit_logger=svc.audit_service,
    )

    # ── 7. Orchestrator ──────────────────────────────────────────────
    svc.planner = ExecutionPlannerService(
        db=db,
        tool_registry=svc.tool_registry,
        agent_registry=svc.agent_registry,
    )
    svc.step_executor = StepExecutor(
        db=db,
        tool_invoker=svc.tool_invoker,
        agent_delegator=svc.agent_delegator,
        policy_resolver=svc.policy_resolver,
        audit_logger=svc.audit_service,
    )
    svc.orchestrator = AgentOrchestratorService(
        db=db,
        planner=svc.planner,
        step_executor=svc.step_executor,
        audit_logger=svc.audit_service,
    )

    # ── 8. Workflow ──────────────────────────────────────────────────
    svc.workflow_engine = WorkflowEngineService(db)

    # ── 9. Collaboration ─────────────────────────────────────────────
    svc.comment_service = CommentService(db)

    # ── 10. Templates ────────────────────────────────────────────────
    svc.template_governance = TemplateGovernanceService(db)
    svc.clause_policy = ClausePolicyService(db)

    # ── 11. Negotiation & Version Intelligence (Phase 9) ─────────────
    svc.negotiation_service = NegotiationService(
        db=db,
        tool_invoker=svc.tool_invoker,
        audit_logger=svc.audit_service,
        policy_resolver=svc.policy_resolver,
    )
    svc.version_intelligence = VersionIntelligenceService(
        db=db,
        tool_invoker=svc.tool_invoker,
        audit_logger=svc.audit_service,
        policy_resolver=svc.policy_resolver,
    )

    # ── 12. Event Bus & Integrations ────────────────────────────────
    svc.event_bus = EventBusService(db)
    svc.webhook_service = WebhookService(db)
    svc.event_dispatcher = EventDispatcher(
        db=db,
        event_bus=svc.event_bus,
        webhook_service=svc.webhook_service,
    )
    svc.event_dispatcher.setup()

    # ── 13. Enterprise Hardening (Phase 12) ─────────────────────────
    svc.branch_mode = BranchModeService(db)
    svc.rbac = RBACService(db)
    svc.tenant_isolation = TenantIsolationService(db)
    svc.integrity = IntegrityService(db)

    # ── 14. Bootstrap tools & agents ─────────────────────────────────
    _register_tools(svc.tool_registry)
    _bootstrap_agents(svc.agent_registry, db, svc.audit_service, svc.policy_resolver)

    logger.info(
        f"Core services bootstrapped: "
        f"{svc.tool_registry.count} tools, "
        f"{svc.agent_registry.count} agents"
    )

    return svc


def _register_tools(registry: ToolRegistryService) -> None:
    """Зарегистрировать все tool-адаптеры (без инициализации сервисов — lazy)."""
    from src.core.tools.adapters import (
        AnalyticsTool,
        ClauseExtractorTool,
        ClauseLibraryTool,
        ComplexityScorerTool,
        ContractGeneratorTool,
        CounterpartyTool,
        DocumentDiffTool,
        DocumentParserTool,
        KnowledgeBaseTool,
        OCRTool,
        RAGSearchTool,
        RecommendationTool,
        RiskScorerTool,
        SmartComposerTool,
        TemplateManagerTool,
        ValidationTool,
        WorkflowTool,
    )

    # Регистрируем без реального сервиса (lazy init при первом вызове)
    tools = [
        DocumentParserTool(None),
        RiskScorerTool(None),
        ClauseExtractorTool(None),
        ContractGeneratorTool(None),
        RAGSearchTool(None),
        ComplexityScorerTool(None),
        CounterpartyTool(None),
        DocumentDiffTool(None),
        SmartComposerTool(None),
        RecommendationTool(None),
        ClauseLibraryTool(None),
        KnowledgeBaseTool(None),
        AnalyticsTool(None),
        TemplateManagerTool(None),
        ValidationTool(None),
        OCRTool(None),
        WorkflowTool(None),
    ]

    for tool in tools:
        registry.register(tool)


def _bootstrap_agents(
    registry: AgentRegistryService,
    db: Session,
    audit_logger=None,
    policy_resolver=None,
) -> None:
    """Зарегистрировать агентов (graceful — не ломается при ошибке импорта)."""
    try:
        from src.core.agents.adapters.registry_bootstrap import bootstrap_agent_registry
        from src.services.llm_gateway import LLMGateway

        llm = LLMGateway()
        bootstrap_agent_registry(
            registry, db, llm,
            audit_logger=audit_logger,
            policy_resolver=policy_resolver,
        )
    except Exception as exc:
        logger.warning(f"Agent bootstrap skipped: {exc}")
