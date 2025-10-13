"""
AI Agents for Contract AI System
"""
from .base_agent import BaseAgent, AgentResult
from .orchestrator_agent import OrchestratorAgent, WorkflowState

# Import full implementations or stubs
try:
    from .onboarding_agent_full import OnboardingAgentFull as OnboardingAgent
except ImportError:
    from .agent_stubs import OnboardingAgent

try:
    from .contract_generator_agent import ContractGeneratorAgent
except ImportError:
    from .agent_stubs import ContractGeneratorAgent

try:
    from .contract_analyzer_agent import ContractAnalyzerAgent
except ImportError:
    from .agent_stubs import ContractAnalyzerAgent

# Stubs for remaining agents
from .agent_stubs import (
    DisagreementProcessorAgent,
    ChangesAnalyzerAgent,
    QuickExportAgent
)

__all__ = [
    "BaseAgent",
    "AgentResult",
    "OrchestratorAgent",
    "WorkflowState",
    "OnboardingAgent",
    "ContractGeneratorAgent",
    "ContractAnalyzerAgent",
    "DisagreementProcessorAgent",
    "ChangesAnalyzerAgent",
    "QuickExportAgent"
]
