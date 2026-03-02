# 📊 Contract AI System - Текущее состояние проекта

**Последнее обновление:** 2026-03-02
**Статус:** Stage 3 Smart Router Production — ЗАВЕРШЁН ✅

---

## 🔴 КРИТИЧЕСКИ ВАЖНО ДЛЯ НОВОГО АГЕНТА

### Принципы работы с пользователем

1. **Единый интерфейс "Стеклянный ящик"** — ВСЯ работа ведётся в ОДНОМ файле `admin/pages/1_Process_Documents.py`. Это единая Streamlit-страница, которая показывает ВСЕ промежуточные результаты обработки. НЕ создавай отдельные страницы для новых этапов — ПРИСОЕДИНЯЙ к существующей!

2. **После реализации каждого подпункта (2.1, 2.2, 2.3, 2.4) — ТЕСТИРУЕМ!** Запускаешь Streamlit (`streamlit run admin/pages/1_Process_Documents.py --server.port=8501`) и пользователь тестирует. Только после его ОК идёшь дальше!

3. **Python 3.9 совместимость!** На машине пользователя Python 3.9. НЕ используй:
   - `str | Path` (union type syntax) → используй `Union[str, Path]`
   - `list[X]` → используй `List[X]`
   - `tuple[X, Y]` → используй `Tuple[X, Y]`
   - `dict[X, Y]` → используй `Dict[X, Y]`
   Всё из `typing`!

4. **Streamlit session_state обязателен!** Результаты обработки ОБЯЗАТЕЛЬНО сохранять в `st.session_state`. Иначе при нажатии на любую кнопку (скачать, утвердить и т.п.) весь скрипт перезапускается и результаты пропадают. Текущая реализация уже исправлена — НЕ ЛОМАЙ.

5. **Весь UI на РУССКОМ языке!**

6. **Пользователь общается по-русски** и ожидает русские ответы.

7. **DOCX-версия генерируется ВСЕГДА** для любого формата документа. В стеклянном ящике есть отдельный раздел "Проверка форматирования документа" где пользователь видит DOCX-превью.

---

## 🎯 Цель проекта

Единая платформа для полного жизненного цикла договоров:
- **Pre-Execution:** Анализ черновиков, сравнение с шаблонами, риск-скоринг, генерация итогового документа
- **Post-Execution:** Цифровизация подписанных документов в исполняемые данные

---

## 🏗️ Архитектура "Стеклянного ящика"

### Что это такое

"Стеклянный ящик" — это Streamlit UI, который показывает ВСЕ промежуточные результаты каждого этапа обработки договора. Пользователь видит:
- Что извлёк text extractor (метод, символы, страницы)
- Что нашёл Level 1 (regex + SpaCy): ИНН, даты, суммы — с указанием НАЗНАЧЕНИЯ каждой сущности в системе
- Что извлёк LLM: структурированные данные (стороны, предмет, финансы, сроки, санкции) — с метриками токенов и стоимости
- RAG-результаты (похожие договоры)
- Валидацию (ошибки + предупреждения)
- Детальный анализ разделов (Section Analysis) — каждый раздел договора анализируется LLM с рекомендациями
- **Проверку форматирования** — DOCX-версия документа с предпросмотром
- **Сравнение с шаблоном** (Stage 2.2) — отклонения от эталона
- Итоговые метрики (время, стоимость, модель, уверенность)
- Действия (утвердить, скачать JSON, скачать DOCX, отклонить)

### Структура страницы (порядок разделов)

```
1️⃣ Загрузка документа
   - Выбор режима: "Новый договор (Pre-Execution)" / "Подписанный договор (Post-Execution)"
   - File uploader (PDF, DOCX, TXT, XML, HTML, изображения)
   - [Только Pre-Execution] Загрузка эталонного шаблона (Playbook)

2️⃣ Ход обработки (expanders для каждого этапа пайплайна)
   - ✅ Извлечение текста
   - ✅ Level 1 Extraction
   - ✅ LLM Extraction
   - ✅ RAG Filter
   - ⚠️ Validation + Section Analysis (внутри)

📄 Проверка форматирования документа (ОТДЕЛЬНЫЙ раздел!)
   - DOCX-превью через mammoth
   - Скачивание оригинала и DOCX-версии

📋 Сравнение с эталонным шаблоном (Stage 2.2, Pre-Execution only)
   - Вердикт, метрики отклонений, детальный список

🎯 Risk Scoring Engine (Stage 2.3)
   - Базовый риск 0-100
   - Остаточный риск после принятых правок
   - Факторы риска + риск по разделам

🛠️ Генерация итогового документа (Stage 2.4)
   - Вариант A: Исправленный DOCX
   - Вариант B: Протокол разногласий (DOCX + JSON)

3️⃣ Итоговые метрики (время, стоимость, модель, уверенность)

4️⃣ Действия с результатами (утвердить, JSON, DOCX, отклонить)

📋 Протокол разногласий (только Post-Execution)
```

