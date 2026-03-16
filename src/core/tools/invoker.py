"""
Tool Invocation Service — безопасный вызов инструментов.

Цепочка: lookup → validate → eligibility gate → execute → record → audit.
Ни один tool не вызывается напрямую — только через invoker.
"""

from __future__ import annotations

import time
from typing import Any

from loguru import logger
from sqlalchemy.orm import Session

from src.core.base import PolicyDecision, ToolContext, ToolResult
from src.core.interfaces import IAuditLogger, ITool
from src.core.policies.resolver import MultiLevelPolicyResolver
from .models import ToolInvocation
from .registry import ToolRegistryService

# Порядок уровней риска (для threshold-проверки)
_RISK_ORDER: dict[str, int] = {"low": 0, "medium": 1, "high": 2, "critical": 3}


class ToolInvocationService:
    """
    Безопасный invoker для инструментов.

    Pipeline:
    1. Lookup tool из registry
    2. Validate input по schema
    3. Eligibility gating — permissions, policy, risk threshold
    4. Execute tool
    5. Record ToolInvocation в DB
    6. Audit log
    """

    def __init__(
        self,
        db: Session,
        registry: ToolRegistryService,
        audit_logger: IAuditLogger,
        policy_resolver: MultiLevelPolicyResolver | None = None,
    ) -> None:
        self.db = db
        self.registry = registry
        self.audit_logger = audit_logger
        self.policy_resolver = policy_resolver

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

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
        action_name = f"tool.{tool_id}.execute"

        # ── 1. Lookup tool ──────────────────────────────────────────
        tool = self.registry.get(tool_id)
        if tool is None:
            return ToolResult(success=False, error=f"Инструмент '{tool_id}' не найден в registry")

        # ── 2. Validate input ───────────────────────────────────────
        validation = tool.validate_input(input_data)
        if not validation.valid:
            error_msg = f"Ошибка валидации: {'; '.join(validation.errors)}"
            # Record failed invocation
            self._record_invocation(
                tool_id=tool_id,
                context=context,
                input_data=input_data,
                status="failed",
                error=error_msg,
            )
            return ToolResult(success=False, error=error_msg)

        # ── 3. Eligibility gating ───────────────────────────────────
        eligibility_error, policy_decision = await self._check_eligibility(tool, input_data, context)
        if eligibility_error is not None:
            return eligibility_error

        # ── 4. Execute ──────────────────────────────────────────────
        start = time.monotonic()
        try:
            result = await tool.execute(input_data, context)
            duration_ms = int((time.monotonic() - start) * 1000)
            result.duration_ms = duration_ms

        except Exception as exc:
            duration_ms = int((time.monotonic() - start) * 1000)
            logger.error(f"Tool '{tool_id}' execution failed: {exc}")

            # ── 5. Record failed invocation ─────────────────────────
            self._record_invocation(
                tool_id=tool_id,
                context=context,
                input_data=input_data,
                status="failed",
                error=str(exc),
                duration_ms=duration_ms,
            )

            # ── 6. Audit failure ────────────────────────────────────
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

        duration_ms = result.duration_ms

        # ── 5. Record invocation ────────────────────────────────────
        invocation = ToolInvocation(
            tool_id=tool_id,
            session_id=context.session_id,
            invoked_by=context.user_id,
            input_data=input_data,
            output_data=result.data if result.success else {"error": result.error},
            status="completed" if result.success else "failed",
            duration_ms=result.duration_ms,
        )
        self.db.add(invocation)
        self.db.flush()

        # ── 6. Audit log ───────────────────────────────────────────
        await self.audit_logger.log(
            actor=context.invoker,
            action=action_name,
            target=tool_id,
            payload={"input": input_data, "output_keys": list(result.data.keys()) if result.data else []},
            result="success" if result.success else "failed",
            policy_decision=policy_decision,
            session_id=context.session_id,
            correlation_id=context.correlation_id,
        )

        return result

    # ------------------------------------------------------------------
    # Eligibility gating (private)
    # ------------------------------------------------------------------

    async def _check_eligibility(
        self,
        tool: ITool,
        input_data: dict[str, Any],
        context: ToolContext,
    ) -> tuple[ToolResult | None, PolicyDecision | None]:
        """
        Проверить, имеет ли пользователь право вызвать этот инструмент.

        Три проверки:
        a) Permissions — у пользователя есть нужные разрешения (tool.permissions)
        b) Policy — policy_resolver разрешает вызов (если resolver доступен)
        c) Risk threshold — risk_level инструмента не выше допустимого для пользователя

        Возвращает (ToolResult с ошибкой, policy_decision) если заблокировано,
        (None, policy_decision) если всё ОК.
        """
        tool_id = tool.tool_id
        action_name = f"tool.{tool_id}.execute"
        policy_decision: PolicyDecision | None = None

        # ── a) Permissions check ────────────────────────────────────
        user_permissions: list[str] = context.metadata.get("user_permissions", [])

        required_permissions = tool.permissions
        if required_permissions and user_permissions:
            missing = [p for p in required_permissions if p not in user_permissions]
            if missing:
                error_msg = f"Недостаточно прав: отсутствуют [{', '.join(missing)}]"
                self._record_invocation(
                    tool_id=tool_id,
                    context=context,
                    input_data=input_data,
                    status="blocked",
                    error=error_msg,
                )
                await self.audit_logger.log(
                    actor=context.invoker,
                    action=action_name,
                    target=tool_id,
                    payload={"input": input_data, "missing_permissions": missing},
                    result="blocked",
                    session_id=context.session_id,
                    correlation_id=context.correlation_id,
                )
                return ToolResult(success=False, error=error_msg), None

        # ── b) Policy check (если resolver доступен) ────────────────
        if self.policy_resolver is not None:
            policy_decision = await self._resolve_policy(tool, context)

            if not policy_decision.allowed:
                error_msg = f"Заблокировано политикой: {policy_decision.reason}"
                self._record_invocation(
                    tool_id=tool_id,
                    context=context,
                    input_data=input_data,
                    status="blocked",
                    error=error_msg,
                )
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
                return ToolResult(success=False, error=error_msg), policy_decision

            if policy_decision.requires_approval:
                error_msg = "Требуется одобрение (approval checkpoint)"
                self._record_invocation(
                    tool_id=tool_id,
                    context=context,
                    input_data=input_data,
                    status="blocked",
                    error=error_msg,
                )
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
                    error=error_msg,
                    metadata={"requires_approval": True, "approval_rule_id": policy_decision.approval_rule_id},
                ), policy_decision

        # ── c) Risk threshold check ────────────────────────────────
        allowed_risk: str | None = context.metadata.get("max_risk_level")

        if allowed_risk is not None:
            tool_risk_idx = _RISK_ORDER.get(tool.risk_level, 0)
            allowed_risk_idx = _RISK_ORDER.get(allowed_risk, 3)
            if tool_risk_idx > allowed_risk_idx:
                error_msg = (
                    f"Уровень риска инструмента '{tool.risk_level}' превышает "
                    f"допустимый '{allowed_risk}'"
                )
                self._record_invocation(
                    tool_id=tool_id,
                    context=context,
                    input_data=input_data,
                    status="blocked",
                    error=error_msg,
                )
                await self.audit_logger.log(
                    actor=context.invoker,
                    action=action_name,
                    target=tool_id,
                    payload={
                        "input": input_data,
                        "tool_risk": tool.risk_level,
                        "allowed_risk": allowed_risk,
                    },
                    result="blocked",
                    session_id=context.session_id,
                    correlation_id=context.correlation_id,
                )
                return ToolResult(success=False, error=error_msg), policy_decision

        return None, policy_decision  # Всё ОК — инструмент разрешён

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    async def _resolve_policy(self, tool: ITool, context: ToolContext) -> PolicyDecision | None:
        """Запросить решение policy resolver (если доступен)."""
        if self.policy_resolver is None:
            return None
        action_name = f"tool.{tool.tool_id}.execute"
        return await self.policy_resolver.resolve(
            action=action_name,
            user_id=context.user_id,
            organization_id=context.organization_id,
            document_id=context.document_id,
            context={"risk_level": tool.risk_level},
        )

    def _record_invocation(
        self,
        tool_id: str,
        context: ToolContext,
        input_data: dict[str, Any],
        status: str,
        error: str | None = None,
        duration_ms: int = 0,
        output_data: dict[str, Any] | None = None,
    ) -> ToolInvocation:
        """Записать ToolInvocation в DB."""
        invocation = ToolInvocation(
            tool_id=tool_id,
            session_id=context.session_id,
            invoked_by=context.user_id,
            input_data=input_data,
            output_data=output_data or ({"error": error} if error else None),
            status=status,
            duration_ms=duration_ms,
        )
        self.db.add(invocation)
        self.db.flush()
        return invocation
