# 🚀 Детальный план реализации Contract AI System v2.0

> Исторический план. Актуальная политика моделей: DeepSeek V4 Flash для
> стандартных задач и DeepSeek V4 Pro только для сложного экспертного анализа.
> Проверка маршрутизации выполняется офлайн через
> `python scripts/check_llm_routing.py` и не использует API-ключи.

**Версия:** 2.0
**Дата создания:** 2026-01-08
**Общая длительность:** 20 недель (5 этапов)
**Методология:** Итеративная разработка с тестированием после каждого этапа

---

## 📊 Общая структура плана

```
Stage 0: Инфраструктура           [Недели 1-2]   ████░░░░░░░░░░░░░░░░ 10%
Stage 1: Post-Execution MVP       [Недели 3-6]   ░░░░████████░░░░░░░░ 30%
Stage 2: Pre-Execution            [Недели 7-10]  ░░░░░░░░░░░░████████ 40%
Stage 3: Smart Router Production  [Недели 11-14] ░░░░░░░░░░░░░░░░████ 60%
Stage 4: Интеграции + UI          [Недели 15-20] ░░░░░░░░░░░░░░░░░░░░ 100%
```

---

# Stage 0: Инфраструктура и подготовка (Недели 1-2)

**Цель:** Подготовить фундамент системы - база данных, API ключи, базовая архитектура.

## Задачи

### 0.1 Миграция базы данных (День 1-3)

**Файлы для создания:**
- `alembic/versions/002_create_contracts_core.py` - Основная таблица
- `alembic/versions/003_create_related_tables.py` - Связанные таблицы
- `alembic/versions/004_enable_pgvector.py` - Векторное расширение

**Таблицы для создания:**

```sql
1. contracts_core
   - id (UUID, PK)
   - doc_number (VARCHAR(100), NOT NULL, UNIQUE)
   - signed_date (DATE)
   - status (VARCHAR(20), CHECK IN 'negotiating'/'active'/'closed')
   - total_amount (NUMERIC(15,2))
   - currency (CHAR(3), DEFAULT 'RUB')
   - attributes (JSONB) -- Гибкие поля
   - raw_data (JSONB)   -- Полный результат IDP
   - embedding (vector(1536)) -- Для поиска
   - created_at, updated_at (TIMESTAMP)

2. contract_parties
   - id (UUID, PK)
   - contract_id (UUID, FK → contracts_core)
   - role (VARCHAR(20): 'client'/'supplier'/'guarantor')
   - name (VARCHAR(255))
   - inn (VARCHAR(12))
   - kpp (VARCHAR(9))
   - address (TEXT)

3. contract_items
   - id (UUID, PK)
   - contract_id (UUID, FK)
   - item_number (INTEGER)
   - description (TEXT)
   - quantity (NUMERIC(10,2))
   - unit (VARCHAR(20))
   - price (NUMERIC(15,2))

4. payment_schedule
   - id (UUID, PK)
   - contract_id (UUID, FK)
   - payment_type (VARCHAR(50): 'prepayment'/'postpayment'/'milestone')
   - amount (NUMERIC(15,2))
   - percent (NUMERIC(5,2))
   - due_date (DATE)

5. contract_rules
   - id (UUID, PK)
   - contract_id (UUID, FK)
   - rule_type (VARCHAR(50): 'penalty'/'sla'/'termination')
   - trigger_condition (TEXT)
   - formula (JSONB) -- { "rate": 0.001, "base": "total_amount", "cap": 0.1 }
   - original_text (TEXT)

6. negotiation_sessions
   - id (UUID, PK)
   - uploaded_doc_path (TEXT)
   - status (VARCHAR(20): 'analyzing'/'ready'/'archived')
   - template_id (UUID, nullable) -- Ссылка на шаблон для сравнения
   - risk_score (NUMERIC(3,2))
   - created_at (TIMESTAMP)

7. disagreements
   - id (UUID, PK)
   - session_id (UUID, FK → negotiation_sessions)
   - section (VARCHAR(100))
   - their_clause (TEXT)
   - our_standard (TEXT)
   - risk_level (VARCHAR(20): 'critical'/'high'/'medium'/'low')
   - suggested_wording (TEXT)
```

