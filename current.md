# Contract AI System — Текущее состояние проекта

**Последнее обновление:** 2026-03-15
**Статус:** Stage 3.5 — Scheduler + Admin Auth + Users ✅

---

## КРИТИЧЕСКИ ВАЖНО ДЛЯ НОВОГО АГЕНТА

### Архитектура: 3 сервиса

Система работает на **трёх** независимых сервисах. **ВСЕ ТРИ** должны быть запущены:

| Сервис | Порт | Технология | Назначение |
|--------|------|------------|------------|
| **FastAPI бэкенд** | 8000 | Python/uvicorn | API, авторизация, БД, LLM |
| **Next.js фронтенд** | 3000 | Node.js/Next.js 14 | Основной UI для пользователей |
| **Streamlit админка** | 8502 | Python/Streamlit | Внутренний инструмент (анализ, метрики) |

**ФРОНТЕНД — ТОЛЬКО Next.js!** Старый Streamlit UI (`_app_streamlit_legacy.py`) — DEPRECATED. НЕ ИСПОЛЬЗУЙ `app.py` как UI. Streamlit используется ТОЛЬКО для админки.

### Порядок запуска (СТРОГО!)

```bash
cd ~/Desktop/Contract-AI-System-
source venv/bin/activate

# 1. СНАЧАЛА бэкенд (без него логин не работает!)
python3 -m uvicorn src.main:app --host 0.0.0.0 --port 8000

# 2. Фронтенд (в отдельном терминале)
cd frontend && npm run dev

# 3. Админка (в отдельном терминале)
cd ~/Desktop/Contract-AI-System-
streamlit run admin/streamlit_dashboard.py --server.port=8502
```

### Критические грабли (уроки 2026-03-15)

1. **SECRET_KEY в .env ОБЯЗАТЕЛЕН!** Если пустой — JWT токены не работают → логин падает молча.
   ```
   SECRET_KEY=gYPs9IPFp3lNs5d3e0u_yuEbMqcdofDJUsGq1Qmc0KE
   ```
   Генерация: `python3 -c "import secrets; print(secrets.token_urlsafe(32))"`

2. **FastAPI бэкенд ОБЯЗАТЕЛЕН для логина!** Next.js фронтенд шлёт POST на `localhost:8000/api/v1/auth/login`. Без бэкенда — "Неверный email или пароль".

3. **Зависимости бэкенда могут отсутствовать** в venv. При запуске `uvicorn src.main:app` проверяй ошибки:
   - `sse-starlette` — `pip install sse-starlette`
   - `pypdf` — `pip install pypdf`

4. **Git: битая ветка `refs/heads/main 2`** — если fetch/pull падает с `bad object refs/heads/main 2`:
   ```bash
   rm -f ".git/refs/heads/main 2"
   git fetch origin
   ```

5. **Пользователи живут в SQLite** (`contract_ai.db`, таблица `users`). Если БД пересоздана — пользователей нет. Нужно создать заново (см. раздел "Учётные записи").

6. **Next.js кеш** — после изменений перезапускай фронт:
   ```bash
   rm -rf frontend/.next/cache
   cd frontend && npm run dev
   ```

7. **Streamlit multipage**: `admin/streamlit_dashboard.py` — главная, страницы в `admin/pages/`. Каждая page — standalone с `st.set_page_config()`.

8. **Пользователь общается по-русски** и ожидает русские ответы.

9. **Весь UI на русском языке!**

10. **Python 3.11** на текущей машине (`/opt/homebrew/Cellar/python@3.11`). Используй `python3`, НЕ `python`.

---

## Учётные записи системы

| Email | Роль | Пароль | Доступ |
|-------|------|--------|--------|
| admin@contractai.ru | admin | Admin123! | Next.js + Админка |
| lawyer@contractai.ru | lawyer | Lawyer123! | Только Next.js |
| vip@contractai.ru | senior_lawyer | Vip12345! | Next.js + Админка |
| demo@contractai.ru | demo | Demo1234! | Только Next.js |

- При первом входе в Next.js — модалка смены пароля (`ChangePasswordModal`)
- Админка Streamlit: только `admin` и `senior_lawyer`
- Пароли хешируются bcrypt, общая БД для обоих интерфейсов

### Создание пользователей (если БД пустая)

```python
python3 << 'EOF'
import sys; sys.path.insert(0, '.')
from src.models.database import SessionLocal
from src.models.auth_models import User
from src.services.auth_service import AuthService

db = SessionLocal()
auth = AuthService(db)

users = [
    ("admin@contractai.ru", "Администратор", "Admin123!", "admin", "enterprise"),
    ("lawyer@contractai.ru", "Юрист", "Lawyer123!", "lawyer", "pro"),
    ("vip@contractai.ru", "VIP Юрист", "Vip12345!", "senior_lawyer", "enterprise"),
    ("demo@contractai.ru", "Демо пользователь", "Demo1234!", "demo", "demo"),
]
for email, name, pwd, role, tier in users:
    user = User(email=email, name=name, password_hash=auth.hash_password(pwd),
                role=role, subscription_tier=tier, email_verified=True, active=True,
                is_demo=(role == "demo"))
    db.add(user)
db.commit(); db.close()
EOF
```

---

## Структура проекта

