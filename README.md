# Contract AI System

**AI-collaborative contract operating system** — платформа интеллектуальной работы с договорами, где AI является центральным участником каждого этапа: от анализа и проверки рисков до согласования и переговоров.

[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104+-green.svg)](https://fastapi.tiangolo.com/)
[![Next.js](https://img.shields.io/badge/Next.js-14-black.svg)](https://nextjs.org/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16+pgvector-blue.svg)](https://www.postgresql.org/)
[![Docker](https://img.shields.io/badge/Docker-Compose-2496ED.svg)](https://docs.docker.com/compose/)
[![CI](https://img.shields.io/badge/CI-GitHub_Actions-green.svg)]()
[![Tests](https://img.shields.io/badge/Tests-430+-brightgreen.svg)]()

---

## Что это

Contract AI System — не очередной «чатбот рядом с документом». Это полноценная операционная система для договорной работы, в которой AI встроен в каждый этап жизненного цикла документа.

**Ключевая идея:** юрист получает не просто подсветку рисков, а готовый разбор всего договора с учётом стандартов компании, правового контекста и баланса интересов сторон.

### Для кого

| Роль | Что получает |
|------|-------------|
| **Юрист** | Полный анализ договора за минуты вместо часов; проверка на соответствие стандартам компании; рекомендации по правкам |
| **Руководитель** | Прозрачные риски по каждому договору; контроль SLA согласования; аналитика портфеля |
| **Бизнес** | Сокращение цикла согласования; единые стандарты проверки; масштабирование без найма |

---

## Возможности

### Полнотекстовый AI-анализ договоров

Двухпроходный анализ: сначала весь текст договора целиком (выявление системных рисков и взаимосвязей), затем детальный разбор каждого пункта.

- Полный текст договора отправляется в LLM без обрезки (типичный договор 10-60К символов — менее 25% контекста модели)
- Выявление рисков: финансовые, юридические, операционные, compliance
- Проверка соответствия стандартам компании
- Оценка баланса прав и обязанностей сторон
- Прогноз вероятности споров
- Генерация рекомендаций с привязкой к конкретным стандартам

### Стандарты компании (Company Policies)

Пользователь задаёт типовые условия своей компании (11 категорий: финансовые, сроки, ответственность, конфиденциальность и др.). При анализе каждого договора система автоматически сравнивает пункты с этими стандартами.

### RAG — база знаний

- Загрузка документов: законы, судебная практика, внутренние регламенты
- Автоматическая индексация каждого проанализированного договора
- Поиск релевантного правового контекста при анализе
- ChromaDB для векторного поиска

### Мультимодельный LLM-каскад

| Модель | Роль | Контекст |
|--------|------|----------|
| DeepSeek-V3 | Primary (90% задач) | 128K токенов |
| Claude | Expert fallback | 200K токенов |
| GPT-4o | Reserve | 128K токенов |
| Gemini | Extended context | 1M токенов |
| Qwen, Perplexity, Yandex | Специализированные задачи | — |

Circuit breaker (3 сбоя / 5 мин), 4 fallback-режима, автоматический роутинг по сложности задачи.

### Агентный оркестратор

Центральный компонент системы — детерминированный оркестратор, который управляет всем жизненным циклом работы с документом через специализированных агентов и инструменты.

**Как работает:**

1. Пользователь формулирует цель (через AI-сессию или API): _«Подготовь договор к согласованию»_
2. Оркестратор подбирает шаблон плана (7 встроенных шаблонов: полный анализ, генерация, переговоры, сравнение версий, compliance и др.)
3. План декомпозируется в последовательность шагов: вызовы инструментов, делегирование агентам, точки одобрения, условные переходы
4. Каждый шаг выполняется с policy-проверкой и аудитом
5. На критических этапах — пауза для одобрения юристом (approval checkpoint)

**Принцип:** планирование детерминированное (код, не LLM), AI используется только для творческой работы внутри агентов.

**Специализированные агенты (7):**

| Агент | Специализация | Примеры задач |
|-------|--------------|---------------|
| Contract Analyzer | Анализ | Риски, compliance, оценка |
| Contract Generator | Генерация | Создание по шаблону, заполнение |
| Disagreement Analyzer | Переговоры | Протоколы разногласий, возражения |
| Changes Analyzer | Сравнение | Diff версий, отслеживание правок |
| Onboarding Agent | Приём | Классификация, intake документов |
| Quick Export | Экспорт | DOCX, PDF, JSON |
| Orchestrator | Координация | Мета-управление пайплайном |

**Инструменты (16+ tool-адаптеров):** парсер документов, экстрактор клауз, скоринг рисков, RAG-поиск, генератор, diff-движок, composer позиций, библиотека клауз, валидатор и др.

**Расширяемость:**
- Все агенты и инструменты работают через единые протоколы (`IAgent`, `ITool`)
- Подключение внешних агентов — через реализацию протокола или обёртку `BaseAgentAdapter` с регистрацией в runtime
- Агенты могут делегировать задачи друг другу (agent→agent delegation) и вызывать инструменты
- Каждый вызов проходит через policy engine и записывается в audit trail

```
Пользователь → Цель → Оркестратор → План
                                       ├── tool: парсер → текст
                                       ├── tool: клаузулы → структура
                                       ├── agent: анализатор → риски
                                       ├── condition: риск HIGH?
                                       ├── checkpoint: одобрение юриста
                                       └── tool: RAG → прецеденты
```

### AI-Collaborative Workspace

14 архитектурных слоёв, каждый на 90-95% готовности:

- **AI Panel** — интерактивные сессии: чат, план действий, быстрые команды
- **Negotiation Engine** — AI-driven переговоры с генерацией возражений
- **Workflow Engine** — маршрутизация, SLA, эскалация, AI-triggered routing
- **Template Governance** — версионирование шаблонов, clause policies
- **Collaboration** — комментарии, потоки, упоминания, якоря в тексте
- **Organization Management** — мультитенантность, роли, policy engine
- **Webhook Integrations** — 20 типов событий, retry с backoff
- **Audit & Compliance** — полный аудит AI-действий, integrity verification

### Bridge API — интеграция с внешними системами

REST API для бесшовной интеграции (используется [Legal AI Platform](https://github.com/Andrew821667/legal-ai-platform)):

| Endpoint | Назначение |
|----------|-----------|
| `GET /api/v1/bridge/status` | Режим работы (online/busy/offline), capabilities |
| `POST /api/v1/bridge/analyze` | Отправка файла на анализ |
| `GET /api/v1/bridge/progress/{job_id}` | Прогресс анализа (%, сообщение) |
| `GET /api/v1/bridge/result/{job_id}` | Полные результаты |
| `GET /api/v1/bridge/result/{job_id}/summary` | Краткий отчёт (для Telegram, до 4096 символов) |
| `GET /api/v1/bridge/result/{job_id}/pdf` | PDF-отчёт |
| `POST /api/v1/auth/sso-token` | SSO-токен для бесшовного входа |

Аутентификация: shared secret через `X-Bridge-Secret` header.

### Безопасность

- JWT access + refresh tokens, bcrypt, session management
- 5 ролей: admin, senior_lawyer, lawyer, junior_lawyer, demo
- Atomic SQL UPDATE для login attempts, pessimistic locking для demo tokens
- Token theft detection, password reset через SHA-256 hash
- Anti-enumeration (без ID в 404), rate limiting, security headers
- 89 тестов auth/admin/upload + 74 core-тестов

---

## Технологический стек

| Слой | Технологии |
|------|-----------|
| **Backend** | Python 3.11, FastAPI, SQLAlchemy, Pydantic v2, Alembic |
| **Frontend** | Next.js 14 (App Router), TypeScript, Tailwind CSS, Zustand |
| **Database** | PostgreSQL 16 + pgvector |
| **Vector DB** | ChromaDB |
| **LLM** | DeepSeek, Claude, GPT-4o, Gemini, Qwen, Perplexity, Yandex |
| **Cache** | Redis 7 |
| **Infra** | Docker Compose (6 сервисов), Nginx, GitHub Actions CI/CD |
| **Testing** | pytest (~430+ тестов), Playwright (33 E2E) |

---

## Быстрый старт

### Docker (рекомендуется)

```bash
cp .env.example .env
# Заполните: DEEPSEEK_API_KEY, SECRET_KEY, пароли

docker compose up -d --build
# http://localhost — через Nginx
```

### Локально (dev)

```bash
# Backend
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
python3 -m uvicorn src.main:app --host 0.0.0.0 --port 8000

# Frontend (отдельный терминал)
cd frontend && npm install && npm run dev
```

### Docker-сервисы

| Сервис | Описание |
|--------|----------|
| **postgres** | PostgreSQL 16 + pgvector |
| **redis** | Cache + sessions |
| **backend** | FastAPI (128 endpoints) |
| **frontend** | Next.js 14 |
| **streamlit** | Admin dashboard |
| **nginx** | Reverse proxy |

---

## Тестирование

```bash
# Backend
python3 -m pytest tests/ -q          # ~430+ тестов

# Frontend E2E
cd frontend && npm run test:e2e      # 33 Playwright-теста
```

---

## Архитектура

```
Contract-AI-System/
├── src/
│   ├── core/                    # AI-collaborative OS (13 подмодулей)
│   │   ├── identity_org/        # Организации, пользователи, роли
│   │   ├── policies/            # Policy engine
│   │   ├── tools/               # Tool registry (16 адаптеров)
│   │   ├── agents/              # Agent registry (7 агентов)
│   │   ├── ai_collaboration/    # AI-сессии, контекст, действия
│   │   ├── orchestrator/        # Deterministic orchestration
│   │   ├── workflow/            # Workflow engine + SLA
│   │   ├── collaboration/       # Комментарии, аннотации
│   │   ├── templates/           # Template governance
│   │   ├── negotiation/         # Negotiation engine
│   │   ├── integrations/        # Webhooks + event bus
│   │   └── enterprise/          # Integrity, branch mode
│   ├── agents/                  # Specialized AI agents
│   ├── services/                # Business logic + LLM gateway
│   ├── api/
│   │   ├── v1/                  # REST API v1 (64 endpoints)
│   │   ├── v2/                  # REST API v2 (64 endpoints)
│   │   └── bridge/              # Bridge API (интеграция)
│   └── models/                  # SQLAlchemy (37 таблиц)
├── frontend/                    # Next.js 14 (16 страниц)
├── admin/                       # Streamlit admin (RAG, клаузулы)
├── config/                      # Pydantic Settings
├── docker-compose.yml           # Production stack
├── .github/workflows/ci.yml     # CI: lint + test + docker
└── tests/                       # Backend tests
```

---

## Связанные проекты

- **[Legal AI Platform](https://github.com/Andrew821667/legal-ai-platform)** — платформа лидогенерации и маркетинга. Использует Bridge API для интеграции анализа договоров в Telegram-бот и веб-сайт.

---

## Автор

**Андрей Попов** — юрист (24 года практики) и разработчик AI-систем для автоматизации юридической работы.

- GitHub: [@Andrew821667](https://github.com/Andrew821667)
- Специализация: договоры, M&A, банкротства, земельное право, ВЭД

---

## Лицензия

MIT License — см. [LICENSE](LICENSE)