**Тестирование:**
```bash
# Применить миграции
alembic upgrade head

# Проверить структуру
psql -d contract_ai -c "\d contracts_core"
psql -d contract_ai -c "SELECT * FROM pg_extension WHERE extname='vector';"
```

### 0.2 Конфигурация API ключей (День 3-4)

**Файлы для создания/изменения:**
- `src/config/llm_config.py` - Конфигурация моделей

```python
from pydantic_settings import BaseSettings

class LLMConfig(BaseSettings):
    # DeepSeek
    DEEPSEEK_API_KEY: str
    DEEPSEEK_BASE_URL: str = "https://api.deepseek.com/v1"
    DEEPSEEK_MODEL: str = "deepseek-v4-flash"
    DEEPSEEK_MAX_TOKENS: int = 4096

    # Anthropic Claude
    ANTHROPIC_API_KEY: str
    ANTHROPIC_MODEL: str = "claude-4-5-sonnet-20250929"
    ANTHROPIC_MAX_TOKENS: int = 4096

    # OpenAI (Reserve)
    OPENAI_API_KEY: str
    OPENAI_MODEL: str = "gpt-4o"

    # Router Config
    ROUTER_DEFAULT_MODEL: str = "deepseek-v4-flash"
    ROUTER_COMPLEXITY_THRESHOLD: float = 0.8  # Порог для переключения на Claude

    class Config:
        env_file = ".env"
```

**Файл `.env.example`:**
```bash
# LLM API Keys
DEEPSEEK_API_KEY=your_deepseek_key_here
ANTHROPIC_API_KEY=your_anthropic_key_here
OPENAI_API_KEY=your_openai_key_here

# Database
DATABASE_URL=postgresql://user:password@localhost:5432/contract_ai
```

**Тестирование:**
```python
# Офлайн-проверка политики выбора моделей
python scripts/check_llm_routing.py
```

### 0.3 Базовый Smart Router (День 4-5)

**Файл:** `src/services/model_router.py`

**Функционал:**
- Выбор модели по умолчанию (DeepSeek V4 Flash)
- Заглушка для complexity_score
- Принудительный выбор модели через параметр

```python
class ModelRouter:
    def select_model(
        self,
        doc_complexity_score: float = 0.0,
        is_scanned_image: bool = False,
        force_model: Optional[str] = None
    ) -> str:
        """
        Выбор модели для обработки документа.

        Args:
            doc_complexity_score: 0.0-1.0, оценка сложности документа
            is_scanned_image: True если документ - скан/фото
            force_model: Принудительный выбор ('deepseek-v4-flash' | 'deepseek-v4-pro')

        Returns:
            Название модели для использования
        """
        if force_model:
            return force_model

        if is_scanned_image and doc_complexity_score > 0.8:
            return "claude-4-5-sonnet"

        return "deepseek-v4-flash"
```

**Тестирование:**
```python
router = ModelRouter()
assert router.select_model() == "deepseek-v4-flash"
assert router.select_model(force_model="claude-4-5-sonnet") == "claude-4-5-sonnet"
assert router.select_model(doc_complexity_score=0.9, is_scanned_image=True) == "claude-4-5-sonnet"
```

### 0.4 Обновление моделей SQLAlchemy (День 5-7)

**Файл:** `src/models/contracts_v2.py`

**Создать ORM модели:**
- `ContractCore` (основной класс)
- `ContractParty`, `ContractItem`, `PaymentSchedule`, `ContractRule`
- `NegotiationSession`, `Disagreement`

**Особенности:**
- Использование JSONB для `attributes` и `raw_data`
- Связи: One-to-Many (contract → parties, items, etc.)
- Индексы на `doc_number`, `signed_date`, `status`
- GIN индекс на JSONB поля

### 0.5 Базовые Pydantic схемы (День 7)

**Файл:** `src/schemas/contracts_v2_schemas.py`

```python
class ContractCoreCreate(BaseModel):
    doc_number: str = Field(..., max_length=100)
    signed_date: Optional[date] = None
    status: Literal["negotiating", "active", "closed"] = "negotiating"
    total_amount: Optional[Decimal] = None
    currency: str = Field(default="RUB", max_length=3)
    attributes: Dict[str, Any] = Field(default_factory=dict)
    raw_data: Dict[str, Any] = Field(default_factory=dict)

class IntermediateJSON(BaseModel):
    """Стандартный формат обмена между AI и БД"""
    metadata: Dict[str, Any]
    financials: Optional[Dict[str, Any]] = None
    parties: List[Dict[str, Any]] = Field(default_factory=list)
    items: List[Dict[str, Any]] = Field(default_factory=list)
    payment_schedule: List[Dict[str, Any]] = Field(default_factory=list)
    rules: List[Dict[str, Any]] = Field(default_factory=list)
```