### Ключевой паттерн session_state

```python
# При обработке — сохраняем:
st.session_state["processing_result"] = result
st.session_state["processing_file_name"] = uploaded_file.name
st.session_state["processing_is_new_contract"] = is_new_contract

# При отображении — читаем:
if "processing_result" in st.session_state:
    result = st.session_state["processing_result"]
    # ... отображаем все результаты ...

# Кнопка "Новый анализ" очищает session_state
```

---

## 🚀 Быстрый запуск

```bash
cd ~/Desktop/Contract-AI-System-
source venv/bin/activate  # или создать: python3 -m venv venv

# Установка
pip install -r requirements.txt
pip install 'openai>=1.50.0' spacy pdf2docx htmldocx
python -m spacy download ru_core_news_sm

# .env уже настроен (DeepSeek API key)

# Запуск стеклянного ящика
streamlit run admin/pages/1_Process_Documents.py --server.port=8501
# Открыть: http://localhost:8501
```

### .env (ключевые переменные)
```
DATABASE_URL=sqlite:///./contract_ai.db
DEEPSEEK_API_KEY=<SET_IN_LOCAL_.ENV_ONLY>
DEEPSEEK_BASE_URL=https://api.deepseek.com/v1
DEEPSEEK_MODEL=deepseek-chat
```

---

## 📁 Ключевые файлы

```
Contract-AI-System-/
├── .env                                    # API ключи (НЕ в git!)
├── .env.example                            # Шаблон .env
├── current.md                              # ЭТОТ ФАЙЛ — читай ПЕРВЫМ!
├── config/settings.py                      # Pydantic Settings
├── admin/
│   └── pages/
│       ├── 1_Process_Documents.py          # ⭐⭐⭐ СТЕКЛЯННЫЙ ЯЩИК (единый UI)
│       └── 3_Model_Metrics.py             # 📊 Dashboard метрик Smart Router
├── src/
│   ├── services/
│   │   ├── document_processor.py           # ⭐ Оркестратор пайплайна (6 этапов)
│   │   ├── text_extractor.py               # ⭐ Извлечение текста + конвертация в DOCX
│   │   ├── level1_extractor.py             # Regex + SpaCy NER
│   │   ├── llm_extractor.py               # ⭐ LLM extraction (DeepSeek/OpenAI)
│   │   ├── validation_service.py           # Pydantic валидация
│   │   ├── contract_section_analyzer.py    # Детальный анализ разделов (LLM)
│   │   ├── template_comparator.py          # ⭐ Stage 2.2: Сравнение с шаблоном (НОВЫЙ)
│   │   ├── risk_scorer.py                  # ⭐ Stage 2.3: Rule-based риск-скоринг 0-100
│   │   ├── stage2_document_generator.py    # ⭐ Stage 2.4: Исправленный DOCX + протокол разногласий
│   │   ├── complexity_scorer.py             # ⭐ Stage 3: Оценка сложности документа (0.0-1.0)
│   │   ├── model_router.py                 # ⭐ Stage 3: Smart Router (выбор модели по сложности)
│   │   ├── template_manager.py             # Управление шаблонами (Jinja2 + DOCX)
│   │   └── rag_service.py                  # RAG (отключён, нужен PostgreSQL)
│   ├── models/database.py                  # SQLAlchemy модели (14 таблиц)
│   └── agents/                             # Multi-agent система
├── tests/fixtures/test_supply_contract.txt # Тестовый договор
└── CONTRACT_AI_SYSTEM_SPECIFICATION.md     # Полная спецификация (2168 строк)
```

---

## 📊 Прогресс Stage 2: Pre-Execution

