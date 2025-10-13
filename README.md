# Contract AI System

Интеллектуальная система для автоматизации работы с договорами на основе LLM и RAG.

## 🎯 Возможности

### 1. Onboarding Agent
- Анализ входящих запросов от пользователей
- Классификация типов договоров
- Извлечение ключевых параметров (стороны, сроки, суммы)
- Автоматическое создание задач для генерации или анализа

### 2. Contract Generator Agent
- Генерация договоров по шаблонам XML
- LLM-заполнение переменных с учетом контекста
- RAG для поиска аналогов и прецедентов
- Валидация структуры и обязательных полей

### 3. Contract Analyzer Agent
- Анализ входящих договоров от контрагентов
- Идентификация рисков (financial, legal, operational, reputational)
- Генерация рекомендаций по изменениям
- Аннотация проблемных пунктов с XPath-привязкой
- Интеграция с API контрагента для доп. информации

### 4. Disagreement Processor Agent
- Генерация возражений на проблемные пункты договора
- LLM + RAG для формирования правовых обоснований
- Автоматическая приоритизация + выбор пользователем
- Экспорт в XML, DOCX, PDF, Email, ЭДО
- Трекинг эффективности (принято/отклонено)

### 5. Changes Analyzer Agent
- Сравнение версий договора (структурное + семантическое)
- LLM-анализ влияния каждого изменения на риски
- Автоматическая связь с ранее отправленными возражениями
- Генерация PDF-отчетов об изменениях
- Создание задач на проверку юристами

### 6. Quick Export Agent
- Быстрый экспорт договоров в DOCX, PDF, TXT, JSON
- Batch-режим экспорта
- Логирование всех экспортов

### 7. Orchestrator Agent
- Координация работы всех агентов
- State management для workflows
- Обработка ошибок и fallback'ов

## 🏗️ Архитектура

```
Contract-AI-System/
├── config/
│   └── settings.py           # Конфигурация (DB, LLM API, RAG)
├── database/
│   ├── schema.sql            # Основные таблицы
│   ├── migration_*.sql       # Миграции для каждого агента
├── src/
│   ├── agents/               # AI агенты
│   ├── models/               # SQLAlchemy модели
│   └── services/             # Вспомогательные сервисы
├── tests/                    # Unit-тесты
└── data/
    ├── templates/            # XML шаблоны договоров
    ├── documents/            # Юридические документы для RAG
    ├── contracts/            # Загруженные договоры
    └── exports/              # Экспортированные файлы
```

## 🚀 Быстрый старт

### 1. Установка зависимостей

```bash
pip install -r requirements.txt
```

### 2. Настройка конфигурации

Создайте `.env` файл:

```env
# Database
DATABASE_URL=postgresql://user:password@localhost:5432/contracts_db

# LLM APIs
OPENAI_API_KEY=your_key_here
ANTHROPIC_API_KEY=your_key_here
YANDEX_API_KEY=your_key_here

# RAG
CHROMA_DB_PATH=./data/chroma_db

# Application
APP_ENV=development
LOG_LEVEL=INFO
```

### 3. Инициализация БД

```bash
psql -U user -d contracts_db -f database/schema.sql
psql -U user -d contracts_db -f database/migration_analyzer.sql
psql -U user -d contracts_db -f database/migration_disagreements.sql
psql -U user -d contracts_db -f database/migration_changes_analyzer.sql
```

### 4. Запуск системы

**Веб-интерфейс (Streamlit):**

```bash
streamlit run app.py
# или
./run_ui.sh
```

Откройте браузер: http://localhost:8501

**Программный интерфейс:**

```bash
python main.py
```

## 📊 База данных

### Основные таблицы
- **users** - Пользователи системы
- **templates** - Шаблоны договоров (XML)
- **contracts** - Загруженные договоры
- **analysis_results** - Результаты анализа
- **review_tasks** - Задачи на проверку юристами

### Analyzer модули
- **contract_risks** - Выявленные риски
- **contract_recommendations** - Рекомендации
- **contract_annotations** - Аннотации
- **analysis_feedback** - Обратная связь

### Disagreements модули
- **disagreements** - Документы с возражениями
- **disagreement_objections** - Отдельные возражения
- **disagreement_feedback** - Эффективность

### Changes модули
- **contract_versions** - Версии договоров
- **contract_changes** - Детальные изменения
- **change_analysis_results** - Сводный анализ

## 🌐 Веб-интерфейс

Streamlit UI предоставляет удобный интерфейс для работы со всеми агентами:

- **📥 Обработка запросов** - Анализ входящих запросов (Onboarding Agent)
- **✍️ Генератор договоров** - Создание договоров по шаблонам
- **🔍 Анализ договоров** - Загрузка и анализ договоров контрагентов
- **⚖️ Возражения** - Генерация документов с возражениями
- **📊 Анализ изменений** - Сравнение версий договоров
- **📤 Экспорт** - Быстрый экспорт в различные форматы
- **⚙️ Настройки** - Конфигурация LLM, БД, RAG

**Запуск:**
```bash
streamlit run app.py
```

## 🧪 Тестирование

```bash
pytest tests/ -v
```

## 📝 Лицензия

Proprietary

---

**Версия:** 1.0.0  
**Status:** ✅ Core functionality implemented
