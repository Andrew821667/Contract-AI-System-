"""
Workflow Engine — запуск и продвижение маршрутов согласования.
"""

from __future__ import annotations

from datetime import datetime, timedelta
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
        task = self.db.query(WorkflowTask).filter(WorkflowTask.id == task_id).first()
        if not task:
            raise ValueError(f"Задача {task_id} не найдена")
        if task.status == "completed":
            raise ValueError(f"Задача {task_id} уже завершена")

        task.status = "completed"
        task.decision = decision
        task.comment = comment
        task.completed_at = datetime.utcnow()

        execution = task.execution
        self._emit_event(execution.id, "task_completed", {
            "task_id": task_id,
            "decision": decision,
            "user_id": user_id,
        })

        # Продвинуть workflow
        if decision == "reject":
            execution.status = "cancelled"
            execution.completed_at = datetime.utcnow()
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

    def _advance_workflow(self, execution: WorkflowExecution) -> None:
        """Продвинуть workflow на следующий шаг."""
        definition = execution.definition
        if not definition:
            return

        steps = definition.steps or []
        next_step_idx = execution.current_step + 1

        if next_step_idx >= len(steps):
            # Все шаги пройдены
            execution.status = "completed"
            execution.completed_at = datetime.utcnow()
            self._emit_event(execution.id, "workflow_completed", {})
        else:
            execution.current_step = next_step_idx
            self._create_task_for_step(execution, steps[next_step_idx], next_step_idx)
            self._emit_event(execution.id, "step_advanced", {"to_step": next_step_idx})

    def _create_task_for_step(
        self,
        execution: WorkflowExecution,
        step_def: dict[str, Any],
        step_order: int,
    ) -> WorkflowTask:
        """Создать задачу для шага."""
        sla_hours = step_def.get("sla_hours")
        sla_deadline = datetime.utcnow() + timedelta(hours=sla_hours) if sla_hours else None

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

    def _emit_event(self, execution_id: str, event_type: str, payload: dict[str, Any]) -> None:
        """Записать событие workflow."""
        event = WorkflowEvent(
            execution_id=execution_id,
            event_type=event_type,
            payload=payload,
            triggered_by="system",
        )
        self.db.add(event)
