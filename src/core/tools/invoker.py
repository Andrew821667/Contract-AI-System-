"""
Tool Invocation Service — безопасный вызов инструментов.

Цепочка: validate → policy check → execute → audit log.
Ни один tool не вызывается напрямую — только через invoker.
"""

from __future__ import annotations

import time
from typing import Any

from loguru import logger
from sqlalchemy.orm import Session

from src.core.base import PolicyDecision, ToolContext, ToolResult
from src.core.interfaces import IAuditLogger, IPolicyResolver, ITool
from .models import ToolInvocation
from .registry import ToolRegistryService


class ToolInvocationService:
    """
    Безопасный invoker для инструментов.

    Гарантирует:
    1. Input валидация по schema
    2. Policy check перед выполнением
    3. Audit log после выполнения (успех или ошибка)
    4. Запись в ToolInvocation
    """

    def __init__(
        self,
        db: Session,
        registry: ToolRegistryService,
        policy_resolver: IPolicyResolver,
        audit_logger: IAuditLogger,
    ) -> None:
        self.db = db
        self.registry = registry
        self.policy_resolver = policy_resolver
        self.audit_logger = audit_logger

    async def invoke(
        self,
        tool_id: str,
        input_data: dict[str, Any],
        context: ToolContext,
    ) -> ToolResult:
        """
        Вызвать инструмент безопасно.

        Возвращает ToolResult (success=False если blocked/failed).
        """
        # 1. Найти tool
        tool = self.registry.get(tool_id)
        if tool is None:
            return ToolResult(success=False, error=f"Инструмент '{tool_id}' не найден в registry")

        # 2. Создать invocation record
        invocation = ToolInvocation(
            tool_id=tool_id,
            invoked_by=context.invoker,
            session_id=context.session_id,
            run_id=context.run_id,
            correlation_id=context.correlation_id,
            input_data=input_data,
            status="pending",
        )
        self.db.add(invocation)
        self.db.flush()

        # 3. Validate input
        validation = tool.validate_input(input_data)
        if not validation.valid:
            invocation.status = "failed"
            invocation.error = f"Ошибка валидации: {'; '.join(validation.errors)}"
            self.db.flush()
            return ToolResult(
                success=False,
                error=invocation.error,
            )

        # 4. Policy check
        action_name = f"tool.{tool_id}.execute"
        policy_decision: PolicyDecision = await self.policy_resolver.resolve(
            action=action_name,
            user_id=context.user_id,
            organization_id=context.organization_id,
            document_id=context.document_id,
            context={"risk_level": tool.risk_level},
        )

        if not policy_decision.allowed:
            invocation.status = "blocked"
            invocation.error = f"Заблокировано политикой: {policy_decision.reason}"
            self.db.flush()

            await self.audit_logger.log(
                actor=context.invoker,
                action=action_name,
                target=tool_id,
                payload={"input": input_data},
                result="blocked",
                policy_decision=policy_decision,
                session_id=context.session_id,
                correlation_id=context.correlation_id,
            )

            return ToolResult(success=False, error=invocation.error)

        if policy_decision.requires_approval:
            invocation.status = "blocked"
            invocation.error = "Требуется одобрение (approval checkpoint)"
            self.db.flush()

            await self.audit_logger.log(
                actor=context.invoker,
                action=action_name,
                target=tool_id,
                payload={"input": input_data},
                result="blocked",
                policy_decision=policy_decision,
                session_id=context.session_id,
                correlation_id=context.correlation_id,
            )

            return ToolResult(
                success=False,
                error=invocation.error,
                metadata={"requires_approval": True, "approval_rule_id": policy_decision.approval_rule_id},
            )

        # 5. Execute
        invocation.status = "running"
        self.db.flush()

        start = time.monotonic()
        try:
            result = await tool.execute(input_data, context)
            duration_ms = int((time.monotonic() - start) * 1000)

            invocation.status = "completed" if result.success else "failed"
            invocation.output_data = result.data
            invocation.error = result.error
            invocation.duration_ms = duration_ms
            result.duration_ms = duration_ms

        except Exception as exc:
            duration_ms = int((time.monotonic() - start) * 1000)
            invocation.status = "failed"
            invocation.error = str(exc)
            invocation.duration_ms = duration_ms
            self.db.flush()

            logger.error(f"Tool '{tool_id}' execution failed: {exc}")

            await self.audit_logger.log(
                actor=context.invoker,
                action=action_name,
                target=tool_id,
                payload={"input": input_data, "error": str(exc)},
                result="failed",
                policy_decision=policy_decision,
                session_id=context.session_id,
                correlation_id=context.correlation_id,
            )

            return ToolResult(success=False, error=str(exc), duration_ms=duration_ms)

        self.db.flush()

        # 6. Audit log
        await self.audit_logger.log(
            actor=context.invoker,
            action=action_name,
            target=tool_id,
            payload={"input": input_data, "output_keys": list(result.data.keys())},
            result="success" if result.success else "failed",
            policy_decision=policy_decision,
            session_id=context.session_id,
            correlation_id=context.correlation_id,
        )

        return result