---

## ✅ Критерии завершения Stage 0

- [ ] База данных мигрирована, все 7 таблиц созданы
- [ ] pgvector расширение установлено и работает
- [ ] `.env` файл настроен с API ключами (DeepSeek + Anthropic + OpenAI)
- [ ] Тестовое подключение к DeepSeek API работает
- [ ] Тестовое подключение к Anthropic API работает
- [ ] `ModelRouter` выбирает модель по логике
- [ ] SQLAlchemy модели созданы и соответствуют схеме БД
- [ ] Pydantic схемы валидируют тестовые данные

**Время на тестирование:** 1 день
**Общее время Stage 0:** 2 недели

---

# Stage 1: Post-Execution MVP (Недели 3-6)

**Цель:** Научиться обрабатывать подписанные документы и превращать их в цифровые двойники.

## Задачи

### 1.1 Endpoint: Загрузка подписанного документа (Неделя 3, День 1-3)

**Файл:** `src/api/contracts/post_execution_routes.py`

```python
@router.post("/api/v1/contracts/digitize")
async def digitize_contract(
    file: UploadFile = File(...),
    force_model: Optional[str] = Query(None, regex="^(deepseek-v4-flash|deepseek-v4-pro)$"),
    background_tasks: BackgroundTasks
):
    """
    Загрузка подписанного документа для цифровизации.

    Args:
        file: PDF/DOCX файл подписанного договора
        force_model: Принудительный выбор модели (опционально)

    Returns:
        { "task_id": "uuid", "status": "processing" }
    """
    # 1. Сохранить файл
    # 2. Определить тип документа (по расширению)
    # 3. Запустить асинхронную обработку
    # 4. Вернуть task_id
```

**Тестирование:**
```bash
curl -X POST "http://localhost:8000/api/v1/contracts/digitize" \
  -F "file=@test_contract.pdf" \
  -F "force_model=deepseek-v4-flash"
```

### 1.2 Orchestrator: Обработка документа (Неделя 3, День 3-7)

**Файл:** `src/services/post_execution_orchestrator.py`

```python
class PostExecutionOrchestrator:
    def __init__(self, model_router: ModelRouter, llm_client: LLMClient):
        self.router = model_router
        self.llm = llm_client

    async def process_document(self, file_path: str, force_model: Optional[str] = None):
        """
        Полный пайплайн обработки подписанного документа.

        Этапы:
        1. Извлечение текста (OCR если нужно)
        2. Level 1: Regex/SpaCy extraction
        3. Level 2: LLM extraction (через Router)
        4. Валидация результата (Pydantic)
        5. Сохранение в БД
        6. Генерация embedding
        """
        # Stage 1: Text Extraction
        text = await self.extract_text(file_path)

        # Stage 2: Level 1 Extraction (Regex/SpaCy)
        level1_data = self.extract_level1(text)

        # Stage 3: Select Model
        model = self.router.select_model(force_model=force_model)

        # Stage 4: LLM Extraction
        intermediate_json = await self.llm.extract_structured_data(text, model)

        # Stage 5: Merge Level 1 + LLM data
        merged_data = self.merge_data(level1_data, intermediate_json)

        # Stage 6: Validate with Pydantic
        validated = IntermediateJSON(**merged_data)

        # Stage 7: Save to DB
        contract_id = await self.save_to_db(validated)

        # Stage 8: Generate embedding
        await self.generate_embedding(contract_id, text)

        return contract_id
```

### 1.3 Level 1 Extractor: Regex + SpaCy (Неделя 4, День 1-3)

**Файл:** `src/services/level1_extractor.py`

**Извлекаемые данные:**
- Даты (regex: `\d{2}\.\d{2}\.\d{4}`)
- ИНН (regex + checksum validation)
- Суммы (regex: `\d+[\s,]?\d*\s?(руб|USD|EUR)`)
- Номер договора
- Email, телефоны

