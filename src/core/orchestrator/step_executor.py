"""
Step Executor — выполнение отдельных шагов плана.

Каждый шаг: policy check → execute (tool/agent) → update status → audit.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from loguru import logger
from sqlalchemy.orm import Session

from src.core.base import AgentContext, AgentTask, ToolContext
from src.core.interfaces import IAuditLogger, IPolicyResolver
from src.core.tools.invoker import ToolInvocationService
from src.core.agents.delegator import AgentDelegationService
from .models import OrchestratorCheckpoint, OrchestratorRun, PlanStep


class StepExecutor:
    """Исполнитель шагов execution plan."""

    def __init__(
        self,
        db: Session,
        tool_invoker: ToolInvocationService,
        agent_delegator: AgentDelegationService,
        policy_resolver: IPolicyResolver,
        audit_logger: IAuditLogger,
    ) -> None:
        self.db = db
        self.tool_invoker = tool_invoker
        self.agent_delegator = agent_delegator
        self.policy_resolver = policy_resolver
        self.audit_logger = audit_logger

    async def execute_step(
        self,
        step: PlanStep,
        run: OrchestratorRun,
        user_id: str,
        previous_outputs: dict[int, dict[str, Any]],
    ) -> bool:
        """
        Выполнить один шаг плана.

        Args:
            step: Шаг для выполнения.
            run: Текущий run.
            user_id: ID инициатора.
            previous_outputs: Результаты предыдущих шагов {order: output_data}.

        Returns:
            True если шаг завершён успешно (или skipped).
        """
        step.status = "running"
        step.started_at = datetime.now(timezone.utc)
        self.db.flush()

        try:
            if step.step_type == "tool_call":
                success = await self._execute_tool_step(step, run, user_id, previous_outputs)
            elif step.step_type == "agent_delegation":
                success = await self._execute_agent_step(step, run, user_id, previous_outputs)
            elif step.step_type == "approval_checkpoint":
                success = await self._execute_checkpoint_step(step, run)
            elif step.step_type == "condition":
                success = self._evaluate_condition(step, previous_outputs)
            else:
                step.status = "failed"
                step.error = f"Неизвестный тип шага: {step.step_type}"
                success = False

        except Exception as exc:
            step.status = "failed"
            step.error = str(exc)
            step.completed_at = datetime.now(timezone.utc)
            self.db.flush()
            logger.error(f"Step {step.id} (order={step.order}) failed: {exc}")
            return False

        if success:
            if step.status == "running":  # Не перезаписываем если уже blocked/skipped
                step.status = "completed"
            step.completed_at = datetime.now(timezone.utc)
            run.completed_steps += 1
        else:
            if step.status == "running":
                step.status = "failed"
            step.completed_at = datetime.now(timezone.utc)
            run.failed_steps += 1

        self.db.flush()
        return success

    async def _execute_tool_step(
        self,
        step: PlanStep,
        run: OrchestratorRun,
        user_id: str,
        previous_outputs: dict[int, dict[str, Any]],
    ) -> bool:
        """Выполнить шаг tool_call."""
        if not step.tool_id:
            step.error = "tool_id не указан"
            return False

        # Подготовить input (с подстановкой $ref из предыдущих шагов)
        input_data = self._resolve_refs(step.input_data or {}, previous_outputs)

        context = ToolContext(
            user_id=user_id,
            document_id=run.document_id,
            session_id=run.session_id,
            run_id=run.id,
            step_id=step.id,
            invoker="orchestrator",
        )

        result = await self.tool_invoker.invoke(step.tool_id, input_data, context)
        step.output_data = result.data if result.success else {"error": result.error}
        return result.success

    async def _execute_agent_step(
        self,
        step: PlanStep,
        run: OrchestratorRun,
        user_id: str,
        previous_outputs: dict[int, dict[str, Any]],
    ) -> bool:
        """Выполнить шаг agent_delegation."""
        if not step.agent_id:
            step.error = "agent_id не указан"
            return False

        input_data = self._resolve_refs(step.input_data or {}, previous_outputs)

        task = AgentTask(
            task_type=step.name or "orchestrator_delegation",
            description=f"Шаг {step.order} плана: {step.name}",
            input_data=input_data,
        )

        context = AgentContext(
            user_id=user_id,
            document_id=run.document_id,
            session_id=run.session_id,
            run_id=run.id,
        )

        result = await self.agent_delegator.delegate(
            from_agent_id="orchestrator",
            to_agent_id=step.agent_id,
            task=task,
            context=context,
        )

        step.output_data = result.data if result.success else {"error": result.error}
        return result.success

    async def _execute_checkpoint_step(self, step: PlanStep, run: OrchestratorRun) -> bool:
        """Создать approval checkpoint — ставит run на паузу."""
        checkpoint = OrchestratorCheckpoint(
            run_id=run.id,
            step_id=step.id,
            checkpoint_type="approval",
            status="pending",
        )
        self.db.add(checkpoint)

        step.status = "blocked"
        run.status = "paused"
        self.db.flush()

        logger.info(f"Run {run.id} paused at checkpoint (step {step.order})")
        return True  # Шаг "успешен" — просто поставлен на паузу

    def _evaluate_condition(
        self,
        step: PlanStep,
        previous_outputs: dict[int, dict[str, Any]],
    ) -> bool:
        """Проверить условие — если False, следующий шаг будет skipped."""
        condition = step.condition
        if not condition:
            step.status = "completed"
            step.output_data = {"condition_met": True}
            return True

        field_ref = condition.get("field", "")
        op = condition.get("op", "==")
        expected = condition.get("value")

        # Резолвим ссылку: "step.3.output.risk_level"
        actual = self._resolve_field_ref(field_ref, previous_outputs)

        met = self._compare(actual, op, expected)
        step.output_data = {"condition_met": met, "actual": actual, "expected": expected}
        step.status = "completed"

        if not met:
            logger.info(f"Condition not met at step {step.order}: {field_ref} {op} {expected} (actual={actual})")

        return True  # Condition сам по себе не fail-ит

    def _resolve_refs(self, data: dict[str, Any], outputs: dict[int, dict[str, Any]]) -> dict[str, Any]:
        """Подставить $ref ссылки на output предыдущих шагов."""
        resolved: dict[str, Any] = {}
        for key, value in data.items():
            if isinstance(value, str) and value.startswith("$ref:"):
                ref_path = value[5:]  # "step.2.output.text"
                resolved[key] = self._resolve_field_ref(ref_path, outputs)
            else:
                resolved[key] = value
        return resolved

    def _resolve_field_ref(self, ref: str, outputs: dict[int, dict[str, Any]]) -> Any:
        """Резолвить ссылку вида 'step.N.output.field'."""
        parts = ref.split(".")
        if len(parts) < 3 or parts[0] != "step":
            return None
        try:
            step_order = int(parts[1])
        except ValueError:
            return None

        output = outputs.get(step_order, {})
        # Навигация по вложенным ключам: output.field1.field2
        for part in parts[2:]:
            if part == "output":
                continue
            if isinstance(output, dict):
                output = output.get(part)
            else:
                return None
        return output

    @staticmethod
    def _compare(actual: Any, op: str, expected: Any) -> bool:
        """Сравнить значения по оператору."""
        try:
            if op == "==":
                return actual == expected
            elif op == "!=":
                return actual != expected
            elif op == ">":
                return actual > expected
            elif op == ">=":
                return actual >= expected
            elif op == "<":
                return actual < expected
            elif op == "<=":
                return actual <= expected
            elif op == "in":
                return actual in (expected or [])
            elif op == "not_in":
                return actual not in (expected or [])
        except (TypeError, ValueError):
            return False
        return False
