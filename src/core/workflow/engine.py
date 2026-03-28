"""
Workflow Engine — запуск и продвижение маршрутов согласования.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from loguru import logger
from sqlalchemy.orm import Session

from .models import WorkflowDefinition, WorkflowEvent, WorkflowExecution, WorkflowTask


class WorkflowEngineService:
    """Движок маршрутов согласования."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def start_workflow(
        self,
        definition_id: str,
        document_id: str,
        initiated_by: str,
    ) -> WorkflowExecution:
        """Запустить workflow для документа."""
        definition = self.db.query(WorkflowDefinition).filter(
            WorkflowDefinition.id == definition_id
        ).first()
        if not definition:
            raise ValueError(f"Workflow definition {definition_id} не найден")

        execution = WorkflowExecution(
            definition_id=definition_id,
            document_id=document_id,
            current_step=0,
            status="active",
        )
        self.db.add(execution)
        self.db.flush()

        # Создать первую задачу
        steps = definition.steps or []
        if steps:
            self._create_task_for_step(execution, steps[0], 0)

        self._emit_event(execution.id, "workflow_started", {"initiated_by": initiated_by})
        self.db.flush()

        logger.info(f"Workflow started: {execution.id} (def={definition_id}, doc={document_id})")
        return execution

    def complete_task(
        self,
        task_id: str,
        user_id: str,
        decision: str,
        comment: str | None = None,
    ) -> WorkflowTask:
        """Завершить задачу и продвинуть workflow."""
        # with_for_update() — блокировка строки для предотвращения race condition
        task = (
            self.db.query(WorkflowTask)
            .filter(WorkflowTask.id == task_id)
            .with_for_update()
            .first()
        )
        if not task:
            raise ValueError(f"Задача {task_id} не найдена")
        if task.status == "completed":
            raise ValueError(f"Задача {task_id} уже завершена")

        task.status = "completed"
        task.decision = decision
        task.comment = comment
        task.completed_at = datetime.now(timezone.utc)

        execution = task.execution
        self._emit_event(execution.id, "task_completed", {
            "task_id": task_id,
            "decision": decision,
            "user_id": user_id,
        })

        # Продвинуть workflow
        if decision == "reject":
            execution.status = "cancelled"
            execution.completed_at = datetime.now(timezone.utc)
            self._emit_event(execution.id, "workflow_cancelled", {"reason": "rejected"})
        elif decision == "return_for_revision":
            # Вернуть на предыдущий шаг
            if execution.current_step > 0:
                execution.current_step -= 1
                definition = execution.definition
                if definition and definition.steps:
                    self._create_task_for_step(
                        execution,
                        definition.steps[execution.current_step],
                        execution.current_step,
                    )
            self._emit_event(execution.id, "step_returned", {"to_step": execution.current_step})
        else:
            # Advance to next step
            self._advance_workflow(execution)

        self.db.flush()
        return task

    def get_user_tasks(self, user_id: str, status: str = "pending") -> list[WorkflowTask]:
        """Задачи пользователя."""
        return (
            self.db.query(WorkflowTask)
            .filter(
                WorkflowTask.assignee_id == user_id,
                WorkflowTask.status == status,
            )
            .order_by(WorkflowTask.sla_deadline.asc().nullslast())
            .all()
        )

    def ai_advance_workflow(
        self,
        document_id: str,
        decision: str = "approve",
        comment: str | None = None,
        ai_session_id: str | None = None,
    ) -> WorkflowTask | None:
        """AI автоматически продвигает workflow для документа.

        Находит активный workflow и текущую pending-задачу,
        завершает её с указанным decision и продвигает workflow.

        Returns:
            Завершённая задача или None если нечего продвигать.
        """
        execution = (
            self.db.query(WorkflowExecution)
            .filter(
                WorkflowExecution.document_id == document_id,
                WorkflowExecution.status == "active",
            )
            .first()
        )
        if not execution:
            logger.info(f"AI advance: нет активного workflow для документа {document_id}")
            return None

        task = (
            self.db.query(WorkflowTask)
            .filter(
                WorkflowTask.execution_id == execution.id,
                WorkflowTask.status == "pending",
            )
            .with_for_update()
            .first()
        )
        if not task:
            logger.info(f"AI advance: нет pending-задач в workflow {execution.id}")
            return None

        task.status = "completed"
        task.decision = decision
        task.comment = comment or f"[AI] Автоматическое решение: {decision}"
        task.completed_at = datetime.now(timezone.utc)

        self._emit_event(execution.id, "task_completed", {
            "task_id": task.id,
            "decision": decision,
            "ai_session_id": ai_session_id,
        }, triggered_by="ai")

        if decision == "reject":
            execution.status = "cancelled"
            execution.completed_at = datetime.now(timezone.utc)
            self._emit_event(execution.id, "workflow_cancelled", {
                "reason": "rejected_by_ai",
            }, triggered_by="ai")
        elif decision == "return_for_revision":
            if execution.current_step > 0:
                execution.current_step -= 1
                definition = execution.definition
                if definition and definition.steps:
                    self._create_task_for_step(
                        execution,
                        definition.steps[execution.current_step],
                        execution.current_step,
                    )
            self._emit_event(execution.id, "step_returned", {
                "to_step": execution.current_step,
            }, triggered_by="ai")
        else:
            self._advance_workflow(execution, triggered_by="ai")

        self.db.flush()
        logger.info(
            f"AI advanced workflow {execution.id}: task={task.id} decision={decision}"
        )
        return task

    def ai_start_workflow(
        self,
        document_id: str,
        document_type: str,
        risk_level: str | None = None,
        org_id: str | None = None,
    ) -> WorkflowExecution | None:
        """AI автоматически запускает подходящий workflow для документа.

        Returns:
            Запущённый workflow или None если не найден подходящий definition.
        """
        definition = self.find_matching_workflow(document_type, risk_level, org_id)
        if not definition:
            logger.info(f"AI start: нет подходящего workflow для {document_type}")
            return None

        # Проверяем, нет ли уже активного workflow
        existing = (
            self.db.query(WorkflowExecution)
            .filter(
                WorkflowExecution.document_id == document_id,
                WorkflowExecution.status == "active",
            )
            .first()
        )
        if existing:
            logger.info(f"AI start: workflow уже запущен для документа {document_id}")
            return existing

        execution = WorkflowExecution(
            definition_id=definition.id,
            document_id=document_id,
            current_step=0,
            status="active",
        )
        self.db.add(execution)
        self.db.flush()

        steps = definition.steps or []
        if steps:
            self._create_task_for_step(execution, steps[0], 0)

        self._emit_event(execution.id, "workflow_started", {
            "initiated_by": "ai",
            "definition_name": definition.name,
        }, triggered_by="ai")
        self.db.flush()

        logger.info(f"AI started workflow {execution.id} (def={definition.id}, doc={document_id})")
        return execution

    def find_matching_workflow(
        self,
        document_type: str,
        risk_level: str | None = None,
        org_id: str | None = None,
    ) -> WorkflowDefinition | None:
        """Найти подходящий workflow definition."""
        query = self.db.query(WorkflowDefinition).filter(
            WorkflowDefinition.active.is_(True),
        )
        if document_type:
            query = query.filter(
                (WorkflowDefinition.document_type == document_type)
                | (WorkflowDefinition.document_type.is_(None))
            )
        if org_id:
            query = query.filter(
                (WorkflowDefinition.org_id == org_id)
                | (WorkflowDefinition.org_id.is_(None))
            )

        definitions = query.all()

        # Выбираем наиболее специфичный
        for defn in definitions:
            conditions = defn.conditions or {}
            if risk_level and "risk_level" in conditions:
                if risk_level not in conditions["risk_level"]:
                    continue
            return defn

        return definitions[0] if definitions else None

    def _advance_workflow(self, execution: WorkflowExecution, triggered_by: str = "system") -> None:
        """Продвинуть workflow на следующий шаг."""
        definition = execution.definition
        if not definition:
            return

        steps = definition.steps or []
        next_step_idx = execution.current_step + 1

        if next_step_idx >= len(steps):
            # Все шаги пройдены
            execution.status = "completed"
            execution.completed_at = datetime.now(timezone.utc)
            self._emit_event(execution.id, "workflow_completed", {}, triggered_by=triggered_by)
        else:
            execution.current_step = next_step_idx
            self._create_task_for_step(execution, steps[next_step_idx], next_step_idx)
            self._emit_event(execution.id, "step_advanced", {"to_step": next_step_idx}, triggered_by=triggered_by)

    def _create_task_for_step(
        self,
        execution: WorkflowExecution,
        step_def: dict[str, Any],
        step_order: int,
    ) -> WorkflowTask:
        """Создать задачу для шага."""
        sla_hours = step_def.get("sla_hours")
        sla_deadline = datetime.now(timezone.utc) + timedelta(hours=sla_hours) if sla_hours else None

        task = WorkflowTask(
            execution_id=execution.id,
            step_name=step_def.get("name", f"Шаг {step_order + 1}"),
            step_order=step_order,
            task_type=step_def.get("task_type", "review"),
            status="pending",
            sla_deadline=sla_deadline,
        )
        self.db.add(task)
        self.db.flush()

        self._emit_event(execution.id, "task_created", {
            "task_id": task.id,
            "step_name": task.step_name,
            "assignee_role": step_def.get("assignee_role"),
        })

        return task

    def _emit_event(self, execution_id: str, event_type: str, payload: dict[str, Any], triggered_by: str = "system") -> None:
        """Записать событие workflow."""
        event = WorkflowEvent(
            execution_id=execution_id,
            event_type=event_type,
            payload=payload,
            triggered_by=triggered_by,
        )
        self.db.add(event)