```python
class Level1Extractor:
    def extract(self, text: str) -> Dict[str, Any]:
        return {
            "dates": self.extract_dates(text),
            "amounts": self.extract_amounts(text),
            "inn_numbers": self.extract_inn(text),
            "doc_number": self.extract_doc_number(text),
            "emails": self.extract_emails(text),
        }
```

**Тестирование:**
```python
text = "Договор №123/2026 от 15.01.2026. Сумма: 100 000 руб. ИНН: 7707083893"
result = extractor.extract(text)
assert "123/2026" in result["doc_number"]
assert 100000 in result["amounts"]
```

### 1.4 LLM Client: Универсальный клиент (Неделя 4, День 3-5)

**Файл:** `src/services/llm_client.py`

```python
class LLMClient:
    def __init__(self, config: LLMConfig):
        self.config = config
        self.deepseek = DeepSeekClient(config.DEEPSEEK_API_KEY)
        self.anthropic = AnthropicClient(config.ANTHROPIC_API_KEY)

    async def extract_structured_data(
        self,
        text: str,
        model: str,
        schema: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Отправить текст в LLM и получить структурированные данные.

        Args:
            text: Текст документа
            model: Название модели ('deepseek-v4-flash' | 'deepseek-v4-pro')
            schema: JSON Schema для структурированного вывода

        Returns:
            IntermediateJSON в виде словаря
        """
        prompt = self._build_extraction_prompt(text, schema)

        if model == "deepseek-v4-flash":
            response = await self.deepseek.chat(prompt)
        elif model == "claude-4-5-sonnet":
            response = await self.anthropic.chat(prompt)
        else:
            raise ValueError(f"Unknown model: {model}")

        return self._parse_response(response)
```

### 1.5 Database Service: Сохранение данных (Неделя 5, День 1-3)

**Файл:** `src/services/database_service.py`

```python
class DatabaseService:
    async def save_contract(self, data: IntermediateJSON) -> UUID:
        """
        Сохранить договор в БД.

        Создает записи в:
        - contracts_core
        - contract_parties
        - contract_items
        - payment_schedule
        - contract_rules
        """
        async with AsyncSession() as session:
            # 1. Create core contract
            contract = ContractCore(
                doc_number=data.metadata["doc_number"],
                total_amount=data.financials.get("amount"),
                attributes=data.metadata,
                raw_data=data.dict()
            )
            session.add(contract)
            await session.flush()

            # 2. Create parties
            for party_data in data.parties:
                party = ContractParty(contract_id=contract.id, **party_data)
                session.add(party)

            # 3. Create items, payments, rules...

            await session.commit()
            return contract.id
```

### 1.6 Endpoint: Получение структурированных данных (Неделя 5, День 3-5)

**Файл:** `src/api/contracts/post_execution_routes.py`

```python
@router.get("/api/v1/contracts/{contract_id}/structured")
async def get_structured_contract(contract_id: UUID):
    """
    Получить цифровой двойник договора.

    Returns:
        {
            "id": "uuid",
            "doc_number": "123/2026",
            "signed_date": "2026-01-15",
            "total_amount": 100000,
            "parties": [...],
            "items": [...],
            "payment_schedule": [...],
            "rules": [...]
        }
    """
```

### 1.7 Integration Tests (Неделя 6)

**Файл:** `tests/integration/test_post_execution.py`

**Тестовые сценарии:**
1. Загрузка простого договора (PDF) → проверка записи в БД
2. Загрузка со сканом (force_model=claude) → проверка использования правильной модели
3. Загрузка с некорректными данными → проверка валидации
4. Получение структурированных данных → проверка полноты данных

---

## ✅ Критерии завершения Stage 1

- [ ] Endpoint `/contracts/digitize` работает с PDF и DOCX
- [ ] Level 1 Extractor извлекает базовые данные (даты, ИНН, суммы)
- [ ] LLM Client использует DeepSeek V4 Flash и извлекает структуру
- [ ] Данные сохраняются во все таблицы (core, parties, items, schedule, rules)
- [ ] Endpoint `/contracts/{id}/structured` возвращает полные данные
- [ ] Интеграционные тесты проходят для 3+ типов документов
- [ ] Стоимость обработки документа < $0.05 (через DeepSeek)

