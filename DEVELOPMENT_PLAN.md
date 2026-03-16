# Contract AI System — План разработки

**Версия:** 1.0
**Дата:** 2026-03-16
**Концепция:** AI-collaborative contract operating system
**Референс:** OpenClaw (agentic patterns), Lobster (deterministic orchestration)

---

## Архитектурная формула

```
hierarchical LLM cascade
+ AI collaborator layer
+ agent orchestrator layer
+ specialized agents
+ controlled tool ecosystem
+ user/org-aware policy system
+ standalone/branch-ready contract domain
```

---

## Phase 0: Architecture & Contracts Foundation

### 0.1. Bounded Context Map

```
┌─────────────────────────────────────────────────────────┐
│                    PLATFORM LAYER                        │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────────┐ │
│  │  Identity /   │ │   Policy     │ │    Audit /       │ │
│  │  Organization │ │   Engine     │ │    Compliance    │ │
│  └──────┬───────┘ └──────┬───────┘ └──────┬───────────┘ │
├─────────┼────────────────┼────────────────┼─────────────┤
│                    AI LAYER                               │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────────┐ │
│  │     AI        │ │   Agent      │ │  Specialized     │ │
│  │ Collaboration │ │ Orchestrator │ │  Agents          │ │
│  └──────┬───────┘ └──────┬───────┘ └──────┬───────────┘ │
│         │                │                 │             │
│  ┌──────┴───────┐ ┌──────┴───────┐ ┌──────┴───────────┐ │
│  │  LLM Routing │ │ Tool Registry│ │ Agent Registry   │ │
│  └──────────────┘ └──────────────┘ └──────────────────┘ │
├──────────────────────────────────────────────────────────┤
│                   DOMAIN LAYER                           │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌────────────┐ │
│  │ Contract │ │ Workflow │ │ Collab-  │ │ Template   │ │
│  │ Domain   │ │ Engine   │ │ oration  │ │ Governance │ │
│  └──────────┘ └──────────┘ └──────────┘ └────────────┘ │
├──────────────────────────────────────────────────────────┤
│                 INTEGRATION LAYER                        │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────────┐ │
│  │   Events /   │ │  Webhooks /  │ │   External       │ │
│  │   Bus        │ │  Adapters    │ │   APIs           │ │
│  └──────────────┘ └──────────────┘ └──────────────────┘ │
└──────────────────────────────────────────────────────────┘
```

### 0.2. Ключевые интерфейсы

```python
# src/core/interfaces.py

class ITool(Protocol):
    """Формализованный инструмент (паттерн OpenClaw Skills)"""
    tool_id: str
    name: str
    description: str
    input_schema: dict        # JSON Schema
    output_schema: dict       # JSON Schema
    permissions: list[str]    # required permissions
    policy_tags: list[str]    # for policy matching
    risk_level: str           # low | medium | high | critical
    sync_mode: str            # sync | async

    async def execute(self, input: dict, context: ToolContext) -> ToolResult: ...
    def validate_input(self, input: dict) -> ValidationResult: ...


class IAgent(Protocol):
    """Специализированный агент"""
    agent_id: str
    name: str
    specialization: str
    allowed_tools: list[str]
    task_types: list[str]
    autonomy_level: str       # advisor | copilot | processor | autonomous
    confidence_threshold: float

    async def execute(self, task: AgentTask, context: AgentContext) -> AgentResult: ...


class IPolicyResolver(Protocol):
    """Каскадный резолвер политик"""
    async def resolve(self,
        action: str,
        user: User,
        organization: Organization | None,
        document: Document | None,
        context: dict
    ) -> PolicyDecision: ...


class IContextBuilder(Protocol):
    """Сборщик контекста для AI"""
    async def build(self,
        document: Document,
        user: User,
        stage: str,
        include_findings: bool = True,
        include_comments: bool = True,
        include_workflow: bool = True,
        include_prior_actions: bool = True,
    ) -> AIContext: ...


class ILLMRouter(Protocol):
    """Каскадный роутер моделей"""
    async def route(self,
        task_type: str,
        sensitivity: str,
        cost_budget: float | None,
        tenant_policy: dict,
    ) -> LLMProfile: ...


class IAuditLogger(Protocol):
    """Аудит AI действий"""
    async def log(self,
        actor: str,          # user_id | agent_id | orchestrator
        action: str,
        target: str,         # document_id | tool_id | etc.
        payload: dict,
        result: str,         # success | blocked | failed | approved | rejected
        policy_decision: PolicyDecision | None,
        session_id: str | None,
    ) -> AuditEvent: ...
```

### 0.3. ERD — Новые сущности (основные)

