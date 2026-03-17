"""
Domain Event Types — каталог всех событий системы.
"""
from __future__ import annotations
from dataclasses import dataclass


@dataclass(frozen=True)
class EventType:
    name: str
    entity_type: str
    description: str
    severity: str  # info, warning, critical


# ── Contract lifecycle ──
CONTRACT_UPLOADED = EventType("contract.uploaded", "contract", "Документ загружен", "info")
CONTRACT_PARSED = EventType("contract.parsed", "contract", "Документ распарсен", "info")
CONTRACT_ANALYZED = EventType("contract.analyzed", "contract", "Анализ завершён", "info")
CONTRACT_RISKS_FOUND = EventType("contract.risks_found", "contract", "Найдены риски", "warning")
CONTRACT_APPROVED = EventType("contract.approved", "contract", "Документ одобрен", "info")
CONTRACT_REJECTED = EventType("contract.rejected", "contract", "Документ отклонён", "warning")
CONTRACT_VERSION_ADDED = EventType("contract.version_added", "contract", "Добавлена новая версия", "info")

# ── AI & Agents ──
AI_SESSION_CREATED = EventType("ai.session.created", "ai_session", "AI сессия создана", "info")
AI_ACTION_EXECUTED = EventType("ai.action.executed", "ai_action", "AI действие выполнено", "info")
AI_ACTION_BLOCKED = EventType("ai.action.blocked", "ai_action", "AI действие заблокировано", "warning")
AGENT_TASK_COMPLETED = EventType("agent.task.completed", "agent_task", "Задача агента завершена", "info")
AGENT_TASK_FAILED = EventType("agent.task.failed", "agent_task", "Задача агента провалена", "warning")

# ── Workflow ──
WORKFLOW_STARTED = EventType("workflow.started", "workflow", "Процесс запущен", "info")
WORKFLOW_COMPLETED = EventType("workflow.completed", "workflow", "Процесс завершён", "info")
WORKFLOW_TASK_ASSIGNED = EventType("workflow.task.assigned", "workflow_task", "Задача назначена", "info")

# ── Negotiation ──
NEGOTIATION_STARTED = EventType("negotiation.started", "negotiation", "Переговоры начаты", "info")
NEGOTIATION_OBJECTIONS_GENERATED = EventType("negotiation.objections_generated", "negotiation", "Возражения сгенерированы", "info")
NEGOTIATION_POSITION_PREPARED = EventType("negotiation.position_prepared", "negotiation", "Позиция подготовлена", "info")

# ── Security ──
POLICY_VIOLATION = EventType("security.policy_violation", "policy", "Нарушение политики", "critical")
PERMISSION_DENIED = EventType("security.permission_denied", "access", "Доступ запрещён", "warning")

# Registry for lookup
ALL_EVENT_TYPES: dict[str, EventType] = {
    et.name: et for et in [
        CONTRACT_UPLOADED, CONTRACT_PARSED, CONTRACT_ANALYZED, CONTRACT_RISKS_FOUND,
        CONTRACT_APPROVED, CONTRACT_REJECTED, CONTRACT_VERSION_ADDED,
        AI_SESSION_CREATED, AI_ACTION_EXECUTED, AI_ACTION_BLOCKED,
        AGENT_TASK_COMPLETED, AGENT_TASK_FAILED,
        WORKFLOW_STARTED, WORKFLOW_COMPLETED, WORKFLOW_TASK_ASSIGNED,
        NEGOTIATION_STARTED, NEGOTIATION_OBJECTIONS_GENERATED, NEGOTIATION_POSITION_PREPARED,
        POLICY_VIOLATION, PERMISSION_DENIED,
    ]
}