**Время на тестирование:** 3 дня
**Общее время Stage 1:** 4 недели

---

# Stage 2: Pre-Execution (Недели 7-10)

**Цель:** Создать систему анализа черновиков, сравнения с шаблонами и генерации протокола разногласий.

## Задачи

### 2.1 Система шаблонов и Playbook (Неделя 7)

**Файл:** `src/services/template_manager.py`

**Функционал:**
- Загрузка эталонных шаблонов договоров
- Извлечение "ключевых пунктов" из шаблона
- Хранение в `templates` таблице (новая миграция)

```sql
CREATE TABLE templates (
    id UUID PRIMARY KEY,
    name VARCHAR(255),
    doc_type VARCHAR(50),
    key_clauses JSONB,  -- Важные условия для сравнения
    full_text TEXT,
    created_at TIMESTAMP
);
```

### 2.2 Endpoint: Загрузка черновика (Неделя 7)

**Файл:** `src/api/contracts/pre_execution_routes.py`

```python
@router.post("/api/v1/negotiation/upload")
async def upload_draft(
    file: UploadFile = File(...),
    template_id: Optional[UUID] = None,
    force_model: Optional[str] = None
):
    """
    Загрузка черновика для анализа.

    Args:
        file: Черновик договора от контрагента
        template_id: ID шаблона для сравнения (опционально)
        force_model: Принудительный выбор модели

    Returns:
        { "session_id": "uuid", "status": "analyzing" }
    """
```

### 2.3 Сравнение с шаблоном (Неделя 8)

**Файл:** `src/services/clause_comparator.py`

**Логика:**
1. Извлечь структуру из входящего документа (LLM)
2. Извлечь key_clauses из шаблона
3. Сравнить пункт-в-пункт:
   - Отсутствующие пункты
   - Измененные формулировки
   - Новые условия (которых нет в шаблоне)

```python
class ClauseComparator:
    async def compare(
        self,
        draft_clauses: List[Dict],
        template_clauses: List[Dict]
    ) -> List[Disagreement]:
        """
        Сравнение условий черновика с шаблоном.

        Returns:
            Список расхождений с risk_level
        """
```

### 2.4 Risk Scoring Engine (Неделя 8)

**Файл:** `src/services/risk_scorer.py`

**Критерии риска:**
- **Critical:** Неограниченная ответственность, иностранная подсудность
- **High:** Предоплата >50%, срок оплаты >60 дней
- **Medium:** Отклонение от стандартных штрафов
- **Low:** Изменение названий разделов

```python
class RiskScorer:
    def score_clause(self, clause: Dict, context: Dict) -> str:
        """
        Оценка уровня риска для одного пункта.

        Returns:
            'critical' | 'high' | 'medium' | 'low'
        """
```

### 2.5 Генерация протокола разногласий (Неделя 9)

**Файл:** `src/services/disagreement_generator.py`

**Выходной формат:**
```json
{
  "session_id": "uuid",
  "overall_risk_score": 0.65,
  "disagreements": [
    {
      "section": "5. Ответственность сторон",
      "their_clause": "Поставщик несет неограниченную ответственность...",
      "our_standard": "Ответственность ограничена суммой договора",
      "risk_level": "critical",
      "suggested_wording": "Изменить п. 5.1: 'Ответственность Сторон ограничивается суммой настоящего Договора'",
      "explanation": "Неограниченная ответственность создает критический финансовый риск"
    }
  ]
}
```

### 2.6 Endpoint: Получение протокола (Неделя 9)

```python
@router.get("/api/v1/negotiation/{session_id}/disagreements")
async def get_disagreements(session_id: UUID):
    """
    Получить протокол разногласий по сессии анализа.
    """
```

### 2.7 Экспорт в DOCX с комментариями (Неделя 10)

**Файл:** `src/services/redline_generator.py`

**Функционал:**
- Создать DOCX копию входящего документа
- Добавить комментарии (Word Comments) к проблемным пунктам
- Выделить цветом:
  - Красный = Critical risk
  - Оранжевый = High risk
  - Желтый = Medium risk

```python
class RedlineGenerator:
    def generate(self, session_id: UUID, output_path: str):
        """
        Генерация DOCX с протоколом разногласий.
        """
```

### 2.8 Integration Tests (Неделя 10)