### ✅ 2.1: Загрузка черновиков для анализа — ГОТОВ

Уже было реализовано ранее:
- Режим "Новый договор (Pre-Execution)" в radio-кнопке
- Загрузка файлов всех форматов (PDF, DOCX, TXT, XML, HTML, изображения)
- Полный пайплайн обработки через DocumentProcessor
- **Конвертация ЛЮБОГО формата в DOCX** с сохранением форматирования:
  - PDF → DOCX через `pdf2docx` (макет, таблицы, шрифты)
  - DOCX → оригинал сохраняется
  - TXT → DOCX с интеллектуальным распознаванием структуры (заголовки, пункты, подпункты, списки, блоки подписей)
  - HTML → DOCX через `htmldocx` (стили, таблицы)
  - XML → DOCX через парсинг + форматирование
  - Изображения → OCR (PaddleOCR) → DOCX
- **Отдельный раздел "Проверка форматирования"** в стеклянном ящике с DOCX-превью и скачиванием
- Результаты сохраняются в `st.session_state` (не пропадают при кликах)
- Кнопка "Новый анализ" для сброса

### ✅ 2.2: Сравнение с шаблонами/Playbook — ГОТОВ (код + state-устойчивость + UI)

Что реализовано:
- `src/services/template_comparator.py` — сервис сравнения через LLM
  - `TemplateComparator.compare(draft_text, template_text, contract_type)`
  - Возвращает `TemplateComparisonResult`: deviations, compliance_score, verdict
  - Каждое отклонение: severity (critical/high/medium/low), deviation_type (missing/modified/added/weakened/contradicts), risk, recommendation
- В UI:
  - загрузчик файла шаблона (только Pre-Execution)
  - автоматический запуск сравнения с сохранением сигнатуры шаблона
  - защита от показа устаревших результатов при смене режима/файла
  - фильтрация по severity и принятие рекомендаций в общий список правок Stage 2.4
- Результаты сохраняются в `st.session_state["template_comparison"]`

### ✅ 2.3: Risk Scoring Engine — ГОТОВ

Что реализовано:
- Новый сервис `src/services/risk_scorer.py`
  - Rule-based скоринг 0-100
  - Уровни риска: `critical/high/medium/low`
  - Учитывает:
    - validation errors/warnings
    - отклонения от шаблона (severity + missing sections)
    - эвристики по тексту (неограниченная ответственность, иностранная подсудность, форс-мажор, порядок споров)
    - финансовые условия (предоплата, срок оплаты, неустойка)
    - результаты section analysis
  - Расчёт остаточного риска после принятых рекомендаций
- В `admin/pages/1_Process_Documents.py` добавлен отдельный раздел:
  - текущий риск, остаточный риск, критичные факторы
  - таблица факторов риска
  - таблица рисков по разделам

### ✅ 2.4: Генерация итогового документа — ГОТОВ

Что реализовано:
- Новый сервис `src/services/stage2_document_generator.py`
  - **Вариант А: Исправленный DOCX**
    - генерирует итоговый DOCX на базе текущей DOCX-версии
    - включает структурированный список всех принятых правок
  - **Вариант Б: Протокол разногласий**
    - генерирует DOCX-таблицу "было → стало"
    - + JSON-экспорт протокола
- В UI добавлен раздел "Генерация итогового документа (Stage 2.4)":
  - выбор варианта (для Pre-Execution)
  - автогенерация и кнопки скачивания (`DOCX`/`JSON`)
  - единый `accepted_recommendations` в `st.session_state` для всех источников рекомендаций (section analysis + template comparison) с защитой от дублей

---

## 🏗️ Техническая архитектура

### Pipeline обработки документа (DocumentProcessor)
```
1. Text Extraction (pdfplumber/python-docx/OCR) + конвертация в DOCX
2. Level 1 Extraction (regex + SpaCy — бесплатно)
3. LLM Extraction (DeepSeek-chat — $0.14/1M токенов)
4. RAG Filter (отключён — нужен PostgreSQL + pgvector)
5. Validation (Pydantic v2 + business logic)
6. Section Analysis (опц. — параллельный LLM-анализ каждого раздела, ~60 сек)
```

