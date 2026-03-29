# Contract AI System — ЧИТАЙ ПЕРВЫМ!

**Последнее обновление:** 2026-03-29
**Статус:** Ветка AI_first смержена в main. Активная разработка — только main.
**Ветка:** main

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

### Ключевые принципы (НАРУШАТЬ НЕЛЬЗЯ)
1. **AI-first** — AI встроен в КАЖДЫЙ этап lifecycle документа, не прикручен сбоку
2. **Policy-first execution** — ни один AI action, tool call или orchestration step не выполняется без permission/policy/audit
3. **Tool-first execution** — оркестратор действует ТОЛЬКО через зарегистрированные tools и agents, никогда напрямую
4. **User/org-aware** — AI ведёт себя по-разному в зависимости от пользователя, роли, организации
5. **Deterministic orchestration** — планы детерминированные (Lobster-паттерн), LLM только для creative work
6. **Branch-ready** — standalone + embedded branch mode с самого начала
7. **Каскадная LLM** — orchestration (fast/cheap) → agent (domain) → tool (deterministic)

---

## 14 АРХИТЕКТУРНЫХ СЛОЁВ

| # | Слой | Бэкенд | Фронтенд | Готовность |
|---|------|--------|----------|------------|
| 1 | **Identity / Organization** | ✅ Модели, API, OrganizationContext | ✅ Admin panel (orgs, members, roles) | 🟢 90% |
| 2 | **Policy** | ✅ MultiLevelPolicyResolver, CRUD API | ✅ Policy governance в admin | 🟢 95% |
| 3 | **LLM Routing** | ✅ CascadeManager, FallbackHandler, RoutingPolicy | ✅ LLM model settings в admin | 🟢 95% |
| 4 | **AI Collaboration** | ✅ Sessions, context, actions, lifecycle | ✅ AI Panel (Chat + Plan + Actions + QuickActions) | 🟢 95% |
| 5 | **Agent Orchestration** | ✅ Runs, plans, steps, checkpoints | ✅ Goal Box + Execution Plan + PlanStepItem | 🟢 95% |
| 6 | **Specialized Agents** | ✅ Registry, 7 агентов, delegation | ✅ Agent registry в admin | 🟢 90% |
| 7 | **Tool Registry / Execution** | ✅ 16 tool-адаптеров, invocation pipeline | ✅ Tool registry в admin | 🟢 95% |
| 8 | **Workflow** | ✅ Engine, definitions, tasks, SLA, AI-triggered routing | ✅ Timeline + TaskCards + 3-tab page | 🟢 95% |
| 9 | **Collaboration** | ✅ Comments, threads, mentions, anchors | ✅ CommentThread + useComments | 🟢 90% |
| 10 | **Template Governance** | ✅ Versioning, clause policy | ✅ Templates tab + clause policies в admin | 🟢 90% |
| 11 | **Contract Domain** | ✅ Documents, versions, findings, risk | ✅ Contracts CRUD, analysis, upload | 🟢 95% |
| 12 | **Integration** | ✅ Events, webhooks, dispatching | ✅ Webhooks CRUD + Event viewer + Delivery history в admin | 🟢 90% |
| 13 | **Audit / Compliance** | ✅ AI audit, security events, integrity | ✅ Audit logs в системе | 🟢 90% |
| 14 | **Frontend Workspace** | — | ✅ AI Panel, Negotiation, Workflow, Admin | 🟢 95% |

---

## ЗАВЕРШЁННЫЕ ФАЗЫ

### Phase 0-8: Architecture + Core Backend + Core Frontend ✅
**Завершено:** 2026-03-16

- `src/core/` — 13 подмодулей, 37 SQLAlchemy таблиц, 34 API v2 эндпоинта
- 8 Protocol-интерфейсов, 16 tool-адаптеров, 7 агентов
- CoreServices DI bootstrap
- 74 core-тестов

### Phase 9: Negotiation & Version Intelligence ✅
**Завершено:** 2026-03-17

- NegotiationService, VersionIntelligenceService
- API v2: 5 negotiation + 4 version intelligence endpoints
- **Frontend:** NegotiationWizard (4 steps), ObjectionCard, PositionView