**Тестовые сценарии:**
1. Загрузка черновика без шаблона → базовый анализ рисков
2. Загрузка черновика с шаблоном → полное сравнение
3. Генерация протокола для 10+ расхождений
4. Экспорт DOCX с комментариями

---

## ✅ Критерии завершения Stage 2

- [ ] Система шаблонов работает (загрузка, хранение, выборка)
- [ ] Endpoint `/negotiation/upload` принимает черновики
- [ ] ClauseComparator находит расхождения
- [ ] RiskScorer правильно оценивает уровень риска
- [ ] Endpoint `/negotiation/{id}/disagreements` возвращает протокол
- [ ] Экспорт в DOCX с цветным выделением работает
- [ ] Интеграционные тесты покрывают все сценарии

**Время на тестирование:** 2 дня
**Общее время Stage 2:** 4 недели

---

# Stage 3: Smart Router Production (Недели 11-14)

**Цель:** Превратить заглушку Router в полноценную систему выбора модели с метриками.

## Задачи

### 3.1 Complexity Scorer (Неделя 11)

**Файл:** `src/services/complexity_scorer.py`

**Факторы сложности:**
1. **Качество скана** (если PDF/изображение):
   - OCR confidence < 0.8 → +0.3 к score
   - Размытость, наклон → +0.2
2. **Структура документа:**
   - Таблицы с >5 колонками → +0.2
   - Вложенные списки → +0.1
3. **Объем:**
   - > 50 страниц → +0.2

```python
class ComplexityScorer:
    def score(self, file_path: str) -> float:
        """
        Оценка сложности документа (0.0 - 1.0).

        Returns:
            0.0-0.5 = простой (DeepSeek справится)
            0.5-0.8 = средний (DeepSeek с осторожностью)
            0.8-1.0 = сложный (нужен Claude)
        """
```

### 3.2 Обновление ModelRouter (Неделя 11-12)

**Файл:** `src/services/model_router.py`

**Новая логика:**
```python
class ModelRouterV2:
    def select_model(
        self,
        file_path: str,
        force_model: Optional[str] = None,
        user_preference: str = "optimal"  # 'optimal' | 'expert'
    ) -> str:
        if force_model:
            return force_model

        if user_preference == "expert":
            return "claude-4-5-sonnet"

        # Auto-routing
        complexity = self.scorer.score(file_path)
        is_scan = self._is_scanned_image(file_path)

        if is_scan and complexity > 0.8:
            return "claude-4-5-sonnet"

        return "deepseek-v4-flash"
```

### 3.3 Fallback механизм (Неделя 12)

**Сценарии:**
1. DeepSeek API недоступен → fallback на Claude
2. DeepSeek вернул низкий confidence (<0.6) → retry с Claude
3. Обе модели недоступны → очередь на повтор через 5 минут

```python
class LLMClientWithFallback:
    async def extract_with_fallback(self, text: str, primary_model: str):
        try:
            result = await self.extract(text, primary_model)
            if result["confidence"] < 0.6:
                logger.warning("Low confidence, retrying with Claude")
                result = await self.extract(text, "claude-4-5-sonnet")
            return result
        except APIError:
            logger.error("Primary model failed, using fallback")
            return await self.extract(text, self._get_fallback_model(primary_model))
```

### 3.4 Метрики и логирование (Неделя 13)

**Таблица:** `llm_usage_metrics`

```sql
CREATE TABLE llm_usage_metrics (
    id UUID PRIMARY KEY,
    document_id UUID,
    model_used VARCHAR(50),
    complexity_score NUMERIC(3,2),
    tokens_input INTEGER,
    tokens_output INTEGER,
    cost_usd NUMERIC(10,6),
    processing_time_sec NUMERIC(6,2),
    confidence_score NUMERIC(3,2),
    created_at TIMESTAMP
);
```

**Dashboard данные:**
- Средняя стоимость документа по моделям
- Распределение: DeepSeek vs Claude
- Средний confidence по типам документов

### 3.5 User Preference API (Неделя 13)

**Добавить параметр в endpoints:**

```python
@router.post("/api/v1/contracts/digitize")
async def digitize_contract(
    file: UploadFile,
    mode: str = Query("optimal", regex="^(optimal|expert)$")
):
    """
    mode:
      - optimal: Автоматический выбор (DeepSeek по умолчанию)
      - expert: Принудительно Claude 4.5 Sonnet
    """
```