### Multi-Model Routing
- **DeepSeek-chat** → 90% задач, $0.14/1M токенов (основной)
- **GPT-4o-mini** → Fallback, $0.15/1M токенов
- **Claude Sonnet 4.5** → Для сложных сканов (будущее)
- Все модели вызываются через OpenAI SDK (совместимый API)

### Два режима работы
- **Новый договор (Pre-Execution):** правки вносятся в DOCX, сравнение с шаблоном
- **Подписанный договор (Post-Execution):** оригинал не трогаем, генерируем протокол разногласий

### Конвертация в DOCX (text_extractor.py)
- `_convert_pdf_to_docx()` — через pdf2docx (макет, таблицы)
- `_text_to_docx()` — интеллектуальная конвертация plain text (заголовки, пункты, отступы, Times New Roman 12pt, поля по ГОСТ)
- `_html_to_docx()` — через htmldocx (стили, таблицы)
- `render_docx_preview()` — через mammoth DOCX→HTML для отображения в Streamlit

### Async в Streamlit
```python
# Streamlit не поддерживает async напрямую. Паттерн:
import concurrent.futures

def _run_async(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()

with concurrent.futures.ThreadPoolExecutor() as executor:
    future = executor.submit(_run_async, process_document_async(...))
    result = future.result(timeout=300)
```

---

## ⚠️ Известные проблемы и ограничения

| Проблема | Статус | Решение |
|----------|--------|---------|
| Python 3.9 на машине | Учтено | Используем `Union`, `List`, `Dict` из typing |
| RAG отключён | Ожидание | Нужен PostgreSQL + pgvector |
| PaddleOCR не установлен | Нормально | OCR не нужен для TXT/DOCX/PDF с текстом |
| pdf2docx может падать на сложных PDF | Известно | Fallback на text_to_docx |
| mammoth превью не идеальное | Известно | Лучше скачать DOCX и открыть в Word |

---

## 📋 Оставшиеся этапы (после Stage 2)

### ✅ Stage 3: Smart Router Production — ГОТОВ

Что реализовано:
- `src/services/complexity_scorer.py` — Rule-based оценка сложности документа (0.0-1.0)
  - Факторы: страницы, OCR confidence, объём текста, секции, таблицы, метод извлечения, плотность
- `src/services/model_router.py` — Smart Router (выбор модели по сложности)
  - `select_model(complexity, is_scanned, user_mode)` → model name
  - `get_fallback_model(current_model)` → fallback model
  - Пороги: <0.5 → DeepSeek, 0.5-0.8 → DeepSeek/GPT-4o, >0.8 → Claude
- `src/config/llm_config.py` — Multi-model конфигурация
  - `get_model_credentials()`, `is_model_available()`, `get_available_models()`
  - Cost tracking per model (input/output per 1M tokens)
- **Интеграция в DocumentProcessor:**
  - После text extraction → ComplexityScorer → Router → выбор модели
  - Fallback при ошибке LLM → альтернативная модель → retry
  - `model_selected_by`: router / force / fallback / default
- **UI в 1_Process_Documents.py:**
  - Selectbox режима модели (Smart Router / Force DeepSeek)
  - Отображение complexity score, способа выбора модели, статуса LLM
- **Dashboard:** `admin/pages/3_Model_Metrics.py`
  - Сводка за сессию (документы, стоимость, время, сложность)
  - Группировка по моделям и статусу
  - Графики: стоимость, сложность, время по документам
  - Таблица всех обработок
  - Конфигурация моделей и доступность API ключей
- **Ограничение:** сейчас доступен только DeepSeek API key. Claude и GPT-4o подготовлены — нужно только добавить ключи в .env

### Stage 4: Интеграции + UI
- Векторный поиск похожих договоров (pgvector)
- Интеграция с 1C/ERP
- UI для юристов (Next.js)
- Dashboard мониторинга

---

## 🔧 Технический стек

- **Python 3.9** (на машине пользователя, НЕ 3.10+!)
- **Database:** SQLite (dev) / PostgreSQL 16+ (prod)
- **LLM:** DeepSeek-chat через OpenAI SDK
- **NLP:** SpaCy (ru_core_news_sm)
- **UI:** Streamlit
- **Конвертация:** pdf2docx, htmldocx, python-docx, mammoth
- **Async:** asyncio + ThreadPoolExecutor
- **Валидация:** Pydantic v2
