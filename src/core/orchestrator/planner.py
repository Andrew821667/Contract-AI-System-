"""
Execution Planner — детерминированное построение планов.

Паттерн Lobster: "Don't orchestrate with LLMs. Use them for creative work,
use code for plumbing."

Planner строит execution plan на основе:
- Цели (goal)
- Типа документа
- Workflow template
- Доступных tools и agents
"""

from __future__ import annotations

from typing import Any

from loguru import logger
from sqlalchemy.orm import Session

from src.core.tools.registry import ToolRegistryService
from src.core.agents.registry import AgentRegistryService
from .models import ExecutionPlan, PlanStep, OrchestratorRun


# ──────────────────────────────────────────────
# Шаблоны планов (детерминированные)
# ──────────────────────────────────────────────

_PLAN_TEMPLATES: dict[str, list[dict[str, Any]]] = {
    "prepare_for_review": [
        {"name": "Парсинг документа", "step_type": "tool_call", "tool_id": "document_parser"},
        {"name": "Извлечение клауз", "step_type": "tool_call", "tool_id": "clause_extractor"},
        {"name": "Оценка рисков", "step_type": "tool_call", "tool_id": "risk_scorer"},
        {
            "name": "Проверка рисков",
            "step_type": "condition",
            "condition": {"field": "step.3.output.risk_level", "op": "in", "value": ["HIGH", "CRITICAL"]},
        },
        {"name": "Одобрение при высоком риске", "step_type": "approval_checkpoint"},
        {"name": "Поиск прецедентов", "step_type": "tool_call", "tool_id": "rag_search"},
    ],
    "full_analysis": [
        {"name": "Парсинг документа", "step_type": "tool_call", "tool_id": "document_parser"},
        {"name": "Извлечение клауз", "step_type": "tool_call", "tool_id": "clause_extractor"},
        {"name": "Оценка рисков", "step_type": "tool_call", "tool_id": "risk_scorer"},
        {"name": "Поиск прецедентов", "step_type": "tool_call", "tool_id": "rag_search"},
        {"name": "Детальный анализ", "step_type": "agent_delegation", "agent_id": "review_agent"},
        {"name": "Финальное одобрение", "step_type": "approval_checkpoint"},
    ],
    "generate_contract": [
        {"name": "Поиск шаблонов", "step_type": "tool_call", "tool_id": "rag_search"},
        {"name": "Генерация договора", "step_type": "tool_call", "tool_id": "contract_generator"},
        {"name": "Анализ сгенерированного", "step_type": "tool_call", "tool_id": "risk_scorer"},
        {"name": "Одобрение", "step_type": "approval_checkpoint"},
    ],
    "compare_versions": [
        {"name": "Парсинг документа A", "step_type": "tool_call", "tool_id": "document_parser"},
        {"name": "Сравнение версий", "step_type": "tool_call", "tool_id": "document_diff"},
        {"name": "Анализ изменений", "step_type": "agent_delegation", "agent_id": "changes_analyzer"},
    ],
    "negotiation_support": [
        {"name": "Парсинг документа", "step_type": "tool_call", "tool_id": "document_parser"},
        {"name": "Извлечение клауз", "step_type": "tool_call", "tool_id": "clause_extractor"},
        {"name": "Оценка рисков", "step_type": "tool_call", "tool_id": "risk_scorer"},
        {"name": "Анализ разногласий", "step_type": "agent_delegation", "agent_id": "disagreement_analyzer"},
        {"name": "Подготовка позиции", "step_type": "tool_call", "tool_id": "smart_composer"},
        {"name": "Одобрение позиции", "step_type": "approval_checkpoint"},
    ],
    "quick_intake": [
        {"name": "Парсинг документа", "step_type": "tool_call", "tool_id": "document_parser"},
        {"name": "Оценка сложности", "step_type": "tool_call", "tool_id": "complexity_scorer"},
        {"name": "Классификация", "step_type": "agent_delegation", "agent_id": "onboarding_agent"},
    ],
    "compliance_check": [
        {"name": "Парсинг документа", "step_type": "tool_call", "tool_id": "document_parser"},
        {"name": "Извлечение клауз", "step_type": "tool_call", "tool_id": "clause_extractor"},
        {"name": "Проверка клауз по библиотеке", "step_type": "tool_call", "tool_id": "clause_library"},
        {"name": "Валидация", "step_type": "tool_call", "tool_id": "contract_validator"},
        {"name": "Оценка рисков", "step_type": "tool_call", "tool_id": "risk_scorer"},
        {
            "name": "Проверка критических рисков",
            "step_type": "condition",
            "condition": {"field": "step.5.output.risk_level", "op": "in", "value": ["HIGH", "CRITICAL"]},
        },
        {"name": "Одобрение при высоком риске", "step_type": "approval_checkpoint"},
    ],
}