### 3.6 A/B тестирование (Неделя 14)

**Файл:** `tests/ab_test_models.py`

**Методология:**
1. Взять 50 тестовых документов (разной сложности)
2. Обработать каждый через DeepSeek И Claude
3. Сравнить:
   - Точность извлечения (F1 score)
   - Стоимость
   - Время обработки
4. Определить оптимальный порог complexity_threshold

---

## ✅ Критерии завершения Stage 3

- [ ] ComplexityScorer оценивает сложность документа
- [ ] ModelRouter выбирает модель автоматически
- [ ] Fallback механизм работает при недоступности модели
- [ ] Метрики записываются в `llm_usage_metrics`
- [ ] User может выбрать режим (optimal/expert)
- [ ] A/B тестирование проведено, порог оптимизирован
- [ ] Dashboard показывает статистику использования моделей

**Время на тестирование:** 2 дня
**Общее время Stage 3:** 4 недели

---

# Stage 4: Интеграции + UI (Недели 15-20)

**Цель:** Завершение системы - доп. соглашения, векторный поиск, интеграции с внешними системами.

## Задачи

### 4.1 Amendment Flow (Неделя 15)

**Endpoint:**
```python
@router.post("/api/v1/contracts/{contract_id}/amendment")
async def upload_amendment(
    contract_id: UUID,
    file: UploadFile
):
    """
    Загрузка доп. соглашения к существующему договору.

    Логика:
    1. Найти родительский договор
    2. Извлечь изменения (что изменилось: сумма, срок, условия)
    3. Создать новую версию в БД
    4. Обновить основную запись (если изменились критичные поля)
    """
```

**Таблица:** `contract_amendments`

```sql
CREATE TABLE contract_amendments (
    id UUID PRIMARY KEY,
    parent_contract_id UUID REFERENCES contracts_core(id),
    amendment_number VARCHAR(50),
    changes JSONB,  -- { "total_amount": { "old": 100000, "new": 150000 } }
    signed_date DATE,
    created_at TIMESTAMP
);
```

### 4.2 Векторный поиск (Неделя 16)

**Файл:** `src/services/vector_search.py`

**Функционал:**
- Генерация embedding при сохранении договора
- Поиск похожих договоров по тексту
- Поиск по семантическому запросу

```python
class VectorSearch:
    async def find_similar_contracts(
        self,
        query_text: str,
        limit: int = 5
    ) -> List[UUID]:
        """
        Найти похожие договоры по тексту.

        Uses:
            pgvector cosine similarity
        """
        embedding = await self.generate_embedding(query_text)

        query = """
        SELECT id, doc_number,
               1 - (embedding <=> :query_embedding) AS similarity
        FROM contracts_core
        ORDER BY embedding <=> :query_embedding
        LIMIT :limit
        """
```

**Endpoint:**
```python
@router.get("/api/v1/contracts/search/similar")
async def search_similar(
    query: str,
    limit: int = Query(5, le=20)
):
    """
    Семантический поиск похожих договоров.

    Example:
        GET /contracts/search/similar?query=договор поставки оборудования
    """
```

### 4.3 Интеграция с 1C (Неделя 17-18)

**Файл:** `src/integrations/onec_integration.py`

**Функционал:**
1. **Export в 1C:**
   - Выгрузка договора в XML формат 1C
   - Mapping полей: контрагент, сумма, реквизиты
2. **Import из 1C:**
   - Загрузка реквизитов контрагента из 1C
   - Синхронизация статусов договоров

```python
class OneCIntegration:
    def export_to_1c(self, contract_id: UUID) -> str:
        """
        Генерация XML файла для импорта в 1C.

        Returns:
            XML string
        """

    def import_counterparty_details(self, inn: str) -> Dict:
        """
        Получение реквизитов контрагента из 1C по ИНН.
        """
```

**Endpoint:**
```python
@router.get("/api/v1/contracts/{contract_id}/export/1c")
async def export_to_1c(contract_id: UUID):
    """
    Экспорт договора в формат 1C.
    """
```

### 4.4 UI: Dashboard для юристов (Неделя 19)

**Компоненты (React/Next.js):**

1. **Upload Page:**
   - Drag&drop для загрузки документов
   - Выбор режима: Pre-Execution / Post-Execution
   - Выбор модели: Optimal / Expert