### Phase 10: Integration Core + Event Model ✅
**Завершено:** 2026-03-17

- 20 domain event types, EventDispatcher, WebhookService
- API v2: 7 integration endpoints
- **Frontend:** НЕ реализован (Integration Settings UI) — единственный пробел

### Phase 11: LLM Cascade Hardening ✅
**Завершено:** 2026-03-17

- CascadeManager, FallbackHandler, LLMRoutingPolicy
- Circuit breaker (3 failures/5min), 4 fallback modes

### Phase 12: Branch Mode + Enterprise Hardening ✅
**Завершено:** 2026-03-17

- BranchModeService, RBACService, TenantIsolationService, IntegrityService

### Frontend: Full Workspace ✅
**Завершено:** 2026-03-23

| Компонент | Файлы | Статус |
|-----------|-------|--------|
| AI Panel (Chat + Plan) | `components/ai/AIPanel.tsx`, `ChatMessage.tsx`, `AIActionCard.tsx`, `ChatInput.tsx`, `QuickActions.tsx` | ✅ |
| Execution Plan + Goal Box | `components/ai/ExecutionPlan.tsx`, `PlanStepItem.tsx` | ✅ |
| Document Sidebar | `components/ai/DocumentSidebar.tsx` | ✅ |
| AI Workspace Page | `app/ai/page.tsx` | ✅ |
| Workflow Timeline | `components/workflow/WorkflowTimeline.tsx`, `TaskCard.tsx` | ✅ |
| Workflow Page (3 tabs) | `app/workflow/page.tsx` | ✅ |
| Negotiation Wizard | `components/negotiations/NegotiationWizard.tsx`, `ObjectionCard.tsx`, `PositionView.tsx` | ✅ |
| Comments/Threads | `components/negotiations/CommentThread.tsx` | ✅ |
| Org Admin Panel | `app/admin/page.tsx` (6 tabs: LLM, Orgs, Policies, Tools, Agents, Templates) | ✅ |

### Security Hardening ✅
**Завершено:** 2026-03-28

- 2 архитектурных аудита + 4-агентный security/load audit
- Atomic SQL UPDATE для login attempts
- Pessimistic locking для demo tokens
- Token theft detection в refresh_session
- Password reset хранит только SHA-256 hash
- Promise deduplication для concurrent API refresh
- Exponential backoff для WebSocket reconnection
- Убраны ID из 404 ошибок (anti-enumeration)
- PostgreSQL-only (SQLite только для тестов)
- 89 тестов для auth/admin/upload validation

### CI/CD ✅
- `.github/workflows/ci.yml` — 3 jobs: backend (lint+test), frontend (lint+build), docker

---

## ROADMAP — АКТИВНЫЙ ПЛАН РАЗВИТИЯ

### Этап 0 — Мерж AI_first → main ✅
- [x] Fast-forward мерж (61 коммит, 0 конфликтов)
- [x] Все дальнейшие изменения — только в main

### Этап 1 — "Условия компании" (Company Policies) ✅
**Цель:** Пользователь задаёт стандартные условия своей компании. При анализе договора система сравнивает пункты с этими стандартами и предлагает корректировки.

- [x] Новая таблица `company_conditions` + миграция Alembic (016)
  - user_id, category, title, description, condition_text, priority, is_active
- [x] CRUD API `/api/v1/conditions` (добавить/редактировать/удалить/список/категории)
- [x] Frontend: раздел "Условия" в sidebar вместо "Клаузулы"
- [x] Карточки условий с добавлением/редактированием/удалением
- [x] Категоризация: 11 категорий (финансовые, сроки, ответственность, расторжение, конфиденциальность и т.д.)

### Этап 2 — Интеграция условий в анализ ✅
**Цель:** Стандарты компании влияют на результаты анализа — персональный RAG-слой.

- [x] При анализе загружать активные условия пользователя из БД
- [x] Передавать в промпт RiskAnalyzer как "Стандарты компании"
- [x] Для каждого пункта договора — проверка соответствия стандартам (compliance_status)
- [x] Новый тип риска "compliance" — несоответствие стандартам компании
- [x] Генерация рекомендаций с привязкой к конкретному стандарту (related_condition)
- [x] Категория рекомендаций "company_standard" для стандартов компании

