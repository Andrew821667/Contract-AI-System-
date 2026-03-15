# Contract AI System

**Статус:** Stage 3.5 — Scheduler + Admin Auth + Users
**Обновлено:** 2026-03-15

---

## ВАЖНО: Читай current.md ПЕРВЫМ!

`current.md` содержит актуальное состояние проекта, все грабли и уроки.
Этот файл (CLAUDE.md) — краткая справка для быстрого старта.

---

## Архитектура: 3 сервиса

| Сервис | Порт | Технология |
|--------|------|------------|
| **FastAPI бэкенд** | 8000 | Python/uvicorn |
| **Next.js фронтенд** | 3000 | Node.js/Next.js 14 |
| **Streamlit админка** | 8502 | Python/Streamlit |

**ФРОНТЕНД = Next.js!** Streamlit используется ТОЛЬКО для админки.
Файлы `_app_streamlit_legacy.py` и `_app_pages_legacy.py` — DEPRECATED.

---

## Запуск

```bash
cd ~/Desktop/Contract-AI-System-
source venv/bin/activate

# 1. Бэкенд (ОБЯЗАТЕЛЕН для логина!)
python3 -m uvicorn src.main:app --host 0.0.0.0 --port 8000

# 2. Фронтенд (отдельный терминал)
cd frontend && npm run dev

# 3. Админка (отдельный терминал)
cd ~/Desktop/Contract-AI-System-
streamlit run admin/streamlit_dashboard.py --server.port=8502
```

---

## Стек

- **Frontend:** Next.js 14, React 18, TypeScript, Tailwind CSS, Zustand
- **Backend:** FastAPI, SQLAlchemy, Pydantic v2, uvicorn
- **Admin:** Streamlit multipage
- **DB:** SQLite (dev) / PostgreSQL 16+ (prod)
- **LLM:** DeepSeek-chat (основной), GPT-4o-mini (fallback)
- **Auth:** JWT (HS256) + bcrypt
- **Scheduler:** APScheduler 3.10.4
- **Python:** 3.11 (используй `python3`, НЕ `python`)

---

## Ключевые файлы

| Файл | Назначение |
|------|------------|
| `current.md` | Полное состояние проекта — **ЧИТАЙ ПЕРВЫМ** |
| `src/main.py` | FastAPI приложение |
| `src/api/dependencies.py` | Единый `get_current_user` (НЕ дублировать!) |
| `src/api/auth/routes.py` | Login, register, change-password |
| `src/services/auth_service.py` | JWT + bcrypt + sessions |
| `src/models/database.py` | SQLAlchemy модели + engine + SessionLocal |
| `src/models/auth_models.py` | User, UserSession, AuditLog |
| `config/settings.py` | Pydantic Settings (SECRET_KEY, API keys) |
| `frontend/src/services/api.ts` | API клиент Next.js |
| `admin/streamlit_dashboard.py` | Главная страница админки |

---

## Учётные записи

| Email | Роль | Пароль |
|-------|------|--------|
| admin@contractai.ru | admin | Admin123! |
| lawyer@contractai.ru | lawyer | Lawyer123! |
| vip@contractai.ru | senior_lawyer | Vip12345! |
| demo@contractai.ru | demo | Demo1234! |

---

## Правила разработки

1. **UI на русском языке** — все интерфейсы и сообщения
2. **Пользователь общается по-русски**
3. **SECRET_KEY в .env обязателен** — без него JWT не работает
4. **`get_current_user`** — только из `src/api/dependencies.py`, НЕ дублировать
5. **Регистрация** — роль всегда `junior_lawyer`, НЕ принимать из клиента
6. **CORS** — только конкретные origins, НЕ wildcard `*`
7. **.env не в git** (есть в .gitignore)
