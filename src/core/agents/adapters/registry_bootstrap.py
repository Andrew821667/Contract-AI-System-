"""
Registry Bootstrap — создание и регистрация адаптеров для существующих агентов.

Функция bootstrap_agent_registry():
- Создаёт экземпляры всех legacy-агентов (src/agents/)
- Оборачивает каждый в BaseAgentAdapter (IAgent protocol)
- Регистрирует в AgentRegistryService
"""

from __future__ import annotations

from typing import Any

from loguru import logger
from sqlalchemy.orm import Session

from .base_agent_adapter import BaseAgentAdapter

# ── Agent configurations ────────────────────────

AGENT_CONFIGS: list[dict[str, Any]] = [
    {
        "agent_id": "contract_analyzer",
        "specialization": "analysis",
        "task_types": ["contract_analysis", "risk_assessment", "compliance_check"],
        "allowed_tools": ["risk_scorer", "clause_extractor", "document_parser"],
        "autonomy_level": "copilot",
        "confidence_threshold": 0.8,
    },
    {
        "agent_id": "contract_generator",
        "specialization": "generation",
        "task_types": ["contract_generation", "template_completion"],
        "allowed_tools": ["contract_generator", "template_manager", "clause_library"],
        "autonomy_level": "copilot",
        "confidence_threshold": 0.8,
    },
    {
        "agent_id": "disagreement_analyzer",
        "specialization": "negotiation",
        "task_types": ["disagreement_analysis", "negotiation_support"],
        "allowed_tools": ["document_diff", "smart_composer"],
        "autonomy_level": "advisor",
        "confidence_threshold": 0.8,
    },
    {
        "agent_id": "changes_analyzer",
        "specialization": "comparison",
        "task_types": ["version_comparison", "change_detection"],
        "allowed_tools": ["document_diff"],
        "autonomy_level": "copilot",
        "confidence_threshold": 0.8,
    },
    {
        "agent_id": "onboarding_agent",
        "specialization": "onboarding",
        "task_types": ["document_intake", "classification"],
        "allowed_tools": ["document_parser", "complexity_scorer", "ocr_service"],
        "autonomy_level": "processor",
        "confidence_threshold": 0.8,
    },
    {
        "agent_id": "quick_export",
        "specialization": "export",
        "task_types": ["document_export"],
        "allowed_tools": [],
        "autonomy_level": "processor",
        "confidence_threshold": 0.8,
    },
    {
        "agent_id": "orchestrator",
        "specialization": "orchestration",
        "task_types": ["full_pipeline"],
        "allowed_tools": ["risk_scorer", "clause_extractor", "document_parser", "contract_generator"],
        "autonomy_level": "copilot",
        "confidence_threshold": 0.8,
    },
]


def _create_agent_instance(
    agent_id: str,
    db: Session,
    llm_gateway: Any,
) -> Any | None:
    """
    Create a legacy agent instance by agent_id.

    Returns None if the agent class cannot be imported (graceful degradation).
    """
    try:
        if agent_id == "contract_analyzer":
            from src.agents.contract_analyzer_agent import ContractAnalyzerAgent
            return ContractAnalyzerAgent(llm_gateway=llm_gateway, db_session=db)

        elif agent_id == "contract_generator":
            from src.agents.contract_generator_agent import ContractGeneratorAgent
            return ContractGeneratorAgent(llm_gateway=llm_gateway, db_session=db)

        elif agent_id == "disagreement_analyzer":
            from src.agents.disagreement_processor_agent import DisagreementProcessorAgent
            return DisagreementProcessorAgent(llm_gateway=llm_gateway, db_session=db)

        elif agent_id == "changes_analyzer":
            from src.agents.changes_analyzer_agent import ChangesAnalyzerAgent
            return ChangesAnalyzerAgent(llm_gateway=llm_gateway, db_session=db)

        elif agent_id == "onboarding_agent":
            from src.agents.onboarding_agent import OnboardingAgent
            return OnboardingAgent(llm_gateway=llm_gateway, db_session=db)

        elif agent_id == "quick_export":
            from src.agents.quick_export_agent import QuickExportAgent
            return QuickExportAgent(llm_gateway=llm_gateway, db_session=db)

        elif agent_id == "orchestrator":
            from src.agents.orchestrator_agent import OrchestratorAgent
            from src.services.review_queue_service import ReviewQueueService

            return OrchestratorAgent(
                llm_gateway=llm_gateway,
                db_session=db,
                review_queue_service=ReviewQueueService(db),
            )

        else:
            logger.warning(f"Unknown agent_id: {agent_id}")
            return None

    except ImportError as exc:
        logger.warning(f"Cannot import agent '{agent_id}': {exc}")
        return None
    except Exception as exc:
        logger.error(f"Failed to create agent '{agent_id}': {exc}")
        return None


def bootstrap_agent_registry(
    registry: Any,
    db: Session,
    llm_gateway: Any,
) -> list[str]:
    """
    Create all legacy agents, wrap in BaseAgentAdapter, register in registry.

    Args:
        registry: AgentRegistryService (IAgentRegistry protocol).
        db: SQLAlchemy Session for legacy agents.
        llm_gateway: LLMGateway instance for legacy agents.

    Returns:
        List of successfully registered agent_id strings.
    """
    registered: list[str] = []

    for config in AGENT_CONFIGS:
        agent_id = config["agent_id"]

        # Create legacy agent instance
        agent_instance = _create_agent_instance(agent_id, db, llm_gateway)
        if agent_instance is None:
            logger.warning(f"Skipping agent '{agent_id}' — could not create instance")
            continue

        # Wrap in adapter
        adapter = BaseAgentAdapter(
            agent=agent_instance,
            agent_id=config["agent_id"],
            specialization=config["specialization"],
            task_types=config["task_types"],
            allowed_tools=config["allowed_tools"],
            autonomy_level=config["autonomy_level"],
            confidence_threshold=config["confidence_threshold"],
        )

        # Register
        try:
            registry.register(adapter)
            registered.append(agent_id)
            logger.info(f"Bootstrapped agent: {agent_id} ({adapter.name})")
        except Exception as exc:
            logger.error(f"Failed to register agent '{agent_id}': {exc}")

    logger.info(
        f"Agent bootstrap complete: {len(registered)}/{len(AGENT_CONFIGS)} agents registered"
    )
    return registered