### Этап 3 — RAG Admin (Streamlit) 🔲
**Цель:** Загрузка и управление документами базы знаний (законы, судебная практика, шаблоны).

- [ ] Новая страница в Streamlit-админке: загрузка документов в RAG
- [ ] При загрузке: определить тип → md с разметкой → чанки → векторизация в ChromaDB
- [ ] UI для просмотра/удаления документов в базе знаний
- [ ] Подключить enhanced_rag.py (код есть, 1044 строки, не используется)

### Этап 4 — Автоиндексация и граф 🔲
**Цель:** Каждый проанализированный договор автоматически обогащает RAG.

- [ ] После анализа договора — автоматически индексировать в RAG
- [ ] Запускать GraphRAGPipeline.ingest_xml() для графовых связей
- [ ] Передавать RAG-контекст (законы + прецеденты) в анализ вместе с условиями компании

### Этап 5 — Перенос клаузул в админку 🔲
**Цель:** Извлечённые пункты — внутренний инструмент, не для пользователя.

- [ ] Убрать раздел "Клаузулы" из пользовательского sidebar
- [ ] Оставить в Streamlit-админке как внутренний инструмент
- [ ] Добавить просмотр/фильтрацию извлечённых пунктов по договорам

---

## ЗАВЕРШЁННЫЕ ЗАДАЧИ (2026-03-29)

### Исправления анализа договоров ✅
- Анализ вынесен в `run_in_executor` — API не блокируется во время LLM-вызовов
- CSRF: добавлена поддержка `*.ngrok-free.dev` для refresh token
- API `/contracts/{id}`: риски и рекомендации из нормализованных таблиц
- Все промпты risk_analyzer и recommendation_generator переведены на русский
- `llm_max_tokens` увеличен 4000 → 8000

---

## LEGACY — ЗАВЕРШЁННЫЕ ЗАДАЧИ

### 4. Ротация секретов 🔲
- `.env.docker` был в git — нужна ручная ротация ключей на сервере

---

## СТЕК

- **Backend:** FastAPI, SQLAlchemy, Pydantic v2, Python 3.11 (`python3`)
- **Frontend:** Next.js 14, React 18, TypeScript, Tailwind CSS, Zustand
- **DB:** PostgreSQL 16 + pgvector (dev & prod), SQLite only in tests
- **LLM:** DeepSeek (primary), Claude (expert), GPT-4o (fallback), + Perplexity, Yandex, Qwen
- **Auth:** JWT (HS256) + bcrypt + session management + token rotation
- **Infra:** Docker Compose (6 services), Nginx, Redis, GitHub Actions CI/CD
- **Tests:** 89 auth/admin/upload + 74 core + существующие = ~430+ тестов

---

## ЭКСПЛУАТАЦИЯ

### Docker (рекомендуется)
```bash
docker compose --env-file .env.docker up --build -d
# http://localhost:8090
```

### Локально (dev)
```bash
python3 -m uvicorn src.main:app --host 0.0.0.0 --port 8000  # Бэкенд
cd frontend && npm run dev                                     # Фронтенд (порт 3000)
```

### Учётные записи
| Email | Роль | Пароль |
|-------|------|--------|
| admin@contractai.ru | admin | Admin123! |
| lawyer@contractai.ru | lawyer | Lawyer123! |
| vip@contractai.ru | senior_lawyer | Vip12345! |
| demo@contractai.ru | demo | Demo1234! |

---

## ПРАВИЛА РАЗРАБОТКИ

1. **UI и коммуникация на русском языке**
2. **Python 3.11** — используй `python3`, НЕ `python`
3. **`get_current_user`** — только из `src/api/dependencies.py`, НЕ дублировать
4. **Policy-first** — любой AI action через policy check + audit
5. **Tool-first** — оркестратор не выполняет действия напрямую, только через tools/agents
6. **Новый код в `src/core/`** — не ломай существующий `src/services/`
7. **API v2 рядом с v1** — backward-compatible
8. **.env не в git**, SECRET_KEY обязателен
