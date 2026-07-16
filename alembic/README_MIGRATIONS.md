# Database Migrations - Contract AI System v2.0

Этот каталог содержит миграции базы данных для Contract AI System v2.0 с архитектурой Multi-Model Routing и RAG.

## 📋 Список миграций

### 001_create_idp_tables.py (Базовые таблицы)
**Создано:** 2026-01-08
**Статус:** ✅ Существующая миграция

**Таблицы:**
1. `contracts_core` - Центральная таблица договоров (Hybrid Star Schema)
2. `contract_parties` - Стороны договора
3. `contract_items` - Спецификация (позиции договора)
4. `payment_schedule` - График платежей
5. `contract_rules` - Правила и формулы (Executable Logic)
6. `idp_extraction_log` - Лог обработки IDP
7. `idp_quality_issues` - Проблемы качества IDP

**Особенности:**
- JSONB поля для гибкости (`attributes`, `raw_data`, `formula`)
- GIN индексы для JSONB
- CHECK constraints для валидации
- CASCADE удаление связанных записей

---

### 002_pgvector.py (Векторное расширение)
**Создано:** 2026-01-09
**Статус:** ✅ Новая миграция v2.0

**Изменения:**
- Включение расширения `vector` для PostgreSQL
- Добавление колонки `embedding` в `contracts_core` (ARRAY of Float)
- Создание IVFFlat индекса для векторного поиска (cosine similarity)

**Зачем:**
- Семантический поиск похожих договоров
- RAG (Retrieval-Augmented Generation)
- Recommendations Engine

---

### 003_negotiation_tables.py (Pre-Execution)
**Создано:** 2026-01-09
**Статус:** ✅ Новая миграция v2.0

**Таблицы:**
1. `negotiation_sessions` - Сессии анализа черновиков
   - Статусы: `analyzing`, `awaiting_approval`, `approved`, `rejected`, `archived`
   - Поля: `risk_score`, `ai_recommendations` (JSONB)
   - Метрики: `processed_by_model`, `processing_time_ms`, `cost_usd`

2. `disagreements` - Протокол разногласий
   - Поля: `their_clause`, `our_standard`, `suggested_wording`
   - Риск: `risk_level` (critical/high/medium/low)
   - **НОВОЕ v2.1:** `ai_recommendation`, `precedents` (JSONB), `user_approved`

**Зачем:**
- Анализ черновиков (Pre-Execution Mode)
- Генерация протокола разногласий
- Одобрение пользователем (Human-in-the-Loop)

---

### 004_system_tables.py (Конфигурация системы)
**Создано:** 2026-01-09
**Статус:** ✅ Новая миграция v2.0

**Таблицы:**
1. `system_config` - Конфигурация системы
   - Режимы работы: `full_load`, `sequential`, `manual`
   - Включенные модули: `ocr`, `level1_extraction`, `llm_extraction`, `rag_filter`
   - Настройки RAG: `top_k`, `similarity_threshold`
   - Настройки Router: `default_model`, `complexity_threshold`

2. `user_approvals` - Отслеживание одобрений
   - Типы: `negotiation`, `extraction`, `protocol`, `digitization`, `amendment`
   - Статусы: `pending`, `approved`, `rejected`, `cancelled`
   - Поле `data_preview` (JSONB) для превью данных

**Зачем:**
- Управление режимами работы системы через UI
- Human-in-the-Loop для всех критичных операций
- Аудит всех одобрений

**Дефолтные значения:**
```json
{
  "system_mode": {"mode": "full_load"},
  "enabled_modules": {"modules": ["ocr", "level1_extraction", ...]},
  "rag_enabled": {"enabled": true, "top_k": 5},
  "router_config": {"default_model": "deepseek-v3", "complexity_threshold": 0.8}
}
```

---

### 005_knowledge_base.py (RAG)
**Создано:** 2026-01-09
**Статус:** ✅ Новая миграция v2.0

