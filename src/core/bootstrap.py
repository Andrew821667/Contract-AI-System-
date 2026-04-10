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
    # LLM gateway for tool services that need it
    try:
        from src.services.llm_gateway import LLMGateway
        _llm = LLMGateway()
    except Exception:
        _llm = None

    _register_tools(svc.tool_registry, db, _llm)

    # Wire WorkflowTool to already-initialized WorkflowEngineService
    wf_tool = svc.tool_registry.get("workflow_manager")
    if wf_tool and svc.workflow_engine:
        wf_tool._engine = svc.workflow_engine

    _bootstrap_agents(svc.agent_registry, db, _llm, svc.audit_service, svc.policy_resolver)

    logger.info(
        f"Core services bootstrapped: "
        f"{svc.tool_registry.count} tools, "
        f"{svc.agent_registry.count} agents"
    )

    return svc


def _register_tools(registry: ToolRegistryService, db: Session, llm_gateway=None) -> None:
    """Зарегистрировать tool-адаптеры с реальными сервисами (graceful — None если сервис недоступен)."""
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

    def _try_create(name: str, factory):
        """Create service instance, return None on failure."""
        try:
            return factory()
        except Exception as exc:
            logger.warning(f"Tool service '{name}' init failed (will be unavailable): {exc}")
            return None

    # ── No-dependency services ───────────────────
    from src.services.document_parser import DocumentParser
    from src.services.clause_extractor import ClauseExtractor
    from src.services.complexity_scorer import ComplexityScorer
    from src.services.document_diff_service import DocumentDiffService
    from src.services.validation_service import ValidationService

    parser = _try_create("DocumentParser", DocumentParser)
    clause_extractor = _try_create("ClauseExtractor", ClauseExtractor)
    complexity = _try_create("ComplexityScorer", ComplexityScorer)
    diff_svc = _try_create("DocumentDiffService", DocumentDiffService)
    validation = _try_create("ValidationService", ValidationService)

    # RiskScorer — module-level class, no __init__
    risk_scorer = None
    try:
        from src.services.risk_scorer import RiskScorer
        risk_scorer = RiskScorer()
    except Exception as exc:
        logger.warning(f"RiskScorer init failed: {exc}")

    # ── LLM-dependent services ───────────────────
    smart_composer = None
    recommendation = None
    if llm_gateway:
        try:
            from src.services.smart_composer import SmartContractComposer
            smart_composer = SmartContractComposer(llm_gateway=llm_gateway)
        except Exception as exc:
            logger.warning(f"SmartComposer init failed: {exc}")
        try:
            from src.services.recommendation_generator import RecommendationGenerator
            recommendation = RecommendationGenerator(llm_gateway=llm_gateway)
        except Exception as exc:
            logger.warning(f"RecommendationGenerator init failed: {exc}")

    # ── DB-dependent services ────────────────────
    analytics = _try_create("AnalyticsService", lambda: __import__(
        "src.services.analytics_service", fromlist=["AnalyticsService"]
    ).AnalyticsService(db_session=db))

    clause_library = _try_create("ClauseLibraryService", lambda: __import__(
        "src.services.clause_library_service", fromlist=["ClauseLibraryService"]
    ).ClauseLibraryService(db_session=db))

    knowledge_base = _try_create("KnowledgeBaseService", lambda: __import__(
        "src.services.knowledge_base_service", fromlist=["KnowledgeBaseService"]
    ).KnowledgeBaseService(db=db))

    template_manager = _try_create("TemplateManager", lambda: __import__(
        "src.services.template_manager", fromlist=["TemplateManager"]
    ).TemplateManager(db_session=db))

    # ── Optional external services ───────────────
    counterparty = _try_create("CounterpartyService", lambda: __import__(
        "src.services.counterparty_service", fromlist=["CounterpartyService"]
    ).CounterpartyService())

    ocr = _try_create("OCRService", lambda: __import__(
        "src.services.ocr_service", fromlist=["OCRService"]
    ).OCRService())

    contract_gen = _try_create("ContractGenerationService", lambda: __import__(
        "src.services.contract_generation_service", fromlist=["ContractGenerationService"]
    ).ContractGenerationService())

    # RAG — singleton from enhanced_rag
    rag = None
    try:
        from src.services.enhanced_rag import get_enhanced_rag
        rag = get_enhanced_rag()
    except Exception as exc:
        logger.warning(f"EnhancedRAG init failed: {exc}")

    tools = [
        DocumentParserTool(parser),
        RiskScorerTool(risk_scorer),
        ClauseExtractorTool(clause_extractor),
        ContractGeneratorTool(contract_gen),
        RAGSearchTool(rag),
        ComplexityScorerTool(complexity),
        CounterpartyTool(counterparty),
        DocumentDiffTool(diff_svc),
        SmartComposerTool(smart_composer),
        RecommendationTool(recommendation),
        ClauseLibraryTool(clause_library),
        KnowledgeBaseTool(knowledge_base),
        AnalyticsTool(analytics),
        TemplateManagerTool(template_manager),
        ValidationTool(validation),
        OCRTool(ocr),
        WorkflowTool(None),  # Uses core WorkflowEngineService, wired separately
    ]

    services = [
        parser, risk_scorer, clause_extractor, contract_gen, rag,
        complexity, counterparty, diff_svc, smart_composer, recommendation,
        clause_library, knowledge_base, analytics, template_manager,
        validation, ocr, None,  # WorkflowTool wired separately
    ]
    initialized = sum(1 for s in services if s is not None)
    logger.info(f"Tool services initialized: {initialized}/{len(tools)}")

    for tool in tools:
        registry.register(tool)


def _bootstrap_agents(
    registry: AgentRegistryService,
    db: Session,
    llm_gateway=None,
    audit_logger=None,
    policy_resolver=None,
) -> None:
    """Зарегистрировать агентов (graceful — не ломается при ошибке импорта)."""
    try:
        from src.core.agents.adapters.registry_bootstrap import bootstrap_agent_registry

        if llm_gateway is None:
            from src.services.llm_gateway import LLMGateway
            llm_gateway = LLMGateway()

        bootstrap_agent_registry(
            registry, db, llm_gateway,
            audit_logger=audit_logger,
            policy_resolver=policy_resolver,
        )
    except Exception as exc:
        logger.warning(f"Agent bootstrap skipped: {exc}")
