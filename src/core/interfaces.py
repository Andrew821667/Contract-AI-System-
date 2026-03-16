"""
Contract AI System — Core Interfaces (Protocols)

Формализованные контракты для всех компонентов AI-collaborative OS.
Используют typing.Protocol — структурная типизация (duck typing).

Паттерн: OpenClaw Skills (typed tools), Lobster (deterministic orchestration).
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from .base import (
    AgentContext,
    AgentResult,
    AgentTask,
    AIContext,
    AuditEvent,
    LLMProfile,
    PolicyDecision,
    ToolContext,
    ToolResult,
    ValidationResult,
)


# ──────────────────────────────────────────────
# ITool — формализованный инструмент
# ──────────────────────────────────────────────

@runtime_checkable
class ITool(Protocol):
    """
    Формализованный инструмент (паттерн OpenClaw Skills).

    Каждый tool:
    - Имеет строгую JSON Schema для input/output
    - Декларирует required permissions и policy tags
    - Проверяется policy engine перед выполнением
    - Логируется в audit trail после выполнения

    Существующие сервисы (document_parser, risk_scorer и т.д.)
    оборачиваются в ITool через адаптеры в src/core/tools/adapters/.
    """

    @property
    def tool_id(self) -> str:
        """Уникальный идентификатор (например, 'document_parser', 'risk_scorer')."""
        ...

    @property
    def name(self) -> str:
        """Человекочитаемое название."""
        ...

    @property
    def description(self) -> str:
        """Описание — что делает инструмент."""
        ...

    @property
    def input_schema(self) -> dict[str, Any]:
        """JSON Schema входных данных."""
        ...

    @property
    def output_schema(self) -> dict[str, Any]:
        """JSON Schema выходных данных."""
        ...

    @property
    def permissions(self) -> list[str]:
        """Требуемые разрешения (например, ['contract.read', 'analysis.execute'])."""
        ...

    @property
    def policy_tags(self) -> list[str]:
        """Теги для матчинга политик (например, ['analysis', 'risk'])."""
        ...

    @property
    def risk_level(self) -> str:
        """Уровень риска: low | medium | high | critical."""
        ...

    @property
    def sync_mode(self) -> str:
        """Режим выполнения: sync | async."""
        ...

    async def execute(self, input_data: dict[str, Any], context: ToolContext) -> ToolResult:
        """
        Выполнить инструмент.

        Args:
            input_data: Входные данные (валидированные по input_schema).
            context: Контекст вызова (кто, откуда, в рамках чего).

        Returns:
            ToolResult с данными или ошибкой.
        """
        ...

    def validate_input(self, input_data: dict[str, Any]) -> ValidationResult:
        """
        Валидация входных данных по input_schema.

        Вызывается перед execute(). Если невалидно — execute не вызывается.
        """
        ...


# ──────────────────────────────────────────────
# IAgent — специализированный агент
# ──────────────────────────────────────────────

@runtime_checkable
class IAgent(Protocol):
    """
    Специализированный агент.

    Агент:
    - Имеет специализацию (review, generation, negotiation, etc.)
    - Использует только разрешённые tools через registry
    - Работает в рамках autonomy level (advisor → autonomous)
    - Может делегировать подзадачи другим агентам

    Существующие агенты (contract_analyzer_agent, etc.)
    оборачиваются в IAgent через адаптеры в src/core/agents/.
    """

    @property
    def agent_id(self) -> str:
        """Уникальный идентификатор."""
        ...

    @property
    def name(self) -> str:
        """Человекочитаемое название."""
        ...

    @property
    def specialization(self) -> str:
        """Область специализации."""
        ...

    @property
    def allowed_tools(self) -> list[str]:
        """Список tool_id, доступных этому агенту."""
        ...

    @property
    def task_types(self) -> list[str]:
        """Типы задач, которые агент умеет решать."""
        ...

    @property
    def autonomy_level(self) -> str:
        """Уровень автономности: advisor | copilot | processor | autonomous."""
        ...

    @property
    def confidence_threshold(self) -> float:
        """Порог уверенности для авто-выполнения (0.0–1.0)."""
        ...

    async def execute(self, task: AgentTask, context: AgentContext) -> AgentResult:
        """
        Выполнить задачу агента.

        Args:
            task: Описание задачи с входными данными.
            context: Контекст (пользователь, документ, разрешённые tools).

        Returns:
            AgentResult с данными, confidence, использованными tools.
        """
        ...


# ──────────────────────────────────────────────
# IPolicyResolver — каскадный резолвер политик
# ──────────────────────────────────────────────

@runtime_checkable
class IPolicyResolver(Protocol):
    """
    Каскадный резолвер политик.

    Политики применяются каскадно:
    platform → tenant → organization → branch → document → user

    Более специфичный уровень переопределяет более общий.
    """

    async def resolve(
        self,
        action: str,
        user_id: str,
        organization_id: str | None = None,
        document_id: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> PolicyDecision:
        """
        Проверить, разрешено ли действие.

        Args:
            action: Идентификатор действия (например, 'tool.risk_scorer.execute').
            user_id: ID пользователя.
            organization_id: ID организации (если есть).
            document_id: ID документа (если релевантно).
            context: Дополнительный контекст (role, confidence, risk_level, etc.).

        Returns:
            PolicyDecision — allowed/denied + причина + требуется ли approval.
        """
        ...


# ──────────────────────────────────────────────
# IContextBuilder — сборщик контекста для AI
# ──────────────────────────────────────────────

@runtime_checkable
class IContextBuilder(Protocol):
    """
    Сборщик контекста для AI-сессии.

    Собирает всю релевантную информацию о документе,
    чтобы AI мог давать осмысленные ответы.
    """

    async def build(
        self,
        document_id: str,
        user_id: str,
        stage: str,
        include_findings: bool = True,
        include_comments: bool = True,
        include_workflow: bool = True,
        include_prior_actions: bool = True,
    ) -> AIContext:
        """
        Собрать контекст для AI.

        Args:
            document_id: ID документа.
            user_id: ID пользователя (для role-aware контекста).
            stage: Стадия lifecycle (intake, review, etc.).
            include_findings: Включить findings анализа.
            include_comments: Включить комментарии.
            include_workflow: Включить состояние workflow.
            include_prior_actions: Включить предыдущие AI-действия.

        Returns:
            AIContext — полный контекст для передачи в LLM.
        """
        ...


# ──────────────────────────────────────────────
# ILLMRouter — каскадный роутер моделей
# ──────────────────────────────────────────────

@runtime_checkable
class ILLMRouter(Protocol):
    """
    Каскадный роутер LLM-моделей.

    Выбирает модель на основе:
    - Типа задачи (analysis, generation, classification, etc.)
    - Чувствительности данных
    - Бюджета (cost)
    - Политики tenant/org
    """

    async def route(
        self,
        task_type: str,
        sensitivity: str = "normal",
        cost_budget: float | None = None,
        tenant_policy: dict[str, Any] | None = None,
    ) -> LLMProfile:
        """
        Выбрать LLM-модель для задачи.

        Args:
            task_type: Тип задачи (analysis, generation, explanation, etc.).
            sensitivity: Чувствительность данных (normal, confidential, restricted).
            cost_budget: Максимальный бюджет на запрос (USD).
            tenant_policy: Политика tenant (разрешённые провайдеры, preferred model, etc.).

        Returns:
            LLMProfile — выбранная модель с параметрами.
        """
        ...


# ──────────────────────────────────────────────
# IAuditLogger — аудит AI-действий
# ──────────────────────────────────────────────

@runtime_checkable
class IAuditLogger(Protocol):
    """
    Аудит всех AI-действий.

    Каждый вызов tool, каждое действие агента, каждое решение policy —
    записывается в audit trail. Принцип: ничего не происходит без лога.
    """

    async def log(
        self,
        actor: str,
        action: str,
        target: str,
        payload: dict[str, Any] | None = None,
        result: str = "success",
        policy_decision: PolicyDecision | None = None,
        session_id: str | None = None,
        correlation_id: str | None = None,
    ) -> AuditEvent:
        """
        Записать событие аудита.

        Args:
            actor: Кто выполнил (user_id | agent:<id> | orchestrator).
            action: Что сделал (tool_call, agent_delegation, approval, etc.).
            target: Над чем (document_id, tool_id, etc.).
            payload: Детали действия.
            result: Результат (success, blocked, failed, approved, rejected).
            policy_decision: Решение политики (если был policy check).
            session_id: ID AI-сессии.
            correlation_id: ID для связывания цепочки действий.

        Returns:
            AuditEvent — записанное событие.
        """
        ...


# ──────────────────────────────────────────────
# IToolRegistry — реестр инструментов
# ──────────────────────────────────────────────

@runtime_checkable
class IToolRegistry(Protocol):
    """
    Реестр зарегистрированных инструментов.

    Оркестратор и агенты получают tools ТОЛЬКО через registry.
    Принцип: никаких прямых вызовов сервисов.
    """

    def register(self, tool: ITool) -> None:
        """Зарегистрировать инструмент."""
        ...

    def get(self, tool_id: str) -> ITool | None:
        """Получить инструмент по ID."""
        ...

    def list_all(self) -> list[ITool]:
        """Список всех зарегистрированных инструментов."""
        ...

    def list_by_tags(self, tags: list[str]) -> list[ITool]:
        """Список инструментов по policy tags."""
        ...

    def list_by_risk_level(self, max_risk: str) -> list[ITool]:
        """Список инструментов с risk_level не выше указанного."""
        ...


# ──────────────────────────────────────────────
# IAgentRegistry — реестр агентов
# ──────────────────────────────────────────────

@runtime_checkable
class IAgentRegistry(Protocol):
    """
    Реестр специализированных агентов.

    Оркестратор делегирует задачи агентам ТОЛЬКО через registry.
    """

    def register(self, agent: IAgent) -> None:
        """Зарегистрировать агента."""
        ...

    def get(self, agent_id: str) -> IAgent | None:
        """Получить агента по ID."""
        ...

    def list_all(self) -> list[IAgent]:
        """Список всех зарегистрированных агентов."""
        ...

    def find_for_task(self, task_type: str) -> list[IAgent]:
        """Найти агентов, способных выполнить данный тип задачи."""
        ...
