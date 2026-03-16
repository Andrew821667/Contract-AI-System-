# Contract AI System

**Статус:** Phase 0 — Архитектурная трансформация
**Обновлено:** 2026-03-16

---

## ВАЖНО: Читай current.md и DEVELOPMENT_PLAN.md ПЕРВЫМ!

- `current.md` — полное состояние проекта, план разработки, что переиспользуем
- `DEVELOPMENT_PLAN.md` — ERD, интерфейсы, API contracts, структура модулей, user flows

---

## Что мы строим

**AI-collaborative contract operating system** — НЕ простой анализатор договоров.

### Архитектурная формула
```
hierarchical LLM cascade + AI collaborator layer + agent orchestrator layer
+ specialized agents + controlled tool ecosystem + user/org-aware policy system
+ standalone/branch-ready contract domain
```

### Референс
**OpenClaw** (github.com/openclaw/openclaw) — ментальная модель:
- Session isolation, typed tools (Skills), deterministic orchestration (Lobster)
- **"Don't orchestrate with LLMs. Use them for creative work, use code for plumbing."**

### Принципы (НАРУШАТЬ НЕЛЬЗЯ)
1. **AI-first** — AI в каждом этапе lifecycle документа
2. **Policy-first** — ни один AI action без policy check + audit
3. **Tool-first** — оркестратор через tools/agents, никогда напрямую
4. **Deterministic orchestration** — планы детерминированные, LLM для creative work
5. **Org/user-aware** — AI ведёт себя по-разному для разных пользователей/ролей
6. **Branch-ready** — standalone + embedded mode

---

## Текущая фаза: Phase 0

Создание архитектурного каркаса в `src/core/` — НЕ ломая существующий код.

Новый код: `src/core/` (13 подмодулей)
Новые API: `/api/v2/` (рядом с существующим v1)
Миграции: backward-compatible (новые таблицы, старые не трогаем)

---

## Стек

- **Backend:** FastAPI, SQLAlchemy, Pydantic v2, Python 3.11 (`python3`)
- **Frontend:** Next.js 14, React 18, TypeScript, Tailwind CSS, Zustand
- **DB:** SQLite (dev) / PostgreSQL 16 + pgvector (prod)
- **LLM:** DeepSeek (primary), Claude (expert), GPT-4o (fallback), + 3 more
- **Infra:** Docker Compose (6 services), Nginx, Redis, GitHub Actions

---

## Ключевые файлы

| Файл | Назначение |
|------|------------|
| `current.md` | **Полное состояние + план** — ЧИТАЙ ПЕРВЫМ |
| `DEVELOPMENT_PLAN.md` | ERD, интерфейсы, API, структура, flows |
| `src/core/` | **НОВОЕ** — ядро AI-collaborative OS |
| `src/api/v2/` | **НОВОЕ** — API v2 для новых доменов |
| `src/api/dependencies.py` | Единый `get_current_user` (НЕ дублировать!) |
| `src/services/llm_gateway.py` | LLM Gateway (6 провайдеров) |
| `src/services/model_router.py` | LLM cascade routing |
| `src/agents/` | Существующие агенты (→ рефакторинг в registry) |
| `config/settings.py` | Pydantic Settings |

---

## Правила разработки

1. **UI и коммуникация на русском языке**
2. **Python 3.11** — `python3`, НЕ `python`
3. **Новый код в `src/core/`** — не ломай существующий `src/services/`
4. **API v2 рядом с v1** — backward-compatible
5. **Policy-first** — любой AI action через policy + audit
6. **`get_current_user`** — только из `src/api/dependencies.py`
7. **.env не в git**, SECRET_KEY обязателен