2. **Negotiation Dashboard:**
   - Список сессий анализа черновиков
   - Карточка с протоколом разногласий
   - Скачать DOCX с комментариями

3. **Contracts Dashboard:**
   - Список всех договоров
   - Фильтры: статус, сумма, дата, контрагент
   - Карточка договора с вкладками:
     - Общая информация
     - Стороны
     - Спецификация (items)
     - График платежей
     - Правила и штрафы
     - История изменений (amendments)

4. **Search Page:**
   - Полнотекстовый поиск
   - Семантический поиск (векторный)
   - Фильтры по metadata

### 4.5 Мониторинг сроков и алерты (Неделя 20)

**Файл:** `src/services/deadline_monitor.py`

**Функционал:**
- Cron задача (Celery Beat): проверка раз в день
- Поиск договоров с приближающимися сроками
- Генерация уведомлений:
  - Срок окончания договора (за 30 дней)
  - Срок платежа (за 7 дней)
  - Просроченные обязательства

```python
class DeadlineMonitor:
    async def check_deadlines(self):
        """
        Проверка всех активных договоров на приближающиеся сроки.

        Creates:
            Notifications в таблицу `notifications`
        """
```

**Таблица:** `notifications`

```sql
CREATE TABLE notifications (
    id UUID PRIMARY KEY,
    contract_id UUID REFERENCES contracts_core(id),
    notification_type VARCHAR(50),  -- 'deadline_approaching' | 'payment_due' | 'contract_expiring'
    message TEXT,
    is_read BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP
);
```

### 4.6 Final Testing (Неделя 20)

**End-to-End тесты:**
1. Полный цикл: черновик → анализ → протокол разногласий → правка → финализация → цифровизация
2. Загрузка 100 реальных документов → проверка точности
3. Нагрузочное тестирование: 50 одновременных загрузок
4. Тестирование fallback механизмов

---

## ✅ Критерии завершения Stage 4

- [ ] Amendment flow работает (обновление существующих договоров)
- [ ] Векторный поиск возвращает релевантные результаты
- [ ] Интеграция с 1C: экспорт/импорт работает
- [ ] UI Dashboard полностью функционален
- [ ] Мониторинг сроков генерирует уведомления
- [ ] End-to-End тесты проходят
- [ ] Документация для пользователей готова

**Время на тестирование:** 3 дня
**Общее время Stage 4:** 6 недель

---

# 📊 Резюме плана

| Этап | Недели | Ключевые результаты | Риски |
|------|--------|---------------------|-------|
| **Stage 0** | 1-2 | БД, API ключи, базовый Router | Проблемы с pgvector установкой |
| **Stage 1** | 3-6 | Post-Execution MVP, цифровизация документов | Качество извлечения данных |
| **Stage 2** | 7-10 | Pre-Execution, протокол разногласий | Сложность сравнения условий |
| **Stage 3** | 11-14 | Smart Router, метрики, fallback | Оптимизация порога переключения |
| **Stage 4** | 15-20 | Интеграции, UI, мониторинг | Интеграция с 1C, UX |

**Общая длительность:** 20 недель
**Команда:** 2-3 разработчика (Backend + Frontend + QA)

---

# 🎯 Ключевые метрики успеха

1. **Точность извлечения данных:** >95% для ключевых полей (сумма, дата, ИНН)
2. **Стоимость обработки:** <$0.05 на документ (средняя)
3. **Время обработки:** <2 минуты на документ
4. **Покрытие тестами:** >80%
5. **Доля использования DeepSeek:** >85% (экономия)
6. **User Satisfaction:** >4.5/5 (после пилота)

---

# 📝 Рекомендации по старту

1. **Начать с Stage 0 немедленно** - инфраструктура критична
2. **Параллельно подготовить тестовые данные:**
   - 50 реальных договоров разных типов
   - 10 шаблонов для сравнения
   - Ground truth разметка для метрик
3. **Создать dev/staging окружения:**
   - dev: для разработки
   - staging: для тестирования перед продом
4. **Настроить CI/CD:**
   - Автоматические тесты при каждом коммите
   - Автодеплой в staging
5. **Еженедельные sync meetings** для отслеживания прогресса

---

**Готовы начинать?** 🚀
