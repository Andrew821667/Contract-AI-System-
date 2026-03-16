"""
Contract AI System — Core Module

AI-collaborative contract operating system: ядро архитектуры.
Содержит интерфейсы, базовые типы, и доменные модули.
"""

from .base import (
    # Value objects
    ToolContext,
    ToolResult,
    ValidationResult,
    AgentTask,
    AgentContext,
    AgentResult,
    PolicyDecision,
    AIContext,
    LLMProfile,
    AuditEvent,
    # Enums
    RiskLevel,
    SyncMode,
    AutonomyLevel,
    PolicyLevel,
    ActionStatus,
    ApprovalDecision,
    SessionStage,
    SessionStatus,
    PlanStepType,
    PlanStepStatus,
    RunStatus,
)

from .interfaces import (
    ITool,
    IAgent,
    IPolicyResolver,
    IContextBuilder,
    ILLMRouter,
    IAuditLogger,
    IToolRegistry,
    IAgentRegistry,
)

__all__ = [
    # Value objects
    "ToolContext",
    "ToolResult",
    "ValidationResult",
    "AgentTask",
    "AgentContext",
    "AgentResult",
    "PolicyDecision",
    "AIContext",
    "LLMProfile",
    "AuditEvent",
    # Enums
    "RiskLevel",
    "SyncMode",
    "AutonomyLevel",
    "PolicyLevel",
    "ActionStatus",
    "ApprovalDecision",
    "SessionStage",
    "SessionStatus",
    "PlanStepType",
    "PlanStepStatus",
    "RunStatus",
    # Interfaces
    "ITool",
    "IAgent",
    "IPolicyResolver",
    "IContextBuilder",
    "ILLMRouter",
    "IAuditLogger",
    "IToolRegistry",
    "IAgentRegistry",
]