#### Identity / Organization
```
Organization: id, name, slug, settings(JSON), created_at
OrganizationUnit: id, org_id(FK), name, parent_unit_id(FK), level
OrganizationMembership: id, user_id(FK), org_id(FK), unit_id(FK), company_role, functional_role, active
DocumentParticipation: id, user_id(FK), document_id(FK), role(owner|reviewer|approver|observer|negotiator|signer|ai_supervisor)
TenantContext: id, org_id(FK), mode(standalone|branch), config(JSON)
UserAgentPolicyProfile: id, user_id(FK), org_id(FK), allowed_ai_modes(JSON), allowed_actions(JSON), allowed_agents(JSON), allowed_tools(JSON), approval_required_for(JSON)
```

#### Policy
```
Policy: id, level(platform|tenant|org|branch|document|user), scope_id, policy_type, rules(JSON), priority, active
ApprovalRule: id, policy_id(FK), action_pattern, required_approvers, escalation_timeout
ActionPermission: id, policy_id(FK), action_type, allowed_roles(JSON), conditions(JSON)
```

#### AI Collaboration
```
AISession: id, document_id(FK), user_id(FK), stage, status(active|paused|closed), context_snapshot(JSON), created_at
AIConversationTurn: id, session_id(FK), role(user|assistant|system), content, model_used, tokens_used, created_at
AIAction: id, session_id(FK), type(explain_finding|suggest_clause|create_comment_draft|...), target_entity_type, target_entity_id, payload(JSON), rationale, confidence, approval_required, execution_status(pending|approved|rejected|executed|blocked), created_at
AIActionApproval: id, action_id(FK), approver_id(FK), decision(approve|reject|edit_and_approve), comment, decided_at
AIAuditRecord: id, session_id(FK), action_id(FK), actor, event_type, details(JSON), model_used, context_sent(JSON), created_at
```

#### Orchestration
```
OrchestratorRun: id, goal, initiated_by(FK), document_id(FK), status(planning|executing|paused|completed|failed|cancelled), created_at
ExecutionPlan: id, run_id(FK), plan_definition(JSON/YAML), version, created_at
PlanStep: id, plan_id(FK), order, type(tool_call|agent_delegation|approval_checkpoint|condition), tool_id(FK?), agent_id(FK?), input(JSON), output(JSON), status(pending|running|completed|failed|blocked|skipped), started_at, completed_at
OrchestratorCheckpoint: id, run_id(FK), step_id(FK), checkpoint_type(approval|review|escalation), status, resolved_by, resolved_at
```

#### Tool & Agent Registry
```
ToolDefinition: id, tool_id(unique), name, description, type(internal|external), input_schema(JSON), output_schema(JSON), permissions(JSON), policy_tags(JSON), risk_level, sync_mode, active, version
ToolInvocation: id, tool_id(FK), invoked_by, context(JSON), input(JSON), output(JSON), status, duration_ms, error, created_at
AgentDefinition: id, agent_id(unique), name, specialization, allowed_tools(JSON), task_types(JSON), autonomy_level, confidence_threshold, model_profile, active, version
AgentInvocation: id, agent_id(FK), task(JSON), context(JSON), result(JSON), tools_used(JSON), status, duration_ms, created_at
AgentDelegation: id, from_agent_id, to_agent_id, task(JSON), run_id(FK), status, created_at
```

#### Workflow
```
WorkflowDefinition: id, name, document_type, jurisdiction, conditions(JSON), steps(JSON), active, version
WorkflowExecution: id, definition_id(FK), document_id(FK), current_step, status, started_at, completed_at
WorkflowTask: id, execution_id(FK), step_name, assignee_id(FK), task_type, status(pending|in_progress|completed|escalated|skipped), sla_deadline, completed_at
WorkflowEvent: id, execution_id(FK), event_type, payload(JSON), triggered_by, created_at
```

#### Collaboration
```
Comment: id, document_id(FK), author_id(FK), content, anchor_type(document|section|clause|finding), anchor_id, anchor_version, is_ai_generated, parent_comment_id(FK), status(active|resolved|deleted), created_at
CommentThread: id, document_id(FK), root_comment_id(FK), status(open|resolved), resolved_by, resolved_at
Mention: id, comment_id(FK), user_id(FK), notified
CommentAssignment: id, comment_id(FK), assignee_id(FK), status, created_at
```

#### Template Governance
```
TemplateVersion: id, template_id(FK), version, content(JSON/XML), variables(JSON), validation_rules(JSON), status(draft|active|deprecated), created_by, created_at
ClausePolicy: id, org_id(FK), clause_type, status(approved|fallback|prohibited|risky), alternative_clause_id(FK), risk_explanation, created_at
GeneratedDocumentTrace: id, document_id(FK), template_id(FK), template_version(FK), variables_used(JSON), clauses_used(JSON), ai_session_id(FK), created_at
```

