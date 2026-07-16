# Contract AI System - Полная техническая спецификация

## Версия документа: 1.0
## Дата: 11 октября 2025

---

## 📋 Содержание

1. [Обзор проекта](#обзор-проекта)
2. [Бизнес-контекст](#бизнес-контекст)
3. [Архитектура системы](#архитектура-системы)
4. [Мультиагентная система](#мультиагентная-система)
5. [Специализированные агенты](#специализированные-агенты)
6. [Технологический стек](#технологический-стек)
7. [Схема данных](#схема-данных)
8. [Сервисы и утилиты](#сервисы-и-утилиты)
9. [Потоки работы](#потоки-работы)
10. [Структура проекта](#структура-проекта)
11. [План разработки](#план-разработки)
12. [Паттерны и best practices](#паттерны-и-best-practices)

---

## 🎯 Обзор проекта

### Название
**Contract AI System** (AI Legal Assistant for Agribusiness)

### Описание
Мультиагентная система на базе LLM для автоматизации работы юридического отдела агрохолдинга. Система покрывает полный жизненный цикл работы с договорами: от онбординга шаблонов до анализа, генерации и обработки разногласий.

### Ключевые возможности
- ✅ Онбординг и аудит существующих типовых форм договоров компании
- ✅ Генерация проектов договоров на основе условий контрагента
- ✅ Анализ входящих договоров с выявлением рисков
- ✅ Обработка протоколов разногласий
- ✅ Анализ tracked changes в документах
- ✅ Проверка соответствия законодательству через RAG
- ✅ Обязательная проверка человеком (human-in-the-loop)
- ✅ Опциональный быстрый вывод документов

### Целевые пользователи
- Юристы агрохолдингов (CLO, старшие, средние, младшие юристы)
- Размер команды: 3-10 человек
- Объём: 10-50 договоров в неделю

### Целевые метрики успеха MVP
- Снижение времени на работу с договором на 60-80%
- Выявление 80%+ юридических рисков
- Реальное использование системы (10+ договоров/неделю)
- Положительный feedback от пользователей

---

## 💼 Бизнес-контекст

### Проблемы, которые решаем

#### 1. Перегрузка договорной работой
- Юристы тратят 60-70% времени на рутину
- Проверка одного договора: 2-4 часа вручную
- Большой объём типовых операций

#### 2. Высокие риски ошибок
- Человеческий фактор при проверке сотен договоров
- Пропуск критических условий → финансовые потери
- Несоответствие внутренним стандартам

#### 3. Сложность отраслевой специфики
- Агробизнес: земельное право, ВЭД, кадастр, банкротство
- Нет готовых универсальных решений
- Требуется глубокая экспертиза

#### 4. Отсутствие системности
- Знания распределены между людьми
- Нет единой базы прецедентов
- Зависимость от ключевых сотрудников

### Уникальное решение

**Мультиагентная система специализированных AI-агентов:**
- Каждый агент решает определённый класс задач
- Глубокая интеграция с законодательной базой (RAG)
- Учёт отраслевой специфики агробизнеса
- Human-in-the-loop для критических решений
- Обучение на данных компании

### Типы договоров (по ГК РФ)

Система работает со всеми поименованными договорами:

**Глава 30: Купля-продажа**
- Поставка товаров
- Поставка для государственных нужд
- Контрактация
- Энергоснабжение
- Продажа недвижимости

**Глава 34: Аренда**
- Аренда зданий/помещений
- Аренда транспорта
- Финансовая аренда (лизинг)
- Аренда земли

**Глава 37: Подряд**
- Бытовой подряд
- Строительный подряд
- Подряд на НИР
- Подрядные работы для государственных нужд

**Глава 39: Возмездное оказание услуг**
- Информационные услуги
- Консультационные услуги
- Аудиторские услуги
- Прочие услуги

**Глава 47: Хранение**
- Хранение на складе
- Хранение в гардеробе
- Хранение в ломбарде

**Другие:**
- Коммерческая концессия (франчайзинг)
- Агентские договоры
- Комиссия
- И другие поименованные договоры по ГК РФ

---

## 🏗️ Архитектура системы

### Высокоуровневая архитектура

```
┌─────────────────────────────────────────────────────────┐
│                    USER INTERFACE                        │
│          (Next.js Web App на локальном сервере)          │
└────────────────────────┬────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────┐
│              ORCHESTRATOR AGENT                          │
│  • Определяет тип задачи                                 │
│  • Маршрутизирует на специализированный агент            │
└────────────────────────┬────────────────────────────────┘
                         │
        ┌────────────────┼────────────────┬───────────────┐
        │                │                │               │
        ▼                ▼                ▼               ▼
┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌────────────┐
│  ONBOARDING  │ │  CONTRACT    │ │ DISAGREEMENT │ │  CHANGES   │
│    AGENT     │ │  GENERATOR   │ │  PROCESSOR   │ │  ANALYZER  │
│              │ │    AGENT     │ │    AGENT     │ │   AGENT    │
└──────┬───────┘ └──────┬───────┘ └──────┬───────┘ └──────┬─────┘
       │                │                │                │
       └────────────────┼────────────────┴────────────────┘
                        ▼
        ┌───────────────┴────────────────┐
        │                                │
        ▼                                ▼
┌──────────────┐                  ┌──────────────┐
│  CONTRACT    │                  │    QUICK     │
│  ANALYZER    │                  │   EXPORT     │
│    AGENT     │                  │    AGENT     │
└──────────────┘                  └──────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────┐
│                   SHARED SERVICES                        │
├─────────────────────────────────────────────────────────┤
│  • Document Parser (DOCX/PDF → XML)                      │
│  • RAG System (векторный + полнотекстовый поиск)        │
│  • Template Manager (управление эталонными формами)      │
│  • LLM Gateway (Claude API / OpenAI API)                │
│  • Human Review Queue (очередь на проверку)             │
└────────────────────────┬────────────────────────────────┘
                         ▼
┌─────────────────────────────────────────────────────────┐
│                   DATA LAYER                             │
├─────────────────────────────────────────────────────────┤
│  • PostgreSQL (документы, метаданные, история)           │
│  • ChromaDB (векторные эмбеддинги)                      │
│  • File Storage (оригинальные файлы, отчеты)            │
└─────────────────────────────────────────────────────────┘
```

### Принципы архитектуры

1. **Модульность**: Каждый агент - независимый модуль
2. **Специализация**: Один агент = одна ответственность
3. **Расширяемость**: Легко добавлять новых агентов
4. **Human-in-the-loop**: Обязательная проверка критических решений
5. **Гибридный подход**: RAG векторный + полнотекстовый поиск
6. **Постепенное развёртывание**: От минимального набора к полному

---

## 🤖 Мультиагентная система

### Терминология

**Агент** = Специализированный компонент системы, который:
- Воспринимает входные данные (input)
- Обрабатывает их через последовательность шагов (graph/workflow)
- Использует инструменты (LLM, RAG, базы данных)
- Выдаёт результат (output)
- Имеет состояние (State)

**Граф (Graph)** = Реализация агента в LangGraph:
- Набор узлов (nodes) - функций обработки
- Набор рёбер (edges) - связей между узлами
- State - общее состояние, передаваемое между узлами

**Мультиагентная система (MAS)** = Набор специализированных агентов + координатор

### Структура системы

```
CONTRACT AI SYSTEM (Multi-Agent System)
│
├── ORCHESTRATOR AGENT
│   └── Координирует работу специализированных агентов
│
├── SPECIALIZED AGENTS
│   ├── Onboarding Agent (онбординг шаблонов)
│   ├── Contract Generator Agent (генерация договоров)
│   ├── Contract Analyzer Agent (анализ договоров)
│   ├── Disagreement Processor Agent (протоколы разногласий)
│   ├── Changes Analyzer Agent (tracked changes)
│   └── Quick Export Agent (быстрый вывод)
│
└── SHARED SERVICES
    ├── Document Parser
    ├── RAG System
    ├── Template Manager
    ├── LLM Gateway
    └── Review Queue
```

### Коммуникация между агентами

```python
# Orchestrator делегирует задачу специализированному агенту
orchestrator_result = orchestrator.run(input_task)
# → определяет тип задачи
# → вызывает нужного агента
# → возвращает результат

# Специализированный агент работает независимо
analyzer_result = contract_analyzer.run(contract_xml)
# → выполняет свой workflow
# → использует shared services
# → возвращает результат
```

---

## 📦 Специализированные агенты

### 1. Orchestrator Agent

**Цель**: Определить тип задачи и делегировать специализированному агенту

**Входные данные**:
```python
{
    "file_path": str,         # Путь к файлу
    "file_name": str,         # Имя файла
    "task_type": str | None   # Опционально: подсказка о типе задачи
}
```

**Workflow (граф)**:
```
START → DETECT_TYPE → NORMALIZE → ROUTE_TO_AGENT → END
```

**Ноды**:
1. `detect_type`: Определяет тип документа и задачи
2. `normalize`: Конвертирует в XML через Document Parser
3. `route_to_agent`: Маршрутизирует к нужному агенту

**Выходные данные**:
```python
{
    "document_type": str,     # "contract", "disagreement", "tracked_changes"
    "result": dict,           # Результат от специализированного агента
    "status": str             # "completed", "error"
}
```

---

### 2. Onboarding Agent

**Цель**: Загрузить и подготовить существующие типовые формы компании

**Когда используется**:
- Первичное внедрение системы
- Добавление новых типов договоров
- Обновление существующих шаблонов

**Входные данные**:
```python
{
    "templates_folder": str,  # Путь к папке с шаблонами
}
```

**Workflow (граф)**:
```
START → UPLOAD → CLASSIFY → NORMALIZE → EXTRACT_STRUCTURE → 
AUDIT → CREATE_METADATA → VECTORIZE → SAVE → REPORT → END
```

**Ноды**:

1. **upload_templates**: Загрузка всех файлов из папки
   - Поддержка: DOCX, PDF
   - Сохранение списка файлов в state

2. **classify_by_type**: Определение типа каждого договора
   - Использует LLM для классификации по ГК РФ
   - Результат: "supply", "service", "construction", "lease", "storage", etc.

3. **normalize_to_xml**: Конвертация в единый XML формат
   - Через Document Parser
   - Стандартизация структуры

4. **extract_structure**: Выделение структуры шаблона
   - Обязательные разделы
   - Опциональные разделы
   - Ключевые условия
   - Вариативные части

5. **compliance_audit**: Аудит на соответствие законодательству
   - Проверка через RAG System
   - Выявление рисков в шаблоне
   - Рекомендации по улучшению

6. **create_metadata**: Создание метаданных шаблона
   - Обязательные поля
   - Допустимые диапазоны значений
   - Связи с законодательством

7. **vectorize_clauses**: Векторизация разделов
   - Разбивка на clauses
   - Генерация embeddings
   - Индексация в ChromaDB

8. **save_to_library**: Сохранение в библиотеку
   - Запись в PostgreSQL (table: templates)
   - Сохранение XML в файловую систему
   - Версионирование

9. **generate_report**: Генерация отчёта по онбордингу
   - Статистика загруженных шаблонов
   - Найденные риски по каждому шаблону
   - Рекомендации по доработке
   - Экспорт в DOCX

**Выходные данные**:
```python
{
    "templates": List[dict],     # Список обработанных шаблонов
    "audit_results": dict,       # Результаты аудита
    "report_path": str,          # Путь к отчёту
    "status": "completed"
}
```

**State структура**:
```python
class OnboardingState(TypedDict):
    templates_folder: str
    uploaded_files: List[str]
    templates: List[dict]  # [{file, type, xml, metadata, structure}]
    audit_results: dict
    recommendations: List[dict]
    report_path: str
    status: str
```

---

### 3. Contract Generator Agent

**Цель**: Сгенерировать проект договора на основе условий контрагента

**Когда используется**:
- Контрагент прислал условия (email, список требований)
- Бизнес запросил договор с определёнными параметрами
- Нужно быстро сформировать проект для отправки

**Входные данные**:
```python
{
    "contract_type": str,              # "supply", "service", etc.
    "counterparty_conditions": str,    # Текст условий от контрагента
    "additional_params": dict,         # Дополнительные параметры
    "user_requested_review": bool      # Нужна ли проверка юристом
}
```

**Workflow (граф)**:
```
START → PARSE_CONDITIONS → SELECT_TEMPLATE → FILL_TEMPLATE → 
CUSTOMIZE → VALIDATE → RISK_CHECK → [REVIEW | QUICK_EXPORT] → 
EXPORT → END
```

**Ноды**:

1. **parse_conditions**: Парсинг условий контрагента
   - Извлечение структурированных данных через LLM
   - Результат: стороны, суммы, сроки, особые условия

2. **select_template**: Выбор подходящего шаблона
   - Загрузка из библиотеки по типу договора
   - Учёт версионности

3. **fill_template**: Заполнение шаблона данными
   - Подстановка реквизитов
   - Заполнение финансовых условий
   - Установка сроков

4. **customize_clauses**: Адаптация под особые условия
   - Модификация разделов
   - Добавление специальных условий
   - Адаптация формулировок

5. **validate_draft**: Валидация заполненного проекта
   - Проверка обязательных полей
   - Проверка диапазонов значений
   - Выявление противоречий

6. **risk_check**: Быстрая проверка рисков
   - Основные юридические риски
   - Критические несоответствия
   - Рекомендации

7. **review_queue** (условный): Добавление в очередь на проверку
   - Создание задачи для юриста
   - Назначение ответственного
   - Установка приоритета

8. **quick_export** (условный): Быстрый вывод без проверки
   - Минимальная валидация
   - Конвертация XML → DOCX
   - Добавление водяного знака "ПРОЕКТ"

9. **export_docx**: Финальный экспорт
   - Конвертация XML → DOCX
   - Форматирование
   - Сохранение

**Conditional Router**:
```python
def review_decision_router(state):
    if state.get("user_requested_review", False):
        return "review_queue"
    else:
        return "quick_export"
```

**Выходные данные**:
```python
{
    "parsed_conditions": dict,
    "selected_template_id": str,
    "filled_contract_xml": str,
    "risks": List[dict],
    "final_docx_path": str,
    "status": str  # "exported_quick", "awaiting_review", "completed"
}
```

**State структура**:
```python
class ContractGeneratorState(TypedDict):
    contract_type: str
    counterparty_conditions: str
    additional_params: dict
    parsed_conditions: dict
    selected_template_id: str
    template_xml: str
    template_metadata: dict
    filled_contract_xml: str
    validation_errors: List[str]
    risks: List[dict]
    user_requested_review: bool
    review_task_id: str
    final_docx_path: str
    status: str
```

---

### 4. Contract Analyzer Agent

**Цель**: Проанализировать входящий договор от контрагента

**Когда используется**:
- Получили договор от контрагента
- Нужно выявить риски и несоответствия
- Принять решение: подписать / разногласия / отклонить

**Входные данные**:
```python
{
    "contract_xml": str,        # XML договора (после нормализации)
    "contract_type": str,       # Тип договора
}
```

**Workflow (граф)**:
```
START → EXTRACT_ENTITIES → CHECK_STANDARDS → CHECK_LEGAL → 
ANALYZE_RISKS → HUMAN_REVIEW → GENERATE_REPORT → END
```

**Ноды**:

1. **extract_entities**: Извлечение ключевых данных
   - Стороны договора
   - Финансовые условия
   - Сроки
   - Особые условия
   - Использует LLM для извлечения

2. **check_standards**: Проверка на соответствие внутренним стандартам
   - Загрузка эталонного шаблона
   - Сравнение структуры (обязательные разделы)
   - Сравнение ключевых условий
   - Сравнение формулировок (semantic similarity)
   - Результат: список несоответствий

3. **check_legal**: Проверка законодательства через RAG
   - Определение релевантных областей права
   - Векторный поиск в базе законодательства
   - Анализ с учётом судебной практики
   - Проверка обязательных требований (персданные, санкции, лицензии)
   - Результат: список юридических рисков

4. **analyze_risks**: Комплексная оценка рисков
   - Агрегация всех найденных проблем
   - Категоризация рисков (financial, legal, reputational, operational)
   - Определение общего уровня риска (CRITICAL, HIGH, MEDIUM, LOW)
   - Генерация рекомендаций

5. **human_review**: Обязательная проверка юристом
   - Создание задачи в review_tasks
   - Назначение ответственного юриста
   - Установка дедлайна (зависит от уровня риска)
   - Отправка уведомления
   - **КРИТИЧНО**: Workflow останавливается и ждёт решения человека

6. **generate_report**: Генерация отчёта
   - Сводка по рискам
   - Детальный анализ
   - Рекомендации
   - Экспорт в DOCX

**Выходные данные**:
```python
{
    "entities": dict,
    "compliance_issues": List[dict],
    "legal_issues": List[dict],
    "risks_by_category": dict,
    "risk_level": str,
    "critical_risks": List[dict],
    "report": dict,
    "report_file": str,
    "status": str  # "awaiting_review", "completed"
}
```

**State структура**:
```python
class ContractAnalysisState(TypedDict):
    document: str
    contract_xml: str
    contract_type: str
    raw_text: str
    sections: dict
    structure: dict
    entities: dict
    compliance_issues: List[dict]
    legal_issues: List[dict]
    risks_by_category: dict
    risk_level: str
    critical_risks: List[dict]
    escalated: bool
    review_task_id: str
    report: dict
    report_file: str
    status: str
```

---

### 5. Disagreement Processor Agent

**Цель**: Обработать протокол разногласий от контрагента

**Когда используется**:
- Получили протокол разногласий на наш договор
- Нужно проанализировать каждый пункт
- Сформировать позицию и ответ

**Входные данные**:
```python
{
    "disagreement_file": str,   # Путь к файлу протокола
    "our_contract_id": str,     # ID нашего договора, к которому протокол
}
```

**Workflow (граф)**:
```
START → PARSE_PROTOCOL → LOAD_OUR_TEMPLATE → ANALYZE_ITEMS → 
RISK_ASSESSMENT → GENERATE_RESPONSE → HUMAN_REVIEW → FINALIZE → END
```

**Ноды**:

1. **parse_disagreement_protocol**: Парсинг структуры протокола
   - Извлечение пунктов разногласий
   - Для каждого пункта: наша редакция, редакция контрагента, обоснование
   - Структурирование данных

2. **load_our_template**: Загрузка нашего договора
   - Получение XML нашего договора
   - Контекст для анализа

3. **analyze_each_item**: Анализ каждого пункта разногласий
   - Определение раздела договора
   - Анализ изменения с помощью LLM + RAG
   - Определение позиции: accept / reject / negotiate
   - Оценка рисков
   - Варианты компромисса

4. **risk_assessment**: Оценка общих рисков
   - Агрегация рисков по всем пунктам
   - Оценка влияния на баланс интересов
   - Рекомендации

5. **generate_response_draft**: Генерация проекта ответа
   - Таблица с ответом по каждому пункту
   - Обоснования
   - Предложения о встрече (для спорных пунктов)
   - Форматирование в официальный документ

6. **human_review**: Обязательная проверка
   - Юрист проверяет анализ и проект ответа
   - Может изменить позицию по пунктам
   - Утверждает финальную версию

7. **finalize_response**: Финализация документа
   - Экспорт в DOCX
   - Подготовка к отправке

**Выходные данные**:
```python
{
    "disagreement_items": List[dict],
    "analysis_by_position": dict,  # {accept: [...], reject: [...], negotiate: [...]}
    "overall_risks": dict,
    "response_draft": str,
    "response_file": str,
    "status": str
}
```

**State структура**:
```python
class DisagreementState(TypedDict):
    disagreement_file: str
    our_contract_id: str
    our_contract_xml: str
    disagreement_items: List[dict]  # List[DisagreementItem]
    analysis_by_position: dict
    overall_risks: dict
    response_draft: str
    response_file: str
    review_task_id: str
    status: str

class DisagreementItem(TypedDict):
    item_number: str
    original_text: str
    proposed_text: str
    reason: str
    our_position: str  # "accept", "reject", "negotiate"
    recommendation: str
    legal_risks: str
    commercial_risks: str
    compromise_options: List[str]
```

---

### 6. Changes Analyzer Agent

**Цель**: Проанализировать документ с tracked changes

**Когда используется**:
- Получили DOCX с отслеживаемыми правками
- Нужно классифицировать изменения по критичности
- Принять решение по каждому изменению

**Входные данные**:
```python
{
    "docx_file": str,           # Путь к DOCX с tracked changes
    "our_template_id": str,     # ID нашего шаблона для сравнения
}
```

**Workflow (граф)**:
```
START → EXTRACT_CHANGES → LOAD_TEMPLATE → CLASSIFY_CHANGES → 
ANALYZE_IMPACT → GENERATE_RECOMMENDATIONS → HUMAN_REVIEW → 
FINALIZE → END
```

**Ноды**:

1. **extract_tracked_changes**: Извлечение всех изменений
   - Парсинг DOCX XML
   - Извлечение insertions (w:ins)
   - Извлечение deletions (w:del)
   - Метаданные: автор, дата, текст

2. **load_our_template**: Загрузка эталона
   - Получение нашего шаблона
   - Контекст для оценки критичности

3. **classify_each_change**: Классификация по критичности
   - Для каждого изменения:
     - Определение контекста в шаблоне
     - Классификация через LLM: critical / high / medium / low
     - Обоснование оценки

4. **analyze_impact**: Анализ влияния изменений
   - Группировка по критичности
   - Оценка совокупного эффекта
   - Выявление связанных изменений

5. **generate_recommendations**: Генерация рекомендаций
   - По каждому изменению: принять / отклонить / обсудить
   - Общие рекомендации по документу
   - Предложения компромиссов

6. **human_review**: Проверка юристом
   - Просмотр всех изменений
   - Финальное решение по каждому
   - Утверждение

7. **finalize_decision**: Финализация
   - Применение принятых изменений
   - Отклонение непринятых
   - Генерация финальной версии

**Выходные данные**:
```python
{
    "changes": List[dict],
    "analysis": dict,  # {critical: [...], high: [...], medium: [...], low: [...]}
    "recommendations": List[dict],
    "final_version": str,
    "status": str
}
```

**State структура**:
```python
class ChangesAnalysisState(TypedDict):
    docx_file: str
    our_template_id: str
    our_template_xml: str
    changes: List[dict]  # List[Change]
    analysis: dict
    recommendations: List[dict]
    final_version: str
    review_task_id: str
    status: str

class Change(TypedDict):
    change_id: str
    change_type: str  # "insert" | "delete"
    author: str
    date: str
    text: str
    paragraph_id: int
    severity: str  # "critical" | "high" | "medium" | "low"
    recommendation: str
    decision: str  # "accept" | "reject" | "discuss"
```

---

### 7. Quick Export Agent

**Цель**: Быстро вывести документ без полной проверки

**Когда используется**:
- Пользователь уверен в документе
- Срочная ситуация
- Технические правки
- Уже согласованный документ

**Входные данные**:
```python
{
    "contract_xml": str,
    "skip_full_review": bool  # Подтверждение пользователя
}
```

**Workflow (граф)**:
```
START → BASIC_VALIDATION → CONVERT_TO_DOCX → 
ADD_WATERMARK → LOG_EXPORT → END
```

**Ноды**:

1. **basic_validation**: Минимальная проверка
   - Все обязательные поля заполнены
   - Нет явных ошибок формата

2. **convert_to_docx**: Конвертация
   - XML → DOCX
   - Применение форматирования

3. **add_watermark** (опционально): Водяной знак
   - Добавление "ПРОЕКТ" если нужно

4. **log_export_action**: Логирование
   - Кто экспортировал
   - Когда
   - Без полной проверки (важно для аудита)

**Выходные данные**:
```python
{
    "docx_path": str,
    "exported_by": str,
    "exported_at": str,
    "status": "exported_without_review"
}
```

---

## 🔧 Технологический стек

### Backend

```yaml
Язык: Python 3.11+

Фреймворки и библиотеки:
  - langchain: ^0.1.0          # LLM фреймворк
  - langgraph: ^0.0.40         # Графы агентов
  - anthropic: ^0.18.0         # Claude API
  - openai: ^1.0.0             # OpenAI API (backup)
  - pydantic: ^2.5.0           # Валидация данных
  - sqlalchemy: ^2.0.0         # ORM
  - psycopg2-binary: ^2.9.0    # PostgreSQL драйвер
  - chromadb: ^0.4.0           # Векторная БД
  - sentence-transformers: ^2.0.0  # Embeddings

Обработка документов:
  - python-docx: ^1.1.0        # DOCX
  - PyPDF2: ^3.0.0             # PDF
  - pdfplumber: ^0.10.0        # PDF advanced
  - lxml: ^5.0.0               # XML
  - mammoth: ^1.6.0            # DOCX → HTML

Инфраструктура:
  - fastapi: ^0.109.0          # REST API (опционально)
  - redis: ^5.0.0              # Кэш (опционально)
```

### Frontend

```yaml
Framework: Next.js 14+

Визуализация:
  - react: ^18.0.0            # Компоненты UI
  - plotly: ^5.18.0            # Графики
  - pandas: ^2.1.0             # Таблицы
```

### Базы данных

```yaml
PostgreSQL: 14+
  - Основная реляционная БД
  - Документы, метаданные, история
  - Полнотекстовый поиск

ChromaDB: 0.4+
  - Векторная БД для RAG
  - Локальное хранилище
  - Коллекции: legislation, templates, precedents
```

### LLM модели

```yaml
Primary: Claude Sonnet 4 (claude-sonnet-4-20250514)
  - Основная модель для всех задач
  - Через Anthropic API

Backup: GPT-4 Turbo
  - На случай недоступности Claude
  - Через OpenAI API

Embeddings: paraphrase-multilingual-MiniLM-L12-v2
  - Локальная модель для embeddings
  - Sentence Transformers
```

### Инфраструктура MVP

```yaml
Хостинг: Локальный ноутбук / ПК
  - CPU: 4+ cores
  - RAM: 16+ GB
  - Storage: 256+ GB SSD
  - GPU: опционально (ускорит embeddings)

Стоимость:
  - Инфраструктура: 0 руб (локально)
  - Anthropic API: ~2000-4000 руб/месяц
  - ИТОГО: ~2000-4000 руб/месяц
```

---

## 💾 Схема данных

### PostgreSQL Schema

```sql
-- Таблица: contracts (договоры)
CREATE TABLE contracts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    file_name VARCHAR(255) NOT NULL,
    file_path TEXT NOT NULL,
    document_type VARCHAR(50) NOT NULL,  -- "contract", "disagreement", "tracked_changes"
    contract_type VARCHAR(50),           -- "supply", "service", "construction", etc.
    upload_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    status VARCHAR(50) DEFAULT 'pending', -- "pending", "analyzing", "reviewing", "completed"
    assigned_to UUID REFERENCES users(id),
    risk_level VARCHAR(20),              -- "CRITICAL", "HIGH", "MEDIUM", "LOW"
    metadata JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_contracts_status ON contracts(status);
CREATE INDEX idx_contracts_risk_level ON contracts(risk_level);
CREATE INDEX idx_contracts_assigned_to ON contracts(assigned_to);

-- Таблица: analysis_results (результаты анализа)
CREATE TABLE analysis_results (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    contract_id UUID REFERENCES contracts(id) ON DELETE CASCADE,
    entities JSONB,                      -- Извлеченные сущности
    compliance_issues JSONB,             -- Несоответствия стандартам
    legal_issues JSONB,                  -- Юридические риски
    risks_by_category JSONB,             -- Риски по категориям
    recommendations JSONB,               -- Рекомендации
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    version INTEGER DEFAULT 1
);

CREATE INDEX idx_analysis_contract_id ON analysis_results(contract_id);

-- Таблица: templates (шаблоны договоров)
CREATE TABLE templates (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    contract_type VARCHAR(50) NOT NULL,  -- "supply", "service", etc.
    xml_content TEXT NOT NULL,
    structure JSONB,                     -- Структура шаблона
    metadata JSONB,                      -- Метаданные (required_fields, etc.)
    version VARCHAR(20) NOT NULL,
    active BOOLEAN DEFAULT true,
    created_by UUID REFERENCES users(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    UNIQUE(contract_type, version)
);

CREATE INDEX idx_templates_type ON templates(contract_type);
CREATE INDEX idx_templates_active ON templates(active);

-- Таблица: review_tasks (задачи на проверку)
CREATE TABLE review_tasks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    contract_id UUID REFERENCES contracts(id) ON DELETE CASCADE,
    assigned_to UUID REFERENCES users(id),
    status VARCHAR(50) DEFAULT 'pending',  -- "pending", "in_progress", "completed"
    priority VARCHAR(20) DEFAULT 'normal', -- "critical", "high", "normal", "low"
    deadline TIMESTAMP,
    decision VARCHAR(50),                  -- "approve", "reject", "negotiate"
    comments TEXT,
    completed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_review_tasks_assigned ON review_tasks(assigned_to);
CREATE INDEX idx_review_tasks_status ON review_tasks(status);
CREATE INDEX idx_review_tasks_deadline ON review_tasks(deadline);

-- Таблица: legal_documents (база знаний для RAG)
CREATE TABLE legal_documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    doc_id VARCHAR(64) UNIQUE NOT NULL,  -- Hash от URL
    title TEXT NOT NULL,
    doc_type VARCHAR(50) NOT NULL,       -- "law", "code", "court_decision", etc.
    content TEXT NOT NULL,
    status VARCHAR(20) DEFAULT 'active', -- "active", "inactive"
    is_vectorized BOOLEAN DEFAULT false,
    metadata JSONB,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_legal_docs_type ON legal_documents(doc_type);
CREATE INDEX idx_legal_docs_status ON legal_documents(status);
CREATE INDEX idx_legal_docs_vectorized ON legal_documents(is_vectorized);

-- Полнотекстовый поиск для legal_documents
CREATE INDEX idx_legal_docs_content_fts ON legal_documents 
    USING GIN(to_tsvector('russian', content));

-- Таблица: users (пользователи)
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) UNIQUE NOT NULL,
    name VARCHAR(255) NOT NULL,
    role VARCHAR(50) NOT NULL,           -- "admin", "senior_lawyer", "lawyer", "junior_lawyer"
    active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Таблица: export_logs (логи экспорта)
CREATE TABLE export_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    contract_id UUID REFERENCES contracts(id),
    exported_by UUID REFERENCES users(id),
    export_type VARCHAR(50),             -- "full_review", "quick_export"
    exported_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    metadata JSONB
);

CREATE INDEX idx_export_logs_contract ON export_logs(contract_id);
CREATE INDEX idx_export_logs_user ON export_logs(exported_by);
```

### ChromaDB Collections

```python
# Collection: legislation (законодательство)
{
    "name": "legislation",
    "metadata": {
        "description": "Законы, кодексы, постановления"
    },
    "embeddings": [vector],
    "documents": [text_chunk],
    "metadatas": [{
        "doc_id": str,
        "title": str,
        "doc_type": str,  # "gk_rf", "zk_rf", etc.
        "section": str,
        "article": str,
        "date": str,
        "status": str  # "active", "inactive"
    }]
}

# Collection: templates (шаблоны компании)
{
    "name": "company_templates",
    "embeddings": [vector],
    "documents": [clause_text],
    "metadatas": [{
        "template_id": str,
        "contract_type": str,
        "section": str,
        "is_required": bool,
        "version": str
    }]
}

# Collection: precedents (прецеденты)
{
    "name": "precedents",
    "embeddings": [vector],
    "documents": [case_text],
    "metadatas": [{
        "case_id": str,
        "court": str,
        "date": str,
        "contract_type": str,
        "outcome": str
    }]
}
```

### File Storage Structure

```
/data/
├── uploads/              # Оригинальные загруженные файлы
│   └── {contract_id}.{ext}
│
├── normalized/           # XML версии документов
│   └── {contract_id}.xml
│
├── reports/              # Сгенерированные отчеты
│   └── {contract_id}_report_{timestamp}.docx
│
├── templates/            # Эталонные формы (XML)
│   ├── supply_contract_v1.xml
│   ├── service_contract_v1.xml
│   └── construction_contract_v1.xml
│
└── exports/              # Экспортированные договоры
    └── {contract_id}_final_{timestamp}.docx
```

---

## 🛠️ Сервисы и утилиты

### Document Parser Service

**Цель**: Универсальная конвертация документов в XML

**Поддерживаемые форматы**:
- DOCX → XML
- PDF (text) → XML
- PDF (scanned) → XML (через OCR)
- XML → XML (нормализация)

**Структура XML договора**:

```xml
<contract>
    <metadata>
        <contract_id>uuid</contract_id>
        <contract_type>supply</contract_type>
        <creation_date>2025-10-11</creation_date>
        <version>1.0</version>
    </metadata>
    
    <parties>
        <party role="supplier">
            <name>ООО "Поставщик"</name>
            <inn>1234567890</inn>
            <address>Москва, ул. Ленина, 1</address>
            <representative>Иванов И.И.</representative>
        </party>
        <party role="buyer">
            <name>ООО "Покупатель"</name>
            <inn>0987654321</inn>
            <address>Тамбов, ул. Советская, 10</address>
            <representative>Петров П.П.</representative>
        </party>
    </parties>
    
    <terms>
        <subject>Поставка пшеницы</subject>
        
        <financial>
            <total_amount>1000000</total_amount>
            <currency>RUB</currency>
            <payment_terms>Предоплата 30%, остальное в течение 10 дней после поставки</payment_terms>
            <payment_schedule>
                <payment date="2025-11-01" amount="300000" />
                <payment date="2025-11-15" amount="700000" />
            </payment_schedule>
        </financial>
        
        <dates>
            <signature_date>2025-10-11</signature_date>
            <start_date>2025-11-01</start_date>
            <end_date>2026-10-31</end_date>
        </dates>
    </terms>
    
    <clauses>
        <clause id="1" type="subject" required="true">
            <title>1. Предмет договора</title>
            <content>
                <paragraph>Поставщик обязуется поставить...</paragraph>
            </content>
        </clause>
        
        <clause id="2" type="financial" required="true">
            <title>2. Цена и порядок расчётов</title>
            <content>
                <paragraph>Общая стоимость товара...</paragraph>
            </content>
        </clause>
        
        <!-- Остальные разделы -->
    </clauses>
    
    <signatures>
        <signature party="supplier" date="2025-10-11" />
        <signature party="buyer" date="2025-10-11" />
    </signatures>
</contract>
```

**API**:

```python
class DocumentParser:
    def parse(self, file_path: str) -> str:
        """Конвертирует файл в XML"""
        
    def convert_docx_to_xml(self, docx_path: str) -> str:
        """DOCX → XML"""
        
    def convert_pdf_to_xml(self, pdf_path: str) -> str:
        """PDF → XML"""
        
    def extract_tracked_changes(self, docx_path: str) -> List[Change]:
        """Извлекает tracked changes из DOCX"""
        
    def normalize_xml(self, xml: str) -> str:
        """Приводит XML к стандартному формату"""
        
    def validate_xml(self, xml: str) -> List[str]:
        """Валидирует XML по схеме"""
```

---

### RAG System Service

**Цель**: Гибридный поиск в базе знаний

**Компоненты**:

1. **Векторный поиск** (ChromaDB)
   - Семантический поиск
   - Топ-K релевантных чанков

2. **Полнотекстовый поиск** (PostgreSQL)
   - Точный поиск по ключевым словам
   - Резервный метод

3. **On-demand векторизация**
   - Векторизация популярных документов
   - Кэширование embeddings

**API**:

```python
class RAGSystem:
    def search(
        self, 
        query: str, 
        collection: str = "legislation",
        top_k: int = 5
    ) -> List[dict]:
        """Гибридный поиск"""
        
    def vector_search(self, query: str, top_k: int) -> List[dict]:
        """Векторный поиск"""
        
    def fulltext_search(self, query: str, limit: int) -> List[dict]:
        """Полнотекстовый поиск"""
        
    def check_template_compliance(
        self,
        xml: str,
        contract_type: str
    ) -> dict:
        """Проверка шаблона на соответствие законодательству"""
        
    def find_relevant_cases(
        self,
        contract_type: str,
        issue: str
    ) -> List[dict]:
        """Поиск релевантных прецедентов"""

class RAGIndexer:
    def index_document(self, doc: LegalDocument):
        """Индексирует документ"""
        
    def index_clause(self, text: str, metadata: dict):
        """Индексирует раздел договора"""
        
    def update_document(self, doc_id: str, new_content: str):
        """Обновляет документ"""
```

---

### Template Manager Service

**Цель**: Управление эталонными формами договоров

**Функции**:
- Загрузка/сохранение шаблонов
- Версионирование
- Поиск шаблона по типу
- Сравнение с шаблоном

**API**:

```python
class TemplateManager:
    def load_template(self, template_id: str) -> dict:
        """Загружает шаблон"""
        
    def get_template_by_type(
        self, 
        contract_type: str,
        version: str = "latest"
    ) -> dict:
        """Получает шаблон по типу"""
        
    def save_template(
        self,
        name: str,
        contract_type: str,
        xml_content: str,
        metadata: dict
    ) -> str:
        """Сохраняет новый шаблон"""
        
    def compare_with_template(
        self,
        contract_xml: str,
        template_id: str
    ) -> dict:
        """Сравнивает договор с шаблоном"""
        
    def list_templates(self, contract_type: str = None) -> List[dict]:
        """Список всех шаблонов"""
```

---

### LLM Gateway Service

**Цель**: Единая точка доступа к LLM с retry и кэшированием

**Функции**:
- Вызов Claude/GPT
- Retry логика
- Кэширование
- Подсчёт токенов и затрат

**API**:

```python
class LLMGateway:
    def call(
        self,
        prompt: str,
        model: str = "claude-sonnet-4-20250514",
        response_format: str = "text",  # "text" | "json"
        temperature: float = 0.0,
        max_tokens: int = 4000
    ) -> str | dict:
        """Вызов LLM"""
        
    def call_with_retry(
        self,
        prompt: str,
        max_retries: int = 3
    ) -> str | dict:
        """Вызов с повторными попытками"""
        
    def get_cached_response(
        self,
        prompt_hash: str
    ) -> str | dict | None:
        """Получение из кэша"""
        
    def count_tokens(self, text: str) -> int:
        """Подсчёт токенов"""
        
    def get_usage_stats(self) -> dict:
        """Статистика использования"""
```

---

### Human Review Queue Service

**Цель**: Управление очередью задач для юристов

**Функции**:
- Создание задач
- Назначение юристов
- Приоритезация
- Уведомления

**API**:

```python
class ReviewQueue:
    def create_task(
        self,
        contract_id: str,
        risk_level: str,
        priority: str = "normal"
    ) -> str:
        """Создаёт задачу на проверку"""
        
    def assign_task(self, task_id: str, user_id: str):
        """Назначает задачу юристу"""
        
    def complete_task(
        self,
        task_id: str,
        decision: str,  # "approve" | "reject" | "negotiate"
        comments: str
    ):
        """Завершает задачу"""
        
    def get_pending_tasks(self, user_id: str = None) -> List[dict]:
        """Список ожидающих задач"""
        
    def get_task_details(self, task_id: str) -> dict:
        """Детали задачи"""
```

---

## 🔄 Потоки работы (Workflows)

### Workflow 1: Онбординг компании

```
1. Юрист загружает папку с типовыми формами (UI)
   ↓
2. Orchestrator запускает Onboarding Agent
   ↓
3. Onboarding Agent:
   - Классифицирует каждый файл по типу договора
   - Конвертирует в XML
   - Извлекает структуру
   - Проводит аудит через RAG
   - Создаёт метаданные
   - Векторизует разделы
   - Сохраняет в библиотеку
   ↓
4. Генерируется отчёт по аудиту
   ↓
5. Юрист просматривает отчёт и устраняет найденные риски (опционально)
   ↓
6. Библиотека шаблонов готова к использованию
```

### Workflow 2: Генерация исходящего договора

```
1. Юрист получает условия от контрагента (email/список требований)
   ↓
2. Загружает условия в систему (UI)
   ↓
3. Выбирает тип договора
   ↓
4. Указывает: нужна ли полная проверка или быстрый вывод
   ↓
5. Orchestrator запускает Contract Generator Agent
   ↓
6. Contract Generator Agent:
   - Парсит условия контрагента
   - Выбирает наш шаблон
   - Заполняет шаблон данными
   - Адаптирует под особые условия
   - Валидирует
   - Проверяет риски
   ↓
7a. Если выбрана полная проверка:
    - Создаётся задача в Review Queue
    - Юрист проверяет проект
    - Утверждает или вносит правки
    - Экспортируется DOCX
    ↓
7b. Если выбран быстрый вывод:
    - Quick Export Agent
    - Сразу экспортируется DOCX с водяным знаком "ПРОЕКТ"
    ↓
8. Юрист отправляет проект контрагенту
```

### Workflow 3: Анализ входящего договора

```
1. Получен договор от контрагента (email/файл)
   ↓
2. Юрист загружает в систему (UI)
   ↓
3. Orchestrator определяет тип: входящий договор
   ↓
4. Запускает Contract Analyzer Agent
   ↓
5. Contract Analyzer Agent:
   - Нормализует в XML
   - Извлекает сущности (стороны, суммы, сроки)
   - Сравнивает с нашим шаблоном (check_standards)
   - Проверяет по законодательству через RAG (check_legal)
   - Классифицирует риски
   ↓
6. ОБЯЗАТЕЛЬНО создаётся задача в Review Queue
   ↓
7. Юрист получает уведомление
   ↓
8. Юрист открывает задачу в UI:
   - Видит AI-анализ
   - Список рисков по категориям
   - Рекомендации
   - Оригинальный договор
   ↓
9. Юрист принимает решение:
   - Подписать (approve)
   - Отклонить (reject)
   - Отправить протокол разногласий (negotiate)
   ↓
10. Генерируется финальный отчёт
    ↓
11. Действия на основе решения:
    - Approve → готовим к подписанию
    - Reject → письмо контрагенту
    - Negotiate → переход к Workflow 4
```

### Workflow 4: Обработка протокола разногласий

```
1. Получен протокол разногласий от контрагента
   ↓
2. Юрист загружает в систему
   ↓
3. Orchestrator определяет тип: протокол разногласий
   ↓
4. Запускает Disagreement Processor Agent
   ↓
5. Disagreement Processor Agent:
   - Парсит структуру протокола
   - Извлекает пункты разногласий
   - Загружает наш договор для контекста
   - Анализирует каждый пункт:
     * Определяет позицию (принять/отклонить/обсудить)
     * Оценивает риски
     * Предлагает компромиссы
   - Генерирует проект ответа
   ↓
6. Создаётся задача в Review Queue
   ↓
7. Юрист проверяет:
   - AI-анализ по каждому пункту
   - Проект ответа
   - Может изменить позицию
   ↓
8. Утверждает финальную версию ответа
   ↓
9. Экспорт ответа в DOCX
   ↓
10. Отправка контрагенту
```

### Workflow 5: Анализ tracked changes

```
1. Получен DOCX с отслеживаемыми правками
   ↓
2. Юрист загружает в систему
   ↓
3. Orchestrator определяет: tracked changes
   ↓
4. Запускает Changes Analyzer Agent
   ↓
5. Changes Analyzer Agent:
   - Извлекает все изменения (insertions + deletions)
   - Загружает наш шаблон
   - Классифицирует каждое изменение по критичности
   - Анализирует совокупное влияние
   - Генерирует рекомендации
   ↓
6. Создаётся задача в Review Queue
   ↓
7. Юрист просматривает:
   - Таблицу изменений с критичностью
   - Рекомендации по каждому
   - Оригинальный документ с подсветкой
   ↓
8. Принимает решение по каждому изменению:
   - Accept (принять)
   - Reject (отклонить)
   - Discuss (обсудить с контрагентом)
   ↓
9. Генерируется финальная версия с применёнными изменениями
   ↓
10. Экспорт
```

---

## 📁 Структура проекта

```
contract-analyzer-mvp/
│
├── README.md                           # Документация проекта
├── requirements.txt                    # Python зависимости
├── .env.example                        # Пример переменных окружения
├── .gitignore
│
├── frontend/                           # Next.js UI
│
├── config/
│   ├── __init__.py
│   ├── settings.py                     # Конфигурация (БД, API ключи)
│   └── prompts.py                      # LLM промпты
│
├── src/
│   ├── __init__.py
│   │
│   ├── orchestrator/
│   │   ├── __init__.py
│   │   ├── main_graph.py               # Orchestrator Agent граф
│   │   └── state.py                    # Определение OrchestratorState
│   │
│   ├── agents/
│   │   ├── __init__.py
│   │   ├── onboarding_agent.py         # Onboarding Agent
│   │   ├── contract_generator_agent.py # Contract Generator Agent
│   │   ├── contract_analyzer_agent.py  # Contract Analyzer Agent
│   │   ├── disagreement_agent.py       # Disagreement Processor Agent
│   │   ├── changes_analyzer_agent.py   # Changes Analyzer Agent
│   │   └── quick_export_agent.py       # Quick Export Agent
│   │
│   ├── services/
│   │   ├── __init__.py
│   │   ├── document_parser.py          # Document Parser Service
│   │   ├── rag_system.py               # RAG System Service
│   │   ├── template_manager.py         # Template Manager Service
│   │   ├── llm_gateway.py              # LLM Gateway Service
│   │   └── review_queue.py             # Human Review Queue Service
│   │
│   ├── models/
│   │   ├── __init__.py
│   │   ├── database.py                 # SQLAlchemy models
│   │   ├── repositories.py             # Database repositories
│   │   └── schemas.py                  # Pydantic schemas
│   │
│   └── utils/
│       ├── __init__.py
│       ├── xml_utils.py                # XML утилиты
│       ├── docx_utils.py               # DOCX утилиты
│       └── helpers.py                  # Вспомогательные функции
│
├── data/
│   ├── uploads/                        # Загруженные файлы
│   ├── normalized/                     # XML версии
│   ├── reports/                        # Отчеты
│   ├── templates/                      # Эталонные формы (XML)
│   └── exports/                        # Экспортированные документы
│
├── database/
│   ├── init.sql                        # Инициализация БД
│   └── migrations/                     # Миграции (Alembic)
│
├── tests/
│   ├── __init__.py
│   ├── test_parser.py
│   ├── test_rag.py
│   ├── test_agents.py
│   └── fixtures/                       # Тестовые файлы
│
└── docs/
    ├── architecture.md                 # Архитектура
    ├── api.md                          # API документация
    └── deployment.md                   # Инструкции по развертыванию
```

---

## 🚀 План разработки MVP (4 недели)

### Неделя 1: Фундамент

**День 1-2: Настройка окружения**
- Установка PostgreSQL + ChromaDB
- Создание структуры проекта
- Настройка виртуального окружения
- Установка зависимостей
- Инициализация БД (init.sql)

**День 3-4: Document Parser**
- Реализация `document_parser.py`
- DOCX → XML конвертация
- PDF → XML конвертация
- Извлечение tracked changes
- Unit тесты

**День 5-7: Template Manager**
- Реализация `template_manager.py`
- Загрузка эталонных форм
- Сравнение структур
- Добавление 2-3 реальных шаблонов из компании

**Результат**: Базовая инфраструктура готова

### Неделя 2: Первый агент

**День 8-9: Contract Analyzer Agent (скелет)**
- Определение ContractAnalysisState
- Создание графа с 3 основными нодами
- Реализация LLM Gateway
- Базовая интеграция с LangGraph

**День 10-11: Entity Extraction + Standards Check**
- Нода: extract_entities
- Нода: check_standards (сравнение с шаблоном)
- Промпты для LLM
- Тесты на 5 реальных договорах

**День 12-14: Human Review + UI**
- Нода: human_review
- Таблица review_tasks в БД
- Базовый UI в Next.js:
  - Загрузка файлов
  - Просмотр результатов анализа
  - Очередь задач на проверку
- Интеграция графа с UI

**Результат**: Работающий Contract Analyzer Agent + UI

### Неделя 3: RAG + Анализ рисков

**День 15-16: RAG System (минимальный)**
- Реализация `rag_system.py`
- Парсинг 500 статей ГК РФ (основные по договорам)
- Векторизация через Sentence Transformers
- Индексация в ChromaDB
- Тестирование поиска

**День 17-18: Legal Compliance Node**
- Нода: check_legal
- Интеграция RAG System
- Промпты для анализа с учётом законодательства
- Тесты

**День 19-21: Risk Analysis + Report Generation**
- Нода: analyze_risks
- Агрегация и классификация рисков
- Генерация DOCX отчёта
- Финализация графа Contract Analyzer Agent

**Результат**: Полный граф Contract Analyzer Agent с RAG

### Неделя 4: Полировка + Тестирование

**День 22-23: UI доработка**
- Улучшение интерфейса загрузки
- Дашборд с аналитикой
- Страница просмотра результатов
- Страница очереди задач

**День 24-26: Тестирование на реальных данных**
- Прогон 20 договоров из практики
- Сбор feedback от коллег-юристов
- Исправление найденных багов
- Доработка промптов

**День 27-28: Документация + Деплой**
- README.md
- Инструкции для пользователей
- Скрипты запуска
- Запуск в локальной сети для команды

**Результат**: Работающий MVP, готовый к пилотному использованию

---

## 📐 Паттерны и Best Practices

### 1. LangGraph паттерны

#### Структура State

```python
from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class MyAgentState(TypedDict):
    # Входные данные
    input_field: str
    
    # Промежуточные данные
    processed_data: dict
    
    # Результаты
    output: dict
    status: str
```

#### Создание графа

```python
def build_agent_graph():
    # Создаём граф
    workflow = StateGraph(MyAgentState)
    
    # Добавляем ноды (функции)
    workflow.add_node("step1", step1_function)
    workflow.add_node("step2", step2_function)
    workflow.add_node("step3", step3_function)
    
    # Определяем последовательность (рёбра)
    workflow.set_entry_point("step1")
    workflow.add_edge("step1", "step2")
    workflow.add_edge("step2", "step3")
    workflow.add_edge("step3", END)
    
    # Компилируем
    return workflow.compile()
```

#### Условное ветвление

```python
def router_function(state):
    """Функция-роутер для условного ветвления"""
    if state["some_condition"]:
        return "path_a"
    else:
        return "path_b"

# В графе
workflow.add_conditional_edges(
    "decision_node",
    router_function,
    {
        "path_a": "node_a",
        "path_b": "node_b"
    }
)
```

### 2. LLM вызовы

#### Базовый вызов

```python
def llm_call(prompt: str, response_format: str = "text") -> str | dict:
    """
    Вызов LLM через LLM Gateway
    """
    from src.services.llm_gateway import LLMGateway
    
    gateway = LLMGateway()
    response = gateway.call(
        prompt=prompt,
        model="claude-sonnet-4-20250514",
        response_format=response_format,
        temperature=0.0
    )
    
    return response
```

#### Промпт для извлечения JSON

```python
prompt = f"""
Извлеки из текста следующую информацию:

{text}

Верни JSON в формате:
{{
    "field1": "value",
    "field2": 123,
    "field3": ["item1", "item2"]
}}

ВАЖНО: Ответь ТОЛЬКО валидным JSON, без дополнительного текста.
"""

response = llm_call(prompt, response_format="json")
data = json.loads(response)
```

### 3. RAG поиск

```python
def search_legislation(query: str) -> List[dict]:
    """
    Поиск в законодательной базе
    """
    from src.services.rag_system import RAGSystem
    
    rag = RAGSystem()
    
    # Векторный поиск
    results = rag.vector_search(
        query=query,
        collection="legislation",
        top_k=5
    )
    
    # Если мало результатов - добавляем полнотекстовый
    if len(results) < 3:
        fulltext_results = rag.fulltext_search(query, limit=5)
        results.extend(fulltext_results)
    
    return results
```

### 4. Работа с БД

#### Repository паттерн

```python
class ContractRepository:
    def __init__(self):
        self.db = get_database_session()
    
    def create(self, contract_data: dict) -> str:
        """Создаёт договор"""
        contract = Contract(**contract_data)
        self.db.add(contract)
        self.db.commit()
        return str(contract.id)
    
    def get_by_id(self, contract_id: str) -> Contract:
        """Получает договор по ID"""
        return self.db.query(Contract).filter_by(id=contract_id).first()
    
    def update_status(self, contract_id: str, status: str):
        """Обновляет статус"""
        self.db.query(Contract).filter_by(id=contract_id).update({"status": status})
        self.db.commit()
```

### 5. Обработка ошибок

```python
def safe_llm_call(prompt: str, max_retries: int = 3):
    """
    LLM вызов с retry логикой
    """
    from tenacity import retry, stop_after_attempt, wait_exponential
    
    @retry(
        stop=stop_after_attempt(max_retries),
        wait=wait_exponential(multiplier=1, min=2, max=10)
    )
    def _call():
        return llm_call(prompt)
    
    try:
        return _call()
    except Exception as e:
        logger.error(f"LLM call failed after {max_retries} retries: {e}")
        raise
```

### 6. Логирование

```python
import logging

# Настройка логгера
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

# Использование
def my_function():
    logger.info("Starting function")
    try:
        # код
        logger.debug("Debug info")
    except Exception as e:
        logger.error(f"Error occurred: {e}", exc_info=True)
```

---

## ⚙️ Конфигурация

### Environment Variables (.env)

```bash
# Database
DATABASE_URL=postgresql://user:password@localhost:5432/contract_ai

# LLM API Keys
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...

# ChromaDB
CHROMA_PERSIST_DIRECTORY=./chroma_data

# File Storage
UPLOAD_DIR=./data/uploads
NORMALIZED_DIR=./data/normalized
REPORTS_DIR=./data/reports
TEMPLATES_DIR=./data/templates
EXPORTS_DIR=./data/exports

# Application
APP_ENV=development  # development | production
LOG_LEVEL=INFO

# UI
NEXT_PUBLIC_API_URL=/api
```

### settings.py

```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # Database
    database_url: str
    
    # LLM
    anthropic_api_key: str
    openai_api_key: str
    
    # ChromaDB
    chroma_persist_directory: str
    
    # Storage
    upload_dir: str
    normalized_dir: str
    reports_dir: str
    templates_dir: str
    exports_dir: str
    
    # App
    app_env: str = "development"
    log_level: str = "INFO"
    
    class Config:
        env_file = ".env"

settings = Settings()
```

---

## 🎯 Критерии успеха MVP

### Количественные метрики

1. **Время обработки**
   - Было: 2-4 часа на договор (вручную)
   - Стало: 5-10 минут (AI) + 30 минут (проверка юристом)
   - Цель: 60-80% экономия времени

2. **Точность выявления рисков**
   - AI находит: 80%+ рисков
   - Ложные срабатывания: <20%

3. **Использование**
   - Минимум 10 договоров/неделю
   - Минимум 3 активных пользователя

### Качественные метрики

1. Юристы реально используют систему (не игнорируют)
2. Положительный feedback
3. Запросы на новые функции
4. Готовность рекомендовать другим отделам

### Критерий для перехода к продукту

Если через 2 месяца использования:
- ✅ Обработано 80+ договоров
- ✅ Экономия времени >50%
- ✅ Нет критических багов
- ✅ Юристы довольны

→ МОЖНО упаковывать в продукт для других компаний

---

## 📝 Дополнительные заметки

### Важные напоминания для разработки

1. **Human-in-the-loop обязателен** - никогда не пропускать проверку человеком для критических решений

2. **XML как единый формат** - все документы конвертируются в стандартный XML для единообразной обработки

3. **Гибридный RAG** - комбинация векторного и полнотекстового поиска для надёжности

4. **On-demand векторизация** - не нужно векторизовать всю базу сразу

5. **Версионирование шаблонов** - всегда храним историю изменений шаблонов

6. **Логирование действий** - особенно важно для quick export без проверки

7. **Работа на ноутбуке** - вся инфраструктура должна работать локально для MVP

### Технические ограничения MVP

- Работает только с договорами (не с другими юридическими документами)
- База знаний: ГК РФ + ЗК РФ (основное)
- 3-5 одновременных пользователей
- Хранение истории за 3 месяца
- Один язык: русский

### Расширения для v2.0 (после MVP)

- Автоматическая генерация писем контрагенту
- Интеграция с электронным документооборотом
- Мониторинг изменений законодательства
- Аналитика и отчёты для руководства
- Мобильное приложение
- Поддержка английского языка
- Расширение на другие отрасли

---

## 📚 Полезные ссылки

### Документация

- [LangChain](https://python.langchain.com/)
- [LangGraph](https://langchain-ai.github.io/langgraph/)
- [Anthropic Claude API](https://docs.anthropic.com/)
- [ChromaDB](https://docs.trychroma.com/)
- [Next.js](https://nextjs.org/docs)

### Законодательство

- [КонсультантПлюс](http://www.consultant.ru/)
- [Гарант](https://www.garant.ru/)
- [ГАС "Правосудие"](https://sudrf.ru/)

---

**Конец документа. Версия 1.0 от 11 октября 2025**