```
Contract-AI-System-/
├── .env                                    # API ключи + SECRET_KEY (НЕ в git!)
├── current.md                              # ЭТОТ ФАЙЛ — читай ПЕРВЫМ!
├── config/settings.py                      # Pydantic Settings
│
├── src/                                    # Python бэкенд
│   ├── main.py                             # FastAPI app (порт 8000)
│   ├── api/                                # API роуты (auth, contracts, etc.)
│   │   └── auth/routes.py                  # Login, register, change-password
│   ├── services/
│   │   ├── auth_service.py                 # JWT + bcrypt + session management
│   │   ├── document_processor.py           # Оркестратор пайплайна (6 этапов)
│   │   ├── text_extractor.py               # Извлечение текста + DOCX конвертация
│   │   ├── llm_extractor.py                # LLM extraction (DeepSeek/OpenAI)
│   │   ├── scheduler_service.py            # APScheduler — фоновые задачи
│   │   ├── knowledge_base_service.py       # CRUD для базы знаний (RAG)
│   │   ├── template_comparator.py          # Сравнение с шаблоном
│   │   ├── risk_scorer.py                  # Risk scoring 0-100
│   │   ├── stage2_document_generator.py    # Генерация DOCX + протокол
│   │   ├── complexity_scorer.py            # Оценка сложности документа
│   │   └── model_router.py                 # Smart Router (выбор LLM модели)
│   └── models/
│       ├── database.py                     # SQLAlchemy модели (ScheduledTaskLog, LegalDocument, etc.)
│       └── auth_models.py                  # User, UserSession, DemoToken, AuditLog
│
├── frontend/                               # Next.js 14 фронтенд (порт 3000)
│   ├── src/app/
│   │   ├── login/page.tsx                  # Страница логина
│   │   ├── dashboard/page.tsx              # Dashboard + ChangePasswordModal
│   │   ├── contracts/                      # Договоры (upload, generate, [id])
│   │   └── clauses/                        # Библиотека клаузул
│   ├── src/services/api.ts                 # API клиент (baseURL: localhost:8000)
│   ├── src/components/ChangePasswordModal.tsx  # Смена пароля при первом входе
│   ├── next.config.js                      # Proxy /api/* → localhost:8000
│   └── public/direct-access.html           # Обход логина (для отладки)
│
├── admin/                                  # Streamlit админка (порт 8502)
│   ├── streamlit_dashboard.py              # Главная страница (защищена auth)
│   ├── shared/
│   │   ├── session_helpers.py              # check_admin_auth(), show_admin_sidebar_user()
│   │   └── ui_components.py                # Общие компоненты UI
│   └── pages/
│       ├── 0_Test_Infrastructure.py        # Тесты инфраструктуры
│       ├── 1_Process_Documents.py          # "Стеклянный ящик" — анализ документов
│       ├── 2_Generate_Contract.py          # Генерация договоров
│       ├── 3_Model_Metrics.py              # Метрики Smart Router
│       ├── 4_Disagreement_Protocol.py      # Протокол разногласий
│       ├── 5_Contract_Library.py           # Библиотека договоров
│       └── 6_Scheduler.py                  # Планировщик фоновых задач
│
├── _app_streamlit_legacy.py                # DEPRECATED: старый Streamlit UI
├── _app_pages_legacy.py                    # DEPRECATED: старые страницы Streamlit
│
├── alembic/                                # Миграции БД
├── tests/                                  # Тесты (pytest)
└── CONTRACT_AI_SYSTEM_SPECIFICATION.md     # Полная спецификация
```

---

## .env (ключевые переменные)

```
DATABASE_URL=sqlite:///./contract_ai.db
SECRET_KEY=<ОБЯЗАТЕЛЬНО! Генерируй через secrets.token_urlsafe(32)>
DEEPSEEK_API_KEY=<ключ>
DEEPSEEK_BASE_URL=https://api.deepseek.com/v1
DEEPSEEK_MODEL=deepseek-chat
```

---

## Технический стек

- **Фронтенд:** Next.js 14, React 18, TypeScript, Tailwind CSS, Zustand, React Query
- **Бэкенд:** FastAPI, SQLAlchemy, Pydantic v2, uvicorn
- **Админка:** Streamlit (multipage)
- **БД:** SQLite (dev) / PostgreSQL 16+ (prod)
- **LLM:** DeepSeek-chat (основной), GPT-4o-mini (fallback), Claude (будущее)
- **Auth:** JWT (HS256) + bcrypt, 60-мин access token, 30-дней refresh
- **Scheduler:** APScheduler 3.10.4
- **NLP:** SpaCy (ru_core_news_sm)

---

## Прогресс

| Этап | Статус | Описание |
|------|--------|----------|
| Stage 2.1: Загрузка черновиков | ✅ | PDF/DOCX/TXT/HTML/XML → конвертация в DOCX |
| Stage 2.2: Сравнение с шаблоном | ✅ | template_comparator.py, LLM-сравнение |
| Stage 2.3: Risk Scoring | ✅ | risk_scorer.py, rule-based 0-100 |
| Stage 2.4: Генерация документа | ✅ | Исправленный DOCX + протокол разногласий |
| Stage 3: Smart Router | ✅ | complexity_scorer + model_router + multi-model |
| Stage 3.5: Scheduler + Auth | ✅ | APScheduler, admin auth, 4 пользователя |
| Stage 4: Интеграции | ❌ | pgvector, 1C/ERP, расширение Next.js UI |

---

## Известные проблемы

| Проблема | Решение |
|----------|---------|
| RAG отключён | Нужен PostgreSQL + pgvector |
| PaddleOCR не установлен | OCR не нужен для TXT/DOCX/PDF с текстом |
| pdf2docx падает на сложных PDF | Fallback на text_to_docx |
| Только DeepSeek API key | Claude и GPT-4o — добавить ключи в .env |
| starlette version mismatch | fastapi 0.109.2 vs starlette 0.52.1 — работает, но warning |