#### Integration
```
IntegrationConfig: id, org_id(FK), type(webhook|api|edo|esign), config(JSON), active
WebhookDelivery: id, config_id(FK), event_type, payload(JSON), status(pending|delivered|failed), attempts, last_attempt_at, delivered_at
DomainEvent: id, event_type, entity_type, entity_id, payload(JSON), emitted_by, created_at
```

### 0.4. API Contracts (верхнеуровневый)

```
# AI Sessions
POST   /api/v2/documents/{id}/ai/sessions          # Создать сессию
GET    /api/v2/documents/{id}/ai/sessions          # Список сессий
POST   /api/v2/ai/sessions/{id}/messages           # Отправить сообщение
GET    /api/v2/ai/sessions/{id}/messages           # История
GET    /api/v2/ai/sessions/{id}/context            # Текущий контекст

# AI Actions
GET    /api/v2/ai/sessions/{id}/actions            # Действия сессии
POST   /api/v2/ai/actions/{id}/approve             # Одобрить
POST   /api/v2/ai/actions/{id}/reject              # Отклонить
POST   /api/v2/ai/actions/{id}/edit-and-approve    # Редактировать и одобрить

# Orchestrator
POST   /api/v2/orchestrator/runs                   # Запустить цель
GET    /api/v2/orchestrator/runs/{id}              # Статус
GET    /api/v2/orchestrator/runs/{id}/plan         # План выполнения
GET    /api/v2/orchestrator/runs/{id}/steps        # Шаги
POST   /api/v2/orchestrator/runs/{id}/continue     # Продолжить после approval
POST   /api/v2/orchestrator/runs/{id}/cancel       # Отменить

# Workflow
POST   /api/v2/workflow/definitions                # Создать маршрут
GET    /api/v2/workflow/tasks                      # Мои задачи
POST   /api/v2/workflow/tasks/{id}/complete        # Завершить задачу
POST   /api/v2/workflow/tasks/{id}/escalate        # Эскалировать

# Comments
POST   /api/v2/documents/{id}/comments            # Создать комментарий
GET    /api/v2/documents/{id}/comments             # Список
POST   /api/v2/comments/{id}/reply                 # Ответить
POST   /api/v2/comments/{id}/resolve               # Закрыть
POST   /api/v2/comments/{id}/assign                # Назначить

# Organizations
POST   /api/v2/organizations                       # Создать
GET    /api/v2/organizations/{id}/members          # Участники
POST   /api/v2/organizations/{id}/members          # Добавить участника

# Policies
GET    /api/v2/policies                            # Список политик
POST   /api/v2/policies                            # Создать
PATCH  /api/v2/policies/{id}                       # Обновить

# Tools & Agents
GET    /api/v2/tools                               # Список инструментов
GET    /api/v2/tools/{id}                          # Детали инструмента
GET    /api/v2/agents                              # Список агентов
GET    /api/v2/agents/{id}                         # Детали агента
```

### 0.5. Модуль `src/core/` — структура

