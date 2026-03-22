# Contract AI System

**AI-collaborative contract operating system** — интеллектуальная платформа для работы с договорами на основе мультимодельного LLM-каскада, агентной оркестрации и policy-driven AI.

[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104+-green.svg)](https://fastapi.tiangolo.com/)
[![Next.js](https://img.shields.io/badge/Next.js-14-black.svg)](https://nextjs.org/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16+pgvector-blue.svg)](https://www.postgresql.org/)
[![Docker](https://img.shields.io/badge/Docker-Compose-2496ED.svg)](https://docs.docker.com/compose/)
[![Tests](https://img.shields.io/badge/Tests-387%20passed-brightgreen.svg)]()

---

## Содержание

- [Архитектура](#архитектура)
- [Возможности](#возможности)
- [Технологический стек](#технологический-стек)
- [Установка](#установка)
- [Docker Deployment](#docker-deployment)
- [Тестирование](#тестирование)
- [API](#api)
- [Roadmap](#roadmap)

---

## Архитектура

```
hierarchical LLM cascade + AI collaborator layer + agent orchestrator layer
+ specialized agents + controlled tool ecosystem + user/org-aware policy system
```

Архитектурные принципы:

1. **AI-first** — AI в каждом этапе lifecycle документа
2. **Policy-first** — ни один AI action без policy check + audit
3. **Tool-first** — оркестратор через tools/agents, никогда напрямую
4. **Deterministic orchestration** — планы детерминированные, LLM для creative work
5. **Org/user-aware** — AI ведёт себя по-разному для разных пользователей/ролей

### Структура проекта

```
Contract-AI-System/
├── src/
│   ├── core/                        # Phase 12: AI-collaborative OS ядро
│   │   ├── identity_org/            # Организации, пользователи, роли
│   │   ├── policies/                # Policy engine (AI action policies)
│   │   ├── tools/                   # Tool registry (typed tools)
│   │   ├── agents/                  # Agent registry + capabilities
│   │   ├── ai_collaboration/        # AI collaborator sessions
│   │   ├── orchestrator/            # Deterministic orchestration (runs/plans/steps)
│   │   ├── workflow/                # Workflow definitions + executions + tasks
│   │   ├── collaboration/           # Comments, annotations, assignments
│   │   ├── templates/               # Template governance + versioning
│   │   ├── negotiation/             # AI-driven negotiation engine
│   │   ├── integrations/            # Webhooks + event bus
│   │   └── enterprise/              # Integrity verification
│   │
│   ├── agents/                      # Specialized AI agents (v1)
│   │   ├── onboarding_agent.py
│   │   ├── contract_analyzer_agent.py
│   │   ├── disagreement_processor_agent.py
│   │   ├── changes_analyzer_agent.py
│   │   └── orchestrator_agent.py
│   │
│   ├── services/                    # Business logic
│   │   ├── llm_gateway.py           # Multi-model LLM gateway (6 providers)
│   │   ├── model_router.py          # Smart LLM cascade routing
│   │   ├── rag_system.py            # RAG with ChromaDB
│   │   ├── auth_service.py          # JWT auth + roles + demo access
│   │   ├── payment_service.py       # Subscription tiers
│   │   └── ...
│   │
│   ├── api/
│   │   ├── v1/                      # REST API v1 (64 endpoints)
│   │   └── v2/                      # REST API v2 (64 endpoints) — Phase 12
│   │
│   └── models/                      # SQLAlchemy models
│
├── frontend/                        # Next.js 14 React frontend
│   ├── src/
│   │   ├── app/                     # App Router pages (16 routes)
│   │   ├── components/              # React components
│   │   ├── hooks/                   # Custom hooks (React Query)
│   │   ├── services/                # API client
│   │   └── stores/                  # Zustand state management
│   └── e2e/                         # Playwright E2E tests (33 tests)
│
├── docker-compose.yml               # Production: 6 services
├── docker-compose.dev.yml           # Dev: postgres + redis
├── nginx/nginx.conf                 # Reverse proxy
└── tests/                           # Backend tests (387 tests)
```

---

## Возможности

### LLM Smart Routing

Мультимодельный каскад с автоматическим роутингом:

| Модель | Роль | Стоимость |
|--------|------|-----------|
| DeepSeek-V3 | Primary worker (90% задач) | $0.14/1M tokens |
| Claude Sonnet | Expert fallback (сложные задачи) | $3.00/1M tokens |
| GPT-4o | Reserve channel | $2.50/1M tokens |

### AI-Collaborative Features (Phase 12)

- **AI Workspace** — интерактивные AI-сессии с контекстом документа
- **Negotiation Engine** — AI-driven переговоры с генерацией возражений
- **Workflow Automation** — определения, исполнения, задачи с эскалацией
- **Template Governance** — версионирование шаблонов, clause policies
- **Organization Management** — мультитенантность, роли, политики
- **Tool & Agent Registry** — typed tools, agent capabilities
- **Webhook Integrations** — event bus, webhook deliveries с retry
- **Collaboration** — комментарии, аннотации, назначения

### Contract Management (v1)

- Загрузка и парсинг договоров (DOCX, PDF, XML)
- Глубокий анализ с выявлением рисков (financial, legal, operational)
- Генерация договоров по шаблонам с LLM
- Генерация возражений с правовыми обоснованиями
- Сравнение версий (структурное + семантическое)
- Экспорт в DOCX, PDF, TXT, JSON

### Authentication & Security

- JWT access + refresh tokens с bcrypt
- 5 ролей: admin, senior_lawyer, lawyer, junior_lawyer, demo
- 4 тарифа: demo, basic, pro, enterprise (с лимитами)
- Demo-доступ по уникальным ссылкам
- Rate limiting, security headers, audit logs
- Email verification, 2FA (TOTP)

### Frontend

- 16 страниц: dashboard, contracts, AI workspace, negotiations, workflow, admin и др.
- Real-time обновления через WebSocket
- Mobile-first responsive design
- Admin panel с 5 вкладками (пользователи, политики, инструменты, агенты, шаблоны)

---

## Технологический стек

| Слой | Технологии |
|------|-----------|
| **Backend** | Python 3.11, FastAPI, SQLAlchemy, Pydantic v2, Alembic |
| **Frontend** | Next.js 14 (App Router), TypeScript, Tailwind CSS, React Query, Zustand |
| **Database** | PostgreSQL 16 + pgvector / SQLite (dev) |
| **LLM** | DeepSeek-V3, Claude Sonnet, GPT-4o, GPT-4o-mini + Perplexity, Qwen |
| **Vector DB** | ChromaDB |
| **Cache** | Redis |
| **Infra** | Docker Compose (6 сервисов), Nginx, GitHub Actions |
| **Testing** | pytest (387 backend), Playwright (33 E2E) |

---

## Установка

### Требования

- Python 3.11+
- Node.js 18+
- PostgreSQL 16+ (или SQLite для dev)

### Локальная разработка

```bash
# 1. Клонирование
git clone https://github.com/Andrew821667/Contract-AI-System.git
cd Contract-AI-System

# 2. Backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 3. Frontend
cd frontend
npm install
cd ..

# 4. Конфигурация
cp .env.example .env
# Отредактируйте .env — минимально: DEEPSEEK_API_KEY или OPENAI_API_KEY

# 5. Dev-инфраструктура (PostgreSQL + Redis)
docker-compose -f docker-compose.dev.yml up -d

# 6. Запуск backend
uvicorn src.main:app --reload --host 0.0.0.0 --port 8000

# 7. Запуск frontend (в отдельном терминале)
cd frontend && npm run dev
```

Backend: http://localhost:8000 | Frontend: http://localhost:3000

---

## Docker Deployment

Полный production-стек из 6 сервисов:

```bash
# 1. Конфигурация
cp .env.example .env
# Заполните API ключи, пароли, SECRET_KEY

# 2. Запуск
docker-compose up -d --build

# 3. Проверка
docker-compose ps
curl http://localhost/health
```

### Сервисы

| Сервис | Порт | Описание |
|--------|------|----------|
| **postgres** | 5432 | PostgreSQL 16 + pgvector |
| **redis** | 6379 | Cache + sessions |
| **backend** | 8000 | FastAPI API (128 endpoints) |
| **streamlit** | 8501 | Admin dashboard (legacy) |
| **frontend** | 3000 | Next.js 14 UI |
| **nginx** | 80 | Reverse proxy + SSL termination |

Nginx маршрутизирует:
- `/api/*` и `/ws/*` → backend
- `/streamlit/*` → streamlit
- `/*` → frontend

---

## Тестирование

### Backend (pytest)

```bash
source venv/bin/activate

# Все тесты
python3 -m pytest tests/ -q

# С verbose
python3 -m pytest tests/ -v

# Конкретный файл
python3 -m pytest tests/test_api_auth.py -v
```

**Результат:** 387 passed, 4 skipped

### Frontend E2E (Playwright)

```bash
cd frontend

# Установка браузеров
npx playwright install chromium

# Запуск тестов
npm run test:e2e

# С UI
npm run test:e2e:ui

# Отчёт
npm run test:e2e:report
```

**Результат:** 33/33 passed (6 spec files)

Покрытие E2E:
- Публичные страницы и редиректы авторизации
- Форма логина и auth flow
- Dashboard и навигация
- Управление контрактами (список, загрузка, генерация)
- Phase 12 страницы (AI, переговоры, workflow, admin)
- Template Governance UI (политики, версии шаблонов)

---

## API

128 endpoints: 64 v1 + 64 v2

### V1 — Contract Management

```
POST   /api/v1/auth/login              # Аутентификация
POST   /api/v1/auth/register           # Регистрация
POST   /api/v1/contracts/upload        # Загрузка договора
POST   /api/v1/contracts/analyze       # Анализ
POST   /api/v1/contracts/generate      # Генерация
GET    /api/v1/contracts/{id}          # Детали
GET    /api/v1/analytics/dashboard     # Аналитика
WS     /api/v1/ws/analysis/{id}       # Real-time анализ
WS     /api/v1/ws/notifications       # Уведомления
```

### V2 — AI-Collaborative OS

```
# AI Collaboration
POST   /api/v2/documents/{id}/ai/sessions          # Создать AI-сессию
POST   /api/v2/ai/sessions/{id}/messages            # Отправить сообщение
POST   /api/v2/ai/actions/{id}/approve              # Одобрить AI action

# Negotiations
POST   /api/v2/negotiations/start                   # Начать переговоры
POST   /api/v2/negotiations/objections/generate     # Генерация возражений

# Workflow
POST   /api/v2/workflow/definitions                 # Создать workflow
POST   /api/v2/workflow/tasks/{id}/complete          # Завершить задачу

# Template Governance
GET    /api/v2/templates/{id}/versions              # Версии шаблона
POST   /api/v2/clause-policies                      # Создать политику клауз
GET    /api/v2/clause-policies/check                # Проверка клаузы

# Organizations & Policies
POST   /api/v2/organizations                        # Создать организацию
POST   /api/v2/policies                             # Создать политику

# Integrations
POST   /api/v2/integrations/webhooks               # Создать webhook
```

---

## Roadmap

### Completed

- [x] **Phases 1-8**: Security, rate limiting, export, tests, modular architecture, performance
- [x] **Phase 9**: Auth system (JWT, roles, demo access, 2FA)
- [x] **Phase 10**: React/Next.js frontend (16 pages, WebSocket)
- [x] **Phase 11**: Analytics dashboard, cost tracking
- [x] **Phase 12**: AI-collaborative OS core (13 sub-modules, 64 v2 endpoints)
  - Identity & organizations, policy engine, tool/agent registry
  - AI collaboration sessions, orchestrator, workflow engine
  - Negotiation engine, template governance, integrations
  - Collaboration (comments/annotations), enterprise integrity
- [x] **Template Governance UI** (admin panel)
- [x] **E2E test suite** (33 Playwright tests)
- [x] **Docker production stack** (6 services)

### In Progress

- [ ] Production deployment и мониторинг
- [ ] CI/CD pipeline (GitHub Actions)
- [ ] API documentation (OpenAPI/Swagger)

### Future

- [ ] Fine-tuned модели для типов договоров
- [ ] Multi-language support
- [ ] Mobile app
- [ ] SSO интеграция (SAML/OIDC)
- [ ] Audit trail UI

---

## Автор

**Andrew821667** — [@Andrew821667](https://github.com/Andrew821667)

---

## Лицензия

MIT License — см. [LICENSE](LICENSE)
