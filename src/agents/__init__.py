"""
AI Agents for Contract AI System
"""
from .base_agent import BaseAgent, AgentResult
from .orchestrator_agent import OrchestratorAgent, WorkflowState

# Import full implementation or stub
try:
    from .onboarding_agent_full import OnboardingAgentFull as OnboardingAgent
except ImportError:
    from .agent_stubs import OnboardingAgent

# Stubs for remaining agents
from .agent_stubs import (
    ContractGeneratorAgent,
    ContractAnalyzerAgent,
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