```
src/core/
├── __init__.py
├── interfaces.py                  # ITool, IAgent, IPolicyResolver, etc.
├── base.py                        # BaseModel extensions, common types
│
├── identity_org/
│   ├── __init__.py
│   ├── models.py                  # Organization, Membership, Roles
│   ├── service.py                 # OrganizationContextService
│   └── schemas.py                 # Pydantic schemas
│
├── policies/
│   ├── __init__.py
│   ├── models.py                  # Policy, ApprovalRule, ActionPermission
│   ├── resolver.py                # MultiLevelPolicyResolver
│   └── schemas.py
│
├── ai_collaboration/
│   ├── __init__.py
│   ├── models.py                  # AISession, AIAction, AIConversationTurn, etc.
│   ├── session_service.py         # AICollaboratorService
│   ├── context_builder.py         # AIContextBuilderService
│   ├── action_parser.py           # AIActionParserService
│   ├── action_executor.py         # AIActionExecutionService
│   ├── approval_service.py        # AIApprovalService
│   ├── audit_service.py           # AIAuditService
│   └── schemas.py
│
├── orchestrator/
│   ├── __init__.py
│   ├── models.py                  # OrchestratorRun, ExecutionPlan, PlanStep, etc.
│   ├── orchestrator_service.py    # AgentOrchestratorService
│   ├── planner.py                 # ExecutionPlannerService (Lobster-pattern)
│   ├── step_executor.py           # StepExecutor (tool calls + agent delegation)
│   └── schemas.py
│
├── tools/
│   ├── __init__.py
│   ├── models.py                  # ToolDefinition, ToolInvocation
│   ├── registry.py                # ToolRegistryService
│   ├── invoker.py                 # ToolInvocationService (validate → policy → execute → audit)
│   ├── adapters/                  # Адаптеры существующих сервисов → tools
│   │   ├── document_parser_tool.py
│   │   ├── risk_scorer_tool.py
│   │   ├── clause_extractor_tool.py
│   │   ├── contract_generator_tool.py
│   │   ├── rag_search_tool.py
│   │   └── ...
│   └── schemas.py
│
├── agents/
│   ├── __init__.py
│   ├── models.py                  # AgentDefinition, AgentInvocation, AgentDelegation
│   ├── registry.py                # AgentRegistryService
│   ├── delegator.py               # AgentDelegationService
│   └── schemas.py
│
├── workflow/
│   ├── __init__.py
│   ├── models.py                  # WorkflowDefinition, Execution, Task, Event
│   ├── engine.py                  # WorkflowEngineService
│   └── schemas.py
│
├── collaboration/
│   ├── __init__.py
│   ├── models.py                  # Comment, Thread, Mention, Assignment
│   ├── service.py                 # CommentAnchorService
│   └── schemas.py
│
├── templates/
│   ├── __init__.py
│   ├── models.py                  # TemplateVersion, ClausePolicy, GeneratedTrace
│   ├── governance_service.py      # TemplateValidationService
│   ├── clause_policy_service.py   # ClausePolicyService
│   └── schemas.py
│
├── integrations/
│   ├── __init__.py
│   ├── models.py                  # IntegrationConfig, WebhookDelivery, DomainEvent
│   ├── event_bus.py               # IntegrationDispatcherService
│   ├── webhook_service.py
│   └── schemas.py
│
└── audit/
    ├── __init__.py
    ├── models.py                  # Extended audit models
    ├── service.py                 # AuditService
    └── schemas.py
```

### 0.6. Migration Strategy

1. **Новый код в `src/core/`** — не ломает существующий `src/services/` и `src/api/`
2. **API v2 рядом с v1** — новые endpoints в `/api/v2/`, старые работают как прежде
3. **Alembic миграции** — новые таблицы создаются, существующие не ломаются
4. **Существующие сервисы → tool adapters** — оборачиваем в ITool интерфейс, не переписываем
5. **Существующие агенты → agent registry** — оборачиваем в IAgent интерфейс
6. **Фронтенд** — новые страницы и компоненты рядом с существующими

---

## Сценарии использования (User Flows)

### Flow 1: Intake with AI
```
Пользователь загружает документ
→ AISession создаётся автоматически (stage: intake)
→ AI классифицирует документ (tool: document_classifier)
→ AI задаёт уточняющие вопросы
→ AI предлагает тип анализа (AIAction: suggest_route)
→ Policy check: пользователь имеет право на этот тип?
→ Пользователь подтверждает → запуск review
```

### Flow 2: Goal-driven Orchestration
```
Пользователь: «Подготовь документ к внутреннему согласованию»
→ OrchestratorRun создаётся
→ ExecutionPlanner строит plan (детерминированно, по workflow template):
  1. tool: document_analyzer → findings
  2. tool: risk_scorer → risk band
  3. agent: review_agent → detailed review
  4. approval_checkpoint: если risk > HIGH → mandatory human review
  5. tool: summary_generator → executive summary
  6. tool: workflow_task_creator → создать задачи для согласователей
→ Каждый шаг: policy check + audit log
→ Пользователь видит plan + progress в Execution Plan UI
```

### Flow 3: AI Collaboration in Review
```
Пользователь открывает findings → AI Panel
→ Ask: «Почему этот пункт помечен как рискованный?»
→ AI строит context (document + finding + clause + org policy)
→ AI отвечает (AIConversationTurn)
→ AI предлагает action: create_comment_draft (confidence: 0.85)
→ Policy check: auto-approve (confidence > 0.8, role: legal_user)
→ Comment draft создаётся, пользователь может отредактировать
```

---

## Критерии приёмки (из ТЗ)

1. ✅ AI встроен в каждый ключевой этап lifecycle документа
2. ✅ AI collaborator modes + agent orchestrator mode
3. ✅ Оркестратор принимает high-level goals и строит execution plans
4. ✅ Оркестратор использует только зарегистрированные tools и agents
5. ✅ Каскадная LLM-архитектура и model routing
6. ✅ AI behavior зависит от user, role, org, document role
7. ✅ Organization membership model
8. ✅ Standalone + embedded branch mode
9. ✅ Workflow, collaboration, templates интегрированы с AI layer
10. ✅ Все действия AI аудируются и не обходят policy
11. ✅ Mandatory human checkpoints
12. ✅ AI-first, agentic, contract-domain-oriented архитектура
