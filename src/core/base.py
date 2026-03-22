"""
Contract AI System — Base Types

Базовые value objects, enums и dataclasses для всего core-модуля.
Не зависит от SQLAlchemy — чистый Python + Pydantic.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


# ──────────────────────────────────────────────
# Enums
# ──────────────────────────────────────────────

class RiskLevel(str, Enum):
    """Уровень риска инструмента или действия."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class SyncMode(str, Enum):
    """Режим выполнения инструмента."""
    SYNC = "sync"
    ASYNC = "async"


class AutonomyLevel(str, Enum):
    """Уровень автономности агента (от пассивного до полностью автономного)."""
    ADVISOR = "advisor"          # Только советует, не действует
    COPILOT = "copilot"          # Действует с подтверждением человека
    PROCESSOR = "processor"      # Выполняет рутинные задачи автоматически
    AUTONOMOUS = "autonomous"    # Полная автономия в рамках policy


class PolicyLevel(str, Enum):
    """Уровень применения политики (каскад от платформы до документа)."""
    PLATFORM = "platform"
    TENANT = "tenant"
    ORGANIZATION = "organization"
    BRANCH = "branch"
    DOCUMENT = "document"
    USER = "user"


class ActionStatus(str, Enum):
    """Статус AI-действия."""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXECUTED = "executed"
    BLOCKED = "blocked"
    FAILED = "failed"


class ApprovalDecision(str, Enum):
    """Решение по approval checkpoint."""
    APPROVE = "approve"
    REJECT = "reject"
    EDIT_AND_APPROVE = "edit_and_approve"


class SessionStage(str, Enum):
    """Стадия AI-сессии в lifecycle документа."""
    INTAKE = "intake"
    CLASSIFICATION = "classification"
    ANALYSIS = "analysis"
    REVIEW = "review"
    NEGOTIATION = "negotiation"
    APPROVAL = "approval"
    GENERATION = "generation"
    EXPORT = "export"


class SessionStatus(str, Enum):
    """Статус AI-сессии."""
    ACTIVE = "active"
    PAUSED = "paused"
    CLOSED = "closed"


class PlanStepType(str, Enum):
    """Тип шага в execution plan (детерминированная оркестрация)."""
    TOOL_CALL = "tool_call"
    AGENT_DELEGATION = "agent_delegation"
    APPROVAL_CHECKPOINT = "approval_checkpoint"
    CONDITION = "condition"


class PlanStepStatus(str, Enum):
    """Статус шага плана."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    BLOCKED = "blocked"
    SKIPPED = "skipped"


class RunStatus(str, Enum):
    """Статус OrchestratorRun."""
    PLANNING = "planning"
    EXECUTING = "executing"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


# ──────────────────────────────────────────────
# Value Objects (Pydantic)
# ──────────────────────────────────────────────

class ToolContext(BaseModel):
    """Контекст вызова инструмента — кто вызывает, в рамках какой сессии."""
    user_id: str
    organization_id: str | None = None
    document_id: str | None = None
    session_id: str | None = None
    run_id: str | None = None
    step_id: str | None = None
    invoker: str = "user"  # user | agent:<agent_id> | orchestrator
    correlation_id: str = Field(default_factory=lambda: str(uuid4()))
    metadata: dict[str, Any] = Field(default_factory=dict)
    # metadata keys used by eligibility gating:
    #   "user_permissions": list[str] — permissions the caller holds
    #   "max_risk_level": str — maximum allowed tool risk level (low|medium|high|critical)


class ValidationResult(BaseModel):
    """Результат валидации входных данных инструмента."""
    valid: bool
    errors: list[str] = Field(default_factory=list)


class ToolResult(BaseModel):
    """Результат выполнения инструмента."""
    success: bool
    data: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None
    duration_ms: int = 0
    metadata: dict[str, Any] = Field(default_factory=dict)


class AgentTask(BaseModel):
    """Задача для специализированного агента."""
    task_id: str = Field(default_factory=lambda: str(uuid4()))
    task_type: str
    description: str
    input_data: dict[str, Any] = Field(default_factory=dict)
    constraints: dict[str, Any] = Field(default_factory=dict)
    priority: int = 0
    timeout_seconds: int = 300


class AgentContext(BaseModel):
    """Контекст выполнения агента."""
    user_id: str
    organization_id: str | None = None
    document_id: str | None = None
    session_id: str | None = None
    run_id: str | None = None
    allowed_tools: list[str] = Field(default_factory=list)
    policy_overrides: dict[str, Any] = Field(default_factory=dict)
    correlation_id: str = Field(default_factory=lambda: str(uuid4()))


class AgentResult(BaseModel):
    """Результат работы агента."""
    success: bool
    data: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None
    tools_used: list[str] = Field(default_factory=list)
    delegated_to: list[str] = Field(default_factory=list)
    confidence: float = 0.0
    duration_ms: int = 0
    next_action: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class PolicyDecision(BaseModel):
    """Результат проверки политики."""
    allowed: bool
    reason: str
    policy_id: str | None = None
    level: PolicyLevel | None = None
    requires_approval: bool = False
    approval_rule_id: str | None = None
    conditions: dict[str, Any] = Field(default_factory=dict)


class AIContext(BaseModel):
    """Собранный контекст для AI — документ, findings, комментарии, workflow."""
    document_id: str
    document_type: str | None = None
    document_text: str | None = None
    document_metadata: dict[str, Any] = Field(default_factory=dict)

    user_id: str
    user_role: str | None = None
    organization_id: str | None = None

    stage: str  # SessionStage value
    findings: list[dict[str, Any]] = Field(default_factory=list)
    comments: list[dict[str, Any]] = Field(default_factory=list)
    workflow_state: dict[str, Any] = Field(default_factory=dict)
    prior_actions: list[dict[str, Any]] = Field(default_factory=list)

    custom: dict[str, Any] = Field(default_factory=dict)


class LLMProfile(BaseModel):
    """Профиль LLM-модели, выбранный роутером."""
    provider: str       # openai | claude | deepseek | ...
    model: str          # gpt-5.4, claude-sonnet-4-6-20250227, deepseek-chat, ...
    temperature: float = 0.3
    max_tokens: int = 4096
    cost_per_1k_input: float = 0.0
    cost_per_1k_output: float = 0.0
    reason: str = ""    # Почему выбрана эта модель


class AuditEvent(BaseModel):
    """Событие аудита AI-действия."""
    event_id: str = Field(default_factory=lambda: str(uuid4()))
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    actor: str                # user_id | agent:<id> | orchestrator
    action: str               # explain_finding | suggest_clause | tool_call | ...
    target: str               # document_id | tool_id | ...
    result: str               # success | blocked | failed | approved | rejected
    payload: dict[str, Any] = Field(default_factory=dict)
    policy_decision: PolicyDecision | None = None
    session_id: str | None = None
    correlation_id: str | None = None