**Таблица:**
1. `knowledge_base` - База знаний для RAG
   - Типы: `best_practice`, `regulation`, `precedent`, `template_clause`, `risk_pattern`, `negotiation_tactic`
   - Поле `embedding` для векторного поиска
   - Метаданные (JSONB): категория, применимость, success_rate
   - Статистика: `usage_count`, `last_used_at`

**Примеры данных:**
- Ограничение ответственности в договорах поставки
- Иностранная подсудность (риск)
- Компромисс по условиям предоплаты
- Стандартная формулировка штрафа

**Зачем:**
- RAG на каждом этапе обработки
- Контекстные рекомендации
- Поиск прецедентов

---

### 006_llm_metrics.py (Метрики LLM)
**Создано:** 2026-01-09
**Статус:** ✅ Новая миграция v2.0

**Таблица:**
1. `llm_usage_metrics` - Метрики использования LLM моделей
   - Модели: `deepseek-v3`, `claude-4-5-sonnet`, `gpt-4o`, `gpt-4o-mini`
   - Метрики: `tokens_input`, `tokens_output`, `cost_usd`, `processing_time_sec`
   - Оценка: `complexity_score`, `confidence_score`
   - RAG: `rag_used`, `rag_docs_retrieved`

**Зачем:**
- Отслеживание стоимости по моделям
- A/B тестирование моделей
- Веб-панель метрик
- Оптимизация Router (complexity_threshold)

---

## 🚀 Применение миграций

### Вариант 1: Скрипт
```bash
./scripts/apply_migrations.sh
```

### Вариант 2: Напрямую через Alembic
```bash
# Посмотреть текущий статус
alembic current

# Посмотреть историю миграций
alembic history

# Применить все миграции
alembic upgrade head

# Откатить на одну миграцию назад
alembic downgrade -1

# Откатить все миграции
alembic downgrade base
```

### Вариант 3: С указанием DATABASE_URL
```bash
export DATABASE_URL="postgresql://user:password@localhost:5432/contract_ai"
alembic upgrade head
```

---

## 🗄️ Итоговая схема БД (14 таблиц)

### Post-Execution (Цифровизация)
1. ✅ `contracts_core` - Центральная таблица
2. ✅ `contract_parties` - Стороны
3. ✅ `contract_items` - Спецификация
4. ✅ `payment_schedule` - Платежи
5. ✅ `contract_rules` - Правила (executable)

### Pre-Execution (Переговоры)
6. ✅ `negotiation_sessions` - Сессии анализа
7. ✅ `disagreements` - Протокол разногласий

### IDP Мониторинг
8. ✅ `idp_extraction_log` - Лог обработки
9. ✅ `idp_quality_issues` - Проблемы качества

### Система
10. ✅ `system_config` - Конфигурация
11. ✅ `user_approvals` - Одобрения
12. ✅ `llm_usage_metrics` - Метрики LLM

### RAG
13. ✅ `knowledge_base` - База знаний

### Расширения
14. ✅ `vector` extension - pgvector для векторного поиска

---

## 📊 Статистика

**Общее количество таблиц:** 14
**Общее количество миграций:** 6
**JSONB колонок:** 15+
**Векторных индексов:** 2 (contracts_core.embedding, knowledge_base.embedding)
**GIN индексов:** 8+

---

## ⚠️ Важные замечания

1. **PostgreSQL 16+** обязателен для `gen_random_uuid()`
2. **pgvector extension** должен быть доступен в PostgreSQL
3. **Миграции применяются последовательно** (001 → 002 → 003 → ...)
4. **Откат миграций** очистит все данные в таблицах (будьте осторожны!)
5. **system_config** имеет дефолтные значения - не удаляйте их
6. **knowledge_base** имеет примеры best practices - используйте как шаблон

---

## 🔄 Обновление миграций

Если вы изменили модели SQLAlchemy, создайте новую миграцию:

```bash
alembic revision -m "Description of changes"
```

Alembic автоматически создаст файл в `alembic/versions/`. Отредактируйте `upgrade()` и `downgrade()` функции вручную.

---

**Дата последнего обновления:** 2026-01-09
**Версия:** v2.1