# Маппинг ключевых слов цели → шаблон
_GOAL_KEYWORDS: dict[str, str] = {
    "согласован": "prepare_for_review",
    "анализ": "full_analysis",
    "проверк": "full_analysis",
    "ревью": "full_analysis",
    "генерац": "generate_contract",
    "создай": "generate_contract",
    "подготов": "prepare_for_review",
    "сравн": "compare_versions",
    "версии": "compare_versions",
    "изменен": "compare_versions",
    "перегов": "negotiation_support",
    "разноглас": "negotiation_support",
    "позици": "negotiation_support",
    "прием": "quick_intake",
    "приём": "quick_intake",
    "загрузк": "quick_intake",
    "классиф": "quick_intake",
    "комплаенс": "compliance_check",
    "соответств": "compliance_check",
    "валидац": "compliance_check",
}


class ExecutionPlannerService:
    """Детерминированный планировщик."""

    def __init__(
        self,
        db: Session,
        tool_registry: ToolRegistryService,
        agent_registry: AgentRegistryService,
    ) -> None:
        self.db = db
        self.tool_registry = tool_registry
        self.agent_registry = agent_registry

    def create_plan(self, run: OrchestratorRun) -> ExecutionPlan:
        """Создать execution plan для цели."""
        template_name = self._match_goal_to_template(run.goal)
        template_steps = _PLAN_TEMPLATES.get(template_name, _PLAN_TEMPLATES["full_analysis"])

        # Фильтруем шаги: убираем tool_call если tool не зарегистрирован
        valid_steps = self._filter_available_steps(template_steps)

        plan = ExecutionPlan(
            run_id=run.id,
            plan_definition={
                "template": template_name,
                "steps_count": len(valid_steps),
            },
            version=1,
        )
        self.db.add(plan)
        self.db.flush()

        # Создаём шаги
        for i, step_def in enumerate(valid_steps, start=1):
            step = PlanStep(
                plan_id=plan.id,
                order=i,
                name=step_def.get("name"),
                step_type=step_def["step_type"],
                tool_id=step_def.get("tool_id"),
                agent_id=step_def.get("agent_id"),
                input_data=step_def.get("input_data"),
                condition=step_def.get("condition"),
                status="pending",
            )
            self.db.add(step)

        run.total_steps = len(valid_steps)
        self.db.flush()

        logger.info(f"Plan created for run {run.id}: template={template_name}, steps={len(valid_steps)}")
        return plan

    def _match_goal_to_template(self, goal: str) -> str:
        """Определить шаблон плана по ключевым словам в цели."""
        goal_lower = goal.lower()
        for keyword, template_name in _GOAL_KEYWORDS.items():
            if keyword in goal_lower:
                return template_name
        return "full_analysis"  # default

    def _filter_available_steps(self, steps: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Убрать шаги с недоступными tools/agents."""
        result: list[dict[str, Any]] = []
        for step in steps:
            if step["step_type"] == "tool_call":
                tid = step.get("tool_id")
                if tid and self.tool_registry.get(tid) is None:
                    logger.warning(f"Tool '{tid}' не зарегистрирован — шаг '{step.get('name')}' пропущен")
                    continue
            elif step["step_type"] == "agent_delegation":
                aid = step.get("agent_id")
                if aid and self.agent_registry.get(aid) is None:
                    logger.warning(f"Agent '{aid}' не зарегистрирован — шаг '{step.get('name')}' пропущен")
                    continue
            result.append(step)
        return result
