"""
Agent Orchestrator Service — основной сервис оркестрации.

Принимает high-level цель, строит план, выполняет шаги последовательно,
останавливается на checkpoints, продолжает после approval.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from loguru import logger
from sqlalchemy.orm import Session

from src.core.interfaces import IAuditLogger
from .models import ExecutionPlan, OrchestratorCheckpoint, OrchestratorRun, PlanStep
from .planner import ExecutionPlannerService
from .step_executor import StepExecutor


class AgentOrchestratorService:
    """Основной сервис оркестрации."""

    def __init__(
        self,
        db: Session,
        planner: ExecutionPlannerService,
        step_executor: StepExecutor,
        audit_logger: IAuditLogger,
    ) -> None:
        self.db = db
        self.planner = planner
        self.step_executor = step_executor
        self.audit_logger = audit_logger

    async def start_run(
        self,
        goal: str,
        user_id: str,
        document_id: str | None = None,
        session_id: str | None = None,
    ) -> OrchestratorRun:
        """Запустить оркестрацию по цели."""

        run = OrchestratorRun(
            goal=goal,
            initiated_by=user_id,
            document_id=document_id,
            session_id=session_id,
            status="planning",
        )
        self.db.add(run)
        self.db.flush()

        # Построить план
        plan = self.planner.create_plan(run)

        # Audit
        await self.audit_logger.log(
            actor=f"user:{user_id}",
            action="orchestrator.start",
            target=run.id,
            payload={"goal": goal, "document_id": document_id, "steps": run.total_steps},
            result="success",
            session_id=session_id,
        )

        # Начать выполнение
        run.status = "executing"
        self.db.flush()

        await self._execute_plan(run, plan, user_id)

        return run

    async def continue_run(self, run_id: str, user_id: str) -> OrchestratorRun | None:
        """Продолжить run после approval checkpoint."""
        run = self.db.query(OrchestratorRun).filter(OrchestratorRun.id == run_id).first()
        if not run:
            return None
        if run.status != "paused":
            logger.warning(f"Run {run_id} is not paused (status={run.status})")
            return run

        # Найти текущий план
        plan = (
            self.db.query(ExecutionPlan)
            .filter(ExecutionPlan.run_id == run_id)
            .order_by(ExecutionPlan.version.desc())
            .first()
        )
        if not plan:
            return run

        # Разблокировать checkpoint step
        blocked_steps = (
            self.db.query(PlanStep)
            .filter(PlanStep.plan_id == plan.id, PlanStep.status == "blocked")
            .all()
        )
        for step in blocked_steps:
            step.status = "completed"
            step.completed_at = datetime.now(timezone.utc)
            run.completed_steps += 1

        run.status = "executing"
        self.db.flush()

        await self.audit_logger.log(
            actor=f"user:{user_id}",
            action="orchestrator.continue",
            target=run.id,
            result="success",
        )

        # Продолжить выполнение
        await self._execute_plan(run, plan, user_id)
        return run

    async def cancel_run(self, run_id: str, user_id: str) -> OrchestratorRun | None:
        """Отменить run."""
        run = self.db.query(OrchestratorRun).filter(OrchestratorRun.id == run_id).first()
        if not run:
            return None

        run.status = "cancelled"
        run.completed_at = datetime.now(timezone.utc)
        self.db.flush()

        await self.audit_logger.log(
            actor=f"user:{user_id}",
            action="orchestrator.cancel",
            target=run.id,
            result="success",
        )

        return run

    async def get_run_status(self, run_id: str) -> dict[str, Any] | None:
        """Статус run с шагами."""
        run = self.db.query(OrchestratorRun).filter(OrchestratorRun.id == run_id).first()
        if not run:
            return None

        plan = (
            self.db.query(ExecutionPlan)
            .filter(ExecutionPlan.run_id == run_id)
            .order_by(ExecutionPlan.version.desc())
            .first()
        )

        steps: list[dict[str, Any]] = []
        if plan:
            for step in plan.steps:
                steps.append({
                    "order": step.order,
                    "name": step.name,
                    "type": step.step_type,
                    "status": step.status,
                    "tool_id": step.tool_id,
                    "agent_id": step.agent_id,
                })

        return {
            "id": run.id,
            "goal": run.goal,
            "status": run.status,
            "total_steps": run.total_steps,
            "completed_steps": run.completed_steps,
            "failed_steps": run.failed_steps,
            "steps": steps,
        }

    async def _execute_plan(self, run: OrchestratorRun, plan: ExecutionPlan, user_id: str) -> None:
        """Выполнить шаги плана последовательно."""
        # Собираем выходы предыдущих шагов
        previous_outputs: dict[int, dict[str, Any]] = {}

        for step in plan.steps:
            if step.status in ("completed", "skipped"):
                # Уже выполнен (при continue)
                if step.output_data:
                    previous_outputs[step.order] = step.output_data
                continue

            if step.status == "blocked":
                # Ждём approval
                break

            # Проверяем condition предыдущего шага
            if self._should_skip(step, plan.steps, previous_outputs):
                step.status = "skipped"
                step.completed_at = datetime.now(timezone.utc)
                self.db.flush()
                continue

            success = await self.step_executor.execute_step(step, run, user_id, previous_outputs)

            if step.output_data:
                previous_outputs[step.order] = step.output_data

            # Если шаг заблокирован (checkpoint) — прерываем
            if step.status == "blocked":
                break

            # Если шаг провалился — прерываем
            if not success and step.status == "failed":
                run.status = "failed"
                run.completed_at = datetime.now(timezone.utc)
                self.db.flush()

                await self.audit_logger.log(
                    actor="orchestrator",
                    action="orchestrator.failed",
                    target=run.id,
                    payload={"failed_step": step.order, "error": step.error},
                    result="failed",
                )
                return

        # Проверяем: все шаги выполнены?
        all_done = all(
            s.status in ("completed", "skipped")
            for s in plan.steps
        )
        if all_done:
            run.status = "completed"
            run.completed_at = datetime.now(timezone.utc)
            self.db.flush()

            await self.audit_logger.log(
                actor="orchestrator",
                action="orchestrator.completed",
                target=run.id,
                payload={"completed_steps": run.completed_steps},
                result="success",
            )

    def _should_skip(
        self,
        step: PlanStep,
        all_steps: list[PlanStep],
        previous_outputs: dict[int, dict[str, Any]],
    ) -> bool:
        """Проверить, нужно ли пропустить шаг (condition предыдущего шага = False)."""
        if step.order <= 1:
            return False

        prev_step = next((s for s in all_steps if s.order == step.order - 1), None)
        if prev_step and prev_step.step_type == "condition":
            output = prev_step.output_data or {}
            if not output.get("condition_met", True):
                return True

        return False
