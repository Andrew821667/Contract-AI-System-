"""
Agent Delegation Service — делегация задач между агентами.

Агент может делегировать подзадачу другому агенту через delegation service.
Всё через registry + policy + audit.
"""

from __future__ import annotations

import time
from typing import Any

from loguru import logger
from sqlalchemy.orm import Session

from src.core.base import AgentContext, AgentResult, AgentTask
from src.core.interfaces import IAuditLogger, IPolicyResolver
from .models import AgentDelegation
from .registry import AgentRegistryService


class AgentDelegationService:
    """Безопасная делегация задач между агентами."""

    def __init__(
        self,
        db: Session,
        registry: AgentRegistryService,
        policy_resolver: IPolicyResolver,
        audit_logger: IAuditLogger,
    ) -> None:
        self.db = db
        self.registry = registry
        self.policy_resolver = policy_resolver
        self.audit_logger = audit_logger

    async def delegate(
        self,
        from_agent_id: str,
        to_agent_id: str,
        task: AgentTask,
        context: AgentContext,
    ) -> AgentResult:
        """Делегировать задачу от одного агента другому."""

        # Найти целевого агента
        target = self.registry.get(to_agent_id)
        if target is None:
            return AgentResult(
                success=False,
                error=f"Агент '{to_agent_id}' не найден в registry",
            )

        # Policy check
        action_name = f"agent.{to_agent_id}.delegate"
        decision = await self.policy_resolver.resolve(
            action=action_name,
            user_id=context.user_id,
            organization_id=context.organization_id,
            document_id=context.document_id,
        )

        if not decision.allowed:
            await self.audit_logger.log(
                actor=f"agent:{from_agent_id}",
                action=action_name,
                target=to_agent_id,
                result="blocked",
                policy_decision=decision,
                session_id=context.session_id,
                correlation_id=context.correlation_id,
            )
            return AgentResult(
                success=False,
                error=f"Делегация заблокирована: {decision.reason}",
            )

        # Создать delegation record
        delegation = AgentDelegation(
            from_agent_id=from_agent_id,
            to_agent_id=to_agent_id,
            run_id=context.run_id,
            task_data=task.model_dump(),
            status="running",
        )
        self.db.add(delegation)
        self.db.flush()

        # Выполнить
        start = time.monotonic()
        try:
            result = await target.execute(task, context)
            duration_ms = int((time.monotonic() - start) * 1000)

            delegation.status = "completed" if result.success else "failed"
            delegation.result_data = result.model_dump()
            delegation.completed_at = __import__("datetime").datetime.utcnow()
            result.duration_ms = duration_ms

        except Exception as exc:
            duration_ms = int((time.monotonic() - start) * 1000)
            delegation.status = "failed"
            delegation.result_data = {"error": str(exc)}
            self.db.flush()

            logger.error(f"Agent delegation {from_agent_id} → {to_agent_id} failed: {exc}")

            await self.audit_logger.log(
                actor=f"agent:{from_agent_id}",
                action=action_name,
                target=to_agent_id,
                payload={"error": str(exc)},
                result="failed",
                session_id=context.session_id,
                correlation_id=context.correlation_id,
            )

            return AgentResult(
                success=False,
                error=str(exc),
                duration_ms=duration_ms,
            )

        self.db.flush()

        # Audit
        await self.audit_logger.log(
            actor=f"agent:{from_agent_id}",
            action=action_name,
            target=to_agent_id,
            payload={"task_type": task.task_type},
            result="success" if result.success else "failed",
            session_id=context.session_id,
            correlation_id=context.correlation_id,
        )

        return result
