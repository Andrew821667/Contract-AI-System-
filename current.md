# Contract AI System — ЧИТАЙ ПЕРВЫМ!

**Последнее обновление:** 2026-03-16
**Статус:** Phase 0 — Архитектурная трансформация в AI-collaborative Contract OS
**Предыдущие этапы:** Stages 1-4.5 завершены ✅ (базовый продукт + security hardening)

---

## ЧТО МЫ СТРОИМ

### Миссия
**AI-collaborative contract operating system** — система, в которой AI является центральным коллаборатором в работе с договорами, а не пассивным чат-виджетом рядом с документом.

### Архитектурная формула
```
Contract-AI-System = hierarchical LLM cascade
                   + AI collaborator layer
                   + agent orchestrator layer
                   + specialized agents
                   + controlled tool ecosystem
                   + user/org-aware policy system
                   + standalone/branch-ready contract domain
```

### Референсная модель
**OpenClaw** (https://github.com/openclaw/openclaw, 163K★) — ментальная модель для agentic patterns:
- Gateway как единый control plane для sessions/tools/events
- Session isolation per agent+user
- SOUL.md = философия агента (не конфигурация, а поведение)
- Skills = typed tools с formal schema + eligibility gating
- **Lobster-паттерн: "Don't orchestrate with LLMs. Use them for creative work, use code for plumbing."** Детерминированные YAML-планы, НЕ LLM-based routing
- Agent-to-Agent communication через explicit allowlists
- Config-first approach (policies/profiles как данные, не hardcoded logic)

### Ключевые принципы (НАРУШАТЬ НЕЛЬЗЯ)
1. **AI-first** — AI встроен в КАЖДЫЙ этап lifecycle документа, не прикручен сбоку
2. **Policy-first execution** — ни один AI action, tool call или orchestration step не выполняется без permission/policy/audit
3. **Tool-first execution** — оркестратор действует ТОЛЬКО через зарегистрированные tools и agents, никогда напрямую
4. **User/org-aware** — AI ведёт себя по-разному в зависимости от пользователя, роли, организации, роли в документе
5. **Deterministic orchestration** — оркестратор строит план детерминированно (по типу документа, risk band, policy), LLM только для creative work
6. **Branch-ready** — standalone + embedded branch mode с самого начала архитектуры
7. **Каскадная LLM** — orchestration level (fast/cheap) → specialized agent level (domain) → tool level (deterministic)

### Что это НЕ является
- ❌ Обычный CLM без агентного ядра
- ❌ Простой AI chatbot рядом с документом
- ❌ Builder-first/no-code платформа
- ❌ Monolithic LLM app без policy/roles/orchestration

---

## 14 АРХИТЕКТУРНЫХ СЛОЁВ

| # | Слой | Назначение | Текущая готовность |
|---|------|------------|--------------------|
| 1 | **Identity / Organization** | Users, orgs, units, memberships, company/functional/document roles | 🟡 20% (User+Role есть, Org нет) |
| 2 | **Policy** | MultiLevelPolicyResolver, approval rules, action permissions, cascade platform→tenant→org→user→doc | 🔴 0% |
| 3 | **LLM Routing** | Каскадный выбор моделей по task/sensitivity/cost/tenant policy | 🟡 40% (model_router.py) |
| 4 | **AI Collaboration** | AI sessions, context builder, conversation turns, typed AI actions, action lifecycle | 🔴 0% |
| 5 | **Agent Orchestration** | Orchestrator runs, execution plans, plan steps, approval checkpoints, execution trace | 🔴 5% (заглушка) |
| 6 | **Specialized Agents** | Agent registry, 8+ специализированных агентов, delegation model | 🟡 25% (agents есть, registry нет) |
| 7 | **Tool Registry / Execution** | Formal tool schemas, eligibility gating, invocation pipeline, policy checks | 🔴 10% (сервисы есть, формализации нет) |
| 8 | **Workflow** | Workflow engine, definitions, 14 статусов, templates, AI-triggered routing, SLA | 🟡 15% (ReviewTask есть) |
| 9 | **Collaboration** | Comments, threads, mentions, anchors, assignments, AI-generated comments | 🔴 5% (feedback есть) |
| 10 | **Template Governance** | Template registry, versions, variables, clause policy, generation traceability | 🟡 20% (template_manager) |
| 11 | **Contract Domain** | Documents, versions, findings, risk summaries, clause links | 🟢 60% (CRUD работает) |
| 12 | **Integration** | Event model, webhooks, adapter abstraction, public API | 🔴 5% |
| 13 | **Audit / Compliance** | AI audit, security events, access logs, integrity records, traceability | 🟡 15% (AuditLog есть) |
| 14 | **Frontend Workspace** | AI Panel, Goal Box, Execution Plan, Workflow Timeline, Comments, Org Admin | 🟡 20% (базовый CRUD) |

---

## ПЛАН РАЗРАБОТКИ (АКТИВНЫЙ)

### Phase 0: Architecture & Contracts Foundation — ВЫПОЛНЕНО ✅
**Статус:** ✅ Завершено (2026-03-16, ветка AI_first)
**Цель:** архитектурный каркас, интерфейсы, ERD, новая структура модулей

Результат:
- [x] `src/core/` — 11 подмодулей, 63 файла, ~6500 строк
- [x] 8 Protocol-интерфейсов: ITool, IAgent, IPolicyResolver, IContextBuilder, ILLMRouter, IAuditLogger, IToolRegistry, IAgentRegistry
- [x] 12 enums, 10 Pydantic value objects (ToolContext, ToolResult, PolicyDecision, AIContext, etc.)
- [x] 37 новых SQLAlchemy таблиц (backward-compatible, Alembic миграция 012)
- [x] 34 API v2 эндпоинта (8 роутеров: ai_sessions, ai_actions, orchestrator, organizations, policies, tools_agents, workflow, comments)
- [x] Сервисы: MultiLevelPolicyResolver, ToolRegistry+Invoker, AgentRegistry+Delegator, AICollaboratorService, ExecutionPlanner, StepExecutor, WorkflowEngine, CommentService, EventBus, WebhookService, AuditQueryService
- [x] 5 tool-адаптеров (document_parser, risk_scorer, clause_extractor, contract_generator, rag_search)
- [x] Тесты: 313 passed, 0 failed (0 регрессий)

### Phase 1: Identity / Organization / Policy Backbone — ВЫПОЛНЕНО ✅
**Статус:** ✅ Завершено (2026-03-16)

Результат:
- [x] Organization, OrganizationUnit, OrganizationMembership (модели в src/core/identity_org/)
- [x] DocumentParticipationRole (7 ролей)
- [x] TenantContext, UserAgentPolicyProfile (модели готовы)
- [x] MultiLevelPolicyResolver (реализован в src/core/policies/resolver.py)
- [x] Policy CRUD API (3 эндпоинта в /api/v2/policies)
- [x] Seed data: 3 platform policies + тестовая организация (src/core/seed.py)
- [x] OrganizationContext dependencies (src/api/v2/dependencies.py)
- [x] 27 тестов для core-модулей (tests/test_core.py)
- [ ] Миграция User/Role (отложено — backward-compatible)

### Phase 2: AI Collaboration Core — ВЫПОЛНЕНО ✅
**Статус:** ✅ Завершено (2026-03-16)

Результат:
- [x] AISession, AIConversationTurn, AIAction, AIActionApproval, AIAuditRecord
- [x] AIContextBuilder — connected to real Comments + WorkflowExecution models
- [x] AIAction с 15 типами (explain_finding, suggest_clause, modify_clause, create_comment_draft, suggest_risk_mitigation, create_summary, compare_versions, translate_clause, answer_question, draft_negotiation_response, analyze_risks, extract_clauses, search_knowledge, generate_contract, assign_reviewer)
- [x] AI Action lifecycle: parse → policy check → threshold → execute/approval/block → audit
- [ ] AIActionPolicy, AIApprovalService, AIAuditService
- [x] LLMRouterAdapter — async bridge к LLMGateway/ModelRouter
- [x] System prompt builder с findings, workflow state, action format
- [ ] **Frontend:** AI Panel (Ask/Explain/Draft/Route/Compare/Negotiate/Summarize/Actions)

### Phase 3: Tool Registry & Tool Execution — ВЫПОЛНЕНО ✅
**Статус:** ✅ Завершено (2026-03-16)

Результат:
- [x] Tool Registry с полным lifecycle (register, get, list_by_tags, list_by_risk)
- [x] 16 tool-адаптеров (5 original + 11 new: complexity_scorer, counterparty, document_diff, smart_composer, recommendation, clause_library, knowledge_base, analytics, template_manager, validation, ocr)
- [x] Tool invocation pipeline: validate → eligibility gate → policy check → execute → record → audit
- [x] Eligibility gating: permissions, policy resolver, risk threshold

### Phase 4: Agent Registry & Specialized Agents — ВЫПОЛНЕНО ✅
**Статус:** ✅ Завершено (2026-03-16)

Результат:
- [x] AgentRegistryService (register, get, find_for_task, unregister)
- [x] BaseAgentAdapter — обёртка legacy BaseAgent → IAgent protocol
- [x] 7 legacy агентов зарегистрированы (contract_analyzer, contract_generator, disagreement_analyzer, changes_analyzer, onboarding, quick_export, orchestrator)
- [x] AgentDelegationService с policy check + audit

### Phase 5: Agent Orchestrator Runtime — ВЫПОЛНЕНО ✅
**Статус:** ✅ Завершено (2026-03-16)

Результат:
- [x] OrchestratorRun, ExecutionPlanner (Lobster-паттерн)
- [x] 8 plan templates: prepare_for_review, full_analysis, generate_contract, compare_versions, negotiation_support, quick_intake, compliance_check
- [x] StepExecutor: tool calls + agent delegations + approval checkpoints + conditions
- [x] $ref resolution между шагами, conditional branching
- [x] Human-in-the-loop: approval gates (checkpoint → pause → continue)
- [ ] **Frontend:** Goal Box + Execution Plan UI

### Phase 6: Workflow Engine — ВЫПОЛНЕНО ✅
**Статус:** ✅ Завершено (2026-03-16)

Результат:
- [x] WorkflowDefinition + WorkflowExecution + WorkflowTask + WorkflowEvent
- [x] WorkflowEngineService (start, complete_task, advance/reject/return)
- [x] SLA tracking (deadline calculation)
- [ ] AI-triggered routing (pending frontend integration)
- [ ] **Frontend:** Workflow Timeline

### Phase 7: Collaboration Core — ВЫПОЛНЕНО ✅
**Статус:** ✅ Завершено (2026-03-16)

Результат:
- [x] Comment, CommentThread, Mention, CommentAssignment models
- [x] CommentService (create, reply, resolve, assign, @mention parsing)
- [x] Document/section/clause/finding-level anchoring
- [ ] **Frontend:** Comments/Threads Panel

### Phase 8: Template Governance + Clause Policy — ВЫПОЛНЕНО ✅
**Статус:** ✅ Завершено (2026-03-16)

Результат:
- [x] TemplateVersion, ClausePolicy models
- [x] TemplateGovernanceService (versioning, activate)
- [x] ClausePolicyService (is_clause_allowed, get_prohibited_clauses)
- [ ] **Frontend:** Template Registry + Clause Policy Manager

### DI Bootstrap — ВЫПОЛНЕНО ✅
- [x] src/core/bootstrap.py — CoreServices container
- [x] Все сервисы связаны через bootstrap() функцию
- [x] Auto-registration: 16 tools + 7 agents

### Phase 9: Negotiation & Version Intelligence ← СЛЕДУЮЩИЙ
**Статус:** ⏳

Deliverables:
- [ ] AI-assisted disagreement flow, draft возражений
- [ ] Version comparison, material change detection
- [ ] **Frontend:** Negotiation workspace

### Phase 10: Integration Core + Event Model
**Статус:** ⏳ Ожидает Phase 9

Deliverables:
- [ ] Event model (15+ domain events)
- [ ] Webhook delivery + retry, adapter abstraction
- [ ] Public integration API, integration settings UI

### Phase 11: LLM Cascade Hardening
**Статус:** ⏳ Ожидает Phase 10

Deliverables:
- [ ] LLM routing policies (tenant, sensitivity, cost, latency, confidentiality)
- [ ] Local-first / external toggle, 3-level cascade
- [ ] Fallback modes (LLM unavailable → workflow continues)

### Phase 12: Branch Mode + Enterprise Hardening
**Статус:** ⏳ Ожидает Phase 11

Deliverables:
- [ ] Standalone + embedded branch mode
- [ ] Shared identity/tools/policy bindings
- [ ] Full RBAC, tenant isolation, sensitive field masking
- [ ] Integrity tracking (hashes, verification, version linkage)

---

## СУЩЕСТВУЮЩИЙ КОД — ЧТО ПЕРЕИСПОЛЬЗУЕМ

### Backend (src/)
| Компонент | Файлы | Роль в новой архитектуре |
|-----------|-------|--------------------------|
| **LLM Gateway** | `services/llm_gateway.py` | → LLM Routing Layer (6 провайдеров: Claude, OpenAI, Perplexity, Yandex, DeepSeek, Qwen) |
| **Model Router** | `services/model_router.py` | → LLM Routing Layer (DeepSeek→Claude→GPT-4o cascade) |
| **Agents** | `agents/*.py` (8 шт) | → Specialized Agents Layer (рефакторинг в formal registry) |
| **RAG** | `services/rag_system.py`, `enhanced_rag.py`, `rag_service.py` | → Tool (ChromaDB + pgvector hybrid search) |
| **Risk Analysis** | `services/risk_scorer.py`, `risk_analyzer.py`, `ml/risk_predictor.py` | → Tool (risk scoring) |
| **Document Processing** | `services/document_processor.py`, `text_extractor.py`, `document_parser*.py` | → Tool (document intake) |
| **Contract Generation** | `services/contract_generation_service.py`, `llm_contract_generator.py` | → Tool (contract generator) |
| **Clause Library** | `services/clause_library_service.py`, `clause_extractor.py` | → Tool (clause search/extract) |
| **Templates** | `services/template_manager.py`, `template_comparator.py` | → Template Governance Layer |
| **Disagreement** | `services/disagreement_service.py`, `disagreement_export_service.py` | → Tool (negotiation) |
| **Auth** | `services/auth_service.py`, `models/auth_models.py` | → Identity Layer (JWT, sessions, audit) |
| **Orchestrator** | `orchestrator/main_graph.py` | → Agent Orchestration Layer (переписать) |

### Frontend (frontend/)
| Компонент | Роль в новой архитектуре |
|-----------|--------------------------|
| Next.js 14 + Tailwind + Zustand | Основа остаётся, расширяем |
| Login, Dashboard, Contracts CRUD | Сохраняем, добавляем AI Panel |
| Sidebar, responsive layout | Сохраняем |
| api.ts (API клиент) | Расширяем для новых endpoints |

### Infrastructure
| Компонент | Статус |
|-----------|--------|
| Docker Compose (6 сервисов) | ✅ Работает на порту 8090 |
| PostgreSQL 16 + pgvector | ✅ Готов |
| Redis | ✅ Готов |
| Nginx reverse proxy | ✅ Готов |
| CI/CD (GitHub Actions) | ✅ Работает |
| 274 теста | ✅ Все проходят |

---

## ЦЕЛЕВАЯ СТРУКТУРА МОДУЛЕЙ

```
src/
├── core/                          # НОВОЕ: ядро AI-collaborative OS
│   ├── identity_org/              # Organizations, memberships, roles
│   ├── policies/                  # MultiLevelPolicyResolver, approval rules
│   ├── ai_collaboration/          # AI sessions, context, actions, lifecycle
│   ├── orchestrator/              # Orchestrator runs, execution plans, steps
│   ├── tools/                     # Tool registry, schemas, invocation pipeline
│   ├── agents/                    # Agent registry, delegation, invocation
│   ├── workflow/                  # Workflow engine, definitions, tasks
│   ├── collaboration/             # Comments, threads, mentions, anchors
│   ├── templates/                 # Template governance, clause policy
│   ├── integrations/              # Event model, webhooks, adapters
│   └── audit/                     # AI audit, security events, integrity
│
├── api/                           # FastAPI routes (расширяем)
│   ├── auth/                      # Существующий auth
│   ├── contracts/                 # Существующий contracts
│   ├── v2/                        # НОВОЕ: API v2 для новых доменов
│   │   ├── ai_sessions.py
│   │   ├── ai_actions.py
│   │   ├── orchestrator.py
│   │   ├── workflow.py
│   │   ├── comments.py
│   │   ├── organizations.py
│   │   ├── policies.py
│   │   ├── tools.py
│   │   └── agents.py
│   └── websocket/
│
├── services/                      # Существующие сервисы (→ формализуются как tools)
├── agents/                        # Существующие агенты (→ рефакторинг в registry)
├── models/                        # Существующие модели (расширяем)
├── middleware/                     # Security middleware
└── main.py                        # FastAPI app
```

---

## ДОКУМЕНТЫ ПРОЕКТА

| Документ | Назначение |
|----------|------------|
| `current.md` | **ЭТОТ ФАЙЛ** — читай первым! Состояние, план, архитектура |
| `CLAUDE.md` | Краткая справка для агента (обновить после Phase 0) |
| `CONTRACT_AI_SYSTEM_SPECIFICATION.md` | Оригинальная спецификация (Stages 1-5) |
| `DEVELOPMENT_PLAN.md` | **НОВОЕ** — детальный план разработки с ERD и интерфейсами |

### ТЗ новой концепции (3 документа)
Хранятся в сообщениях пользователя (2026-03-16):
1. **Техническое задание** — 30 разделов, полная архитектурная спецификация
2. **Roadmap** — 12 этапов (P0-P3): architecture → identity → workspace → workflow → tools → orchestrator → templates → negotiation → integrations → llm cascade → branch mode → enterprise
3. **Implementation Brief** — инструкция для агента разработки: что строить, в каком порядке, что запрещено

---

## ЭКСПЛУАТАЦИЯ

### Docker (рекомендуется)
```bash
cd ~/Desktop/Contract-AI-System-
docker compose --env-file .env.docker up --build -d
# Всё работает на http://localhost:8090
```

### Локально (dev)
```bash
cd ~/Desktop/Contract-AI-System-
source venv/bin/activate
python3 -m uvicorn src.main:app --host 0.0.0.0 --port 8000  # Бэкенд
cd frontend && npm run dev                                     # Фронтенд (порт 3000)
streamlit run admin/streamlit_dashboard.py --server.port=8502  # Админка
```

### Учётные записи
| Email | Роль | Пароль |
|-------|------|--------|
| admin@contractai.ru | admin | Admin123! |
| lawyer@contractai.ru | lawyer | Lawyer123! |
| vip@contractai.ru | senior_lawyer | Vip12345! |
| demo@contractai.ru | demo | Demo1234! |

### .env (ключевые переменные)
```
SECRET_KEY=<ОБЯЗАТЕЛЬНО! secrets.token_urlsafe(32)>
DATABASE_URL=sqlite:///./contract_ai.db  # dev
DEEPSEEK_API_KEY=<ключ>
```

### Технический стек
- **Backend:** FastAPI, SQLAlchemy, Pydantic v2, Python 3.11 (`python3`)
- **Frontend:** Next.js 14, React 18, TypeScript, Tailwind CSS, Zustand
- **Admin:** Streamlit multipage
- **DB:** SQLite (dev) / PostgreSQL 16 + pgvector (prod)
- **LLM:** DeepSeek (основной), Claude (expert), GPT-4o (fallback), + Perplexity, Yandex, Qwen
- **Auth:** JWT (HS256) + bcrypt + session management + email verification
- **Infra:** Docker Compose, Nginx, Redis, GitHub Actions CI/CD

---

## ПРАВИЛА РАЗРАБОТКИ

1. **UI и коммуникация на русском языке**
2. **Python 3.11** — используй `python3`, НЕ `python`
3. **`get_current_user`** — только из `src/api/dependencies.py`, НЕ дублировать
4. **CORS** — только конкретные origins, НЕ wildcard `*`
5. **Policy-first** — любой AI action через policy check + audit
6. **Tool-first** — оркестратор не выполняет действия напрямую, только через tools/agents
7. **Не ломай существующее** — новый код в `src/core/`, API v2 рядом с v1, миграции backward-compatible
8. **.env не в git** (есть в .gitignore)
9. **SECRET_KEY обязателен** — без него JWT не работает

---

## ИСТОРИЯ ЗАВЕРШЁННЫХ ЭТАПОВ

<details>
<summary>Stages 1-4.5 (завершены до 2026-03-16)</summary>

| Этап | Описание |
|------|----------|
| Stage 2.1 | Загрузка черновиков: PDF/DOCX/TXT/HTML/XML → DOCX |
| Stage 2.2 | Сравнение с шаблоном (template_comparator.py) |
| Stage 2.3 | Risk Scoring (risk_scorer.py, 0-100) |
| Stage 2.4 | Генерация DOCX + протокол разногласий |
| Stage 3 | Smart Router (complexity_scorer + model_router) |
| Stage 3.5 | Scheduler + Admin Auth + 4 пользователя |
| Stage 4 | Docker, CI/CD, pgvector, async SMTP |
| Stage 4.5 | Security Hardening: 25+ уязвимостей (JWT jti/iss/aud, token rotation, rate limiting, XSS, CORS, account enumeration, etc.) |

274 теста, 0 ошибок. Docker: 6 контейнеров healthy на порту 8090.
</details>
</content>
</invoke>