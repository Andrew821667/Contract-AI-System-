"""
BaseAgentAdapter — обёртка существующих BaseAgent в IAgent protocol.

Паттерн Adapter: позволяет старым агентам (src/agents/) работать
через новый IAgent интерфейс без изменения их кода.

Добавляет audit logging и policy checking вокруг legacy execute().
"""

from __future__ import annotations

import time
from typing import Any, TYPE_CHECKING

from loguru import logger

from src.core.base import AgentContext, AgentResult, AgentTask

if TYPE_CHECKING:
    from src.core.ai_collaboration.audit_service import AIAuditService
    from src.core.policies.resolver import MultiLevelPolicyResolver


class BaseAgentAdapter:
    """
    Wraps existing BaseAgent instance as IAgent protocol.

    Преобразует:
    - AgentTask → state dict (для BaseAgent.execute)
    - old AgentResult → new AgentResult (core.base)
    - Properties → IAgent protocol properties
    - Adds audit logging + policy check around legacy execute()
    """

    def __init__(
        self,
        agent: Any,
        agent_id: str,
        specialization: str,
        task_types: list[str],
        allowed_tools: list[str] | None = None,
        autonomy_level: str = "copilot",
        confidence_threshold: float = 0.8,
        audit_logger: AIAuditService | None = None,
        policy_resolver: MultiLevelPolicyResolver | None = None,
    ) -> None:
        self._agent = agent
        self._agent_id = agent_id
        self._specialization = specialization
        self._task_types = list(task_types)
        self._allowed_tools = list(allowed_tools or [])
        self._autonomy_level = autonomy_level
        self._confidence_threshold = confidence_threshold
        self._audit_logger = audit_logger
        self._policy_resolver = policy_resolver

    # ── IAgent protocol properties ──────────────

    @property
    def agent_id(self) -> str:
        return self._agent_id

    @property
    def name(self) -> str:
        try:
            return self._agent.get_name()
        except AttributeError:
            return self._agent_id

    @property
    def specialization(self) -> str:
        return self._specialization

    @property
    def task_types(self) -> list[str]:
        return self._task_types

    @property
    def allowed_tools(self) -> list[str]:
        return self._allowed_tools

    @property
    def autonomy_level(self) -> str:
        return self._autonomy_level

    @property
    def confidence_threshold(self) -> float:
        return self._confidence_threshold

    # ── IAgent.execute ──────────────────────────

    async def execute(self, task: AgentTask, context: AgentContext) -> AgentResult:
        """
        Execute task by converting to legacy state dict and calling BaseAgent.execute().

        Adds policy check (if resolver available) and audit logging around execution.
        """
        action_name = f"agent:{self._agent_id}:{task.task_type}"

        # ── Policy check ────────────────────────────
        if self._policy_resolver:
            try:
                decision = await self._policy_resolver.resolve(
                    action=action_name,
                    user_id=context.user_id or "system",
                    organization_id=context.organization_id,
                    document_id=context.document_id,
                )
                if not decision.allowed:
                    logger.warning(
                        f"BaseAgentAdapter[{self._agent_id}] blocked by policy: {decision.reason}"
                    )
                    if self._audit_logger:
                        await self._audit_logger.log(
                            actor=f"agent:{self._agent_id}",
                            action=action_name,
                            target=context.document_id or task.task_id,
                            result="blocked",
                            policy_decision=decision,
                            session_id=context.session_id,
                        )
                    return AgentResult(
                        success=False,
                        data={},
                        error=f"Policy blocked: {decision.reason}",
                        duration_ms=0,
                    )
            except Exception as exc:
                logger.warning(f"Policy check failed (allowing): {exc}")

        # ── Build state dict from task + context ────
        state: dict[str, Any] = {
            "task_id": task.task_id,
            "task_type": task.task_type,
            "description": task.description,
            **task.input_data,
        }

        if context.document_id:
            state.setdefault("document_id", context.document_id)
        if context.user_id:
            state.setdefault("user_id", context.user_id)
        if context.organization_id:
            state.setdefault("organization_id", context.organization_id)
        if context.session_id:
            state.setdefault("session_id", context.session_id)

        if task.constraints:
            state.setdefault("constraints", task.constraints)

        logger.info(
            f"BaseAgentAdapter[{self._agent_id}] executing task "
            f"{task.task_type} (task_id={task.task_id})"
        )

        start_ms = time.monotonic_ns() // 1_000_000

        try:
            old_result = self._agent.execute(state)
            elapsed_ms = int(time.monotonic_ns() // 1_000_000 - start_ms)

            result = AgentResult(
                success=old_result.success,
                data=old_result.data if isinstance(old_result.data, dict) else {"raw": old_result.data},
                error=old_result.error,
                tools_used=[],
                delegated_to=[],
                confidence=old_result.metadata.get("confidence", 0.0) if old_result.metadata else 0.0,
                duration_ms=elapsed_ms,
                next_action=old_result.next_action,
                metadata=old_result.metadata if old_result.metadata else {},
            )

            # ── Audit log success ───────────────────
            if self._audit_logger:
                try:
                    await self._audit_logger.log(
                        actor=f"agent:{self._agent_id}",
                        action=action_name,
                        target=context.document_id or task.task_id,
                        payload={"duration_ms": elapsed_ms, "success": result.success},
                        result="success" if result.success else "failed",
                        session_id=context.session_id,
                    )
                except Exception:
                    pass  # audit failure must not break agent execution

            return result

        except Exception as exc:
            elapsed_ms = int(time.monotonic_ns() // 1_000_000 - start_ms)
            logger.error(
                f"BaseAgentAdapter[{self._agent_id}] failed: {exc}"
            )

            # ── Audit log failure ───────────────────
            if self._audit_logger:
                try:
                    await self._audit_logger.log(
                        actor=f"agent:{self._agent_id}",
                        action=action_name,
                        target=context.document_id or task.task_id,
                        payload={"error": str(exc), "duration_ms": elapsed_ms},
                        result="failed",
                        session_id=context.session_id,
                    )
                except Exception:
                    pass

            return AgentResult(
                success=False,
                data={},
                error=str(exc),
                duration_ms=elapsed_ms,
            )

    # ── Utility ─────────────────────────────────

    @property
    def wrapped_agent(self) -> Any:
        """Access the underlying BaseAgent instance."""
        return self._agent

    def __repr__(self) -> str:
        return (
            f"BaseAgentAdapter(id={self._agent_id!r}, "
            f"name={self.name!r}, spec={self._specialization!r})"
        )
