"""
LLM Extractor - Level 2 Extraction
Извлечение сложных данных через LLM (Smart Router)

Извлекает:
- Стороны договора (полная информация)
- Сроки выполнения / действия договора
- Условия оплаты и платежный график
- Обязательства сторон
- Санкции и штрафы
- Условия расторжения
- Риски и особые условия
"""

import logging
import json
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
import time

# OpenAI client
try:
    from openai import AsyncOpenAI
except ImportError:
    AsyncOpenAI = None

logger = logging.getLogger(__name__)


@dataclass
class LLMExtractionResult:
    """Результат LLM извлечения"""
    data: Dict[str, Any]  # Извлеченные данные
    model_used: str  # Какая модель использована
    tokens_input: int
    tokens_output: int
    cost_usd: float
    processing_time: float
    confidence: float  # Общая уверенность
    raw_response: str  # Сырой ответ LLM для отладки


class LLMExtractor:
    """
    Level 2 extractor с использованием LLM через Smart Router

    Использует промпты для извлечения структурированных данных
    """

    def __init__(self, openai_api_key: str, model: str = "gpt-4o-mini"):
        """
        Args:
            openai_api_key: API ключ OpenAI
            model: Модель для использования (по умолчанию gpt-4o-mini для тестов)
        """
        if not AsyncOpenAI:
            raise ImportError("openai package required. pip install openai")

        self.client = AsyncOpenAI(api_key=openai_api_key)
        self.model = model

        # Стоимость токенов (на 1M токенов)
        self.costs = {
            "gpt-4o-mini": {"input": 0.15, "output": 0.60},
            "gpt-4o": {"input": 2.50, "output": 10.00},
            "gpt-4": {"input": 30.00, "output": 60.00}
        }

        logger.info(f"LLMExtractor initialized with model: {self.model}")

    async def extract(self, text: str,
                     level1_entities: Optional[Dict[str, Any]] = None) -> LLMExtractionResult:
        """
        Извлекает структурированные данные из текста договора

        Args:
            text: Полный текст документа
            level1_entities: Результаты Level 1 extraction (для контекста)

        Returns:
            LLMExtractionResult с извлеченными данными
        """
        start_time = time.time()

        # Строим промпт
        prompt = self._build_extraction_prompt(text, level1_entities)

        # Вызываем LLM
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": self._get_system_prompt()},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,  # Low temperature для consistency
                response_format={"type": "json_object"}  # JSON mode
            )

            # Парсим ответ
            raw_response = response.choices[0].message.content
            extracted_data = json.loads(raw_response)

            # Метрики
            tokens_input = response.usage.prompt_tokens
            tokens_output = response.usage.completion_tokens
            cost_usd = self._calculate_cost(tokens_input, tokens_output)
            processing_time = time.time() - start_time

            # Оценка confidence
            confidence = extracted_data.get("_meta", {}).get("confidence", 0.85)

            logger.info(f"LLM extraction complete: "
                       f"model={self.model}, "
                       f"tokens={tokens_input}+{tokens_output}, "
                       f"cost=${cost_usd:.6f}, "
                       f"time={processing_time:.2f}s")

            return LLMExtractionResult(
                data=extracted_data,
                model_used=self.model,
                tokens_input=tokens_input,
                tokens_output=tokens_output,
                cost_usd=cost_usd,
                processing_time=processing_time,
                confidence=confidence,
                raw_response=raw_response
            )

        except Exception as e:
            logger.error(f"LLM extraction failed: {e}")
            raise

    def _get_system_prompt(self) -> str:
        """Системный промпт для извлечения данных"""
        return """Ты - эксперт по анализу договоров.
Извлекай структурированные данные из текста договора.

ВАЖНО:
- Возвращай ТОЛЬКО валидный JSON
- Используй русский язык для значений
- Если данных нет - используй null
- Добавь поле "_meta" с confidence (0.0-1.0) для каждого раздела

⚠️ КРИТИЧЕСКИ ВАЖНО ДЛЯ СПЕЦСИМВОЛОВ И АДРЕСОВ:
1. СПЕЦСИМВОЛЫ: Сохраняй ВСЕ спецсимволы как есть (№, «, », —, -, /, \, и т.д.)
   - Пример: "Договор №123/2025" → сохрани ТОЧНО "Договор №123/2025"
   - Пример: ИНН "7707083893" → сохрани ТОЧНО "7707083893"
   - Пример: "р/с 40702810400000000001" → сохрани ТОЧНО "40702810400000000001"

2. АДРЕСА: Ищи ПОЛНЫЙ адрес в разделе "Реквизиты" или "Адреса и реквизиты сторон"
   - Извлекай адрес ПОЛНОСТЬЮ: индекс, страна, регион, город, улица, дом, корпус, офис
   - Пример ПРАВИЛЬНОГО извлечения: "119991, Россия, г. Москва, Ленинский проспект, д. 38А, корп. 2, оф. 405"
   - НЕ сокращай адрес! НЕ пропускай части адреса!
   - Если в договоре написано "г. Москва" - сохраняй "г. Москва", а не просто "Москва"

3. БАНКОВСКИЕ РЕКВИЗИТЫ: Извлекай с максимальной точностью
   - р/с (расчетный счет) - 20 цифр
   - к/с (корреспондентский счет) - 20 цифр
   - БИК - 9 цифр
   - Сохраняй ВСЕ цифры, не укорачивай!

Формат ответа:
{
  "parties": {
    "supplier": {
      "name": "Полное наименование (сохраняй кавычки «», скобки, спецсимволы)",
      "inn": "10 или 12 цифр (без пробелов)",
      "ogrn": "13 или 15 цифр",
      "kpp": "9 цифр",
      "legal_address": "ПОЛНЫЙ адрес из Реквизитов: индекс, страна, регион, город, улица, дом, корпус, офис",
      "actual_address": "Фактический адрес (если указан отдельно от юридического)",
      "representative": "ФИО представителя (сохраняй точно как в договоре)",
      "position": "Должность представителя",
      "bank_account": "Расчетный счет (20 цифр)",
      "bank_name": "Наименование банка",
      "bic": "БИК банка (9 цифр)",
      "correspondent_account": "Корр. счет (20 цифр)"
    },
    "customer": {
      "name": "Полное наименование (сохраняй кавычки «», скобки, спецсимволы)",
      "inn": "10 или 12 цифр (без пробелов)",
      "ogrn": "13 или 15 цифр",
      "kpp": "9 цифр",
      "legal_address": "ПОЛНЫЙ адрес из Реквизитов: индекс, страна, регион, город, улица, дом, корпус, офис",
      "actual_address": "Фактический адрес (если указан отдельно от юридического)",
      "representative": "ФИО представителя (сохраняй точно как в договоре)",
      "position": "Должность представителя",
      "bank_account": "Расчетный счет (20 цифр)",
      "bank_name": "Наименование банка",
      "bic": "БИК банка (9 цифр)",
      "correspondent_account": "Корр. счет (20 цифр)"
    },
    "_meta": {"confidence": 0.95}
  },
  "subject": {
    "description": "Краткое описание предмета (1-2 предложения)",
    "full_description": "ПОЛНОЕ описание предмета договора на основе LLM-анализа всех разделов. Опиши ЧТО поставляется/выполняется, В КАКОМ объеме, КАК будет происходить, КАКИЕ обязательства сторон. НЕ копируй текст - создай связное описание своими словами.",
    "type": "supply|service|work|mixed|...",
    "_meta": {"confidence": 0.90, "source": "LLM analysis of sections 1, 3, 4"}
  },
  "term": {
    "start_date": "YYYY-MM-DD",
    "end_date": "YYYY-MM-DD",
    "duration_days": 365,
    "_meta": {"confidence": 0.90}
  },
  "financials": {
    "total_amount": 1000000.00,
    "currency": "RUB",
    "vat_included": true,
    "vat_rate": 20,
    "_meta": {"confidence": 0.95}
  },
  "payment": {
    "method": "bank_transfer",
    "terms": "...",
    "schedule": [
      {"type": "prepayment", "amount": 300000, "due_date": "YYYY-MM-DD"}
    ],
    "_meta": {"confidence": 0.85}
  },
  "obligations": {
    "supplier": ["...", "..."],
    "customer": ["...", "..."],
    "_meta": {"confidence": 0.80}
  },
  "penalties": [
    {
      "type": "delay|breach|...",
      "amount_formula": "0.1% per day (сохраняй спецсимволы)",
      "cap": "10% of contract",
      "description": "..."
    }
  ],
  "termination": {
    "grounds": ["...", "..."],
    "notice_period_days": 30,
    "_meta": {"confidence": 0.75}
  },
  "risks": [
    {"type": "...", "description": "...", "severity": "low|medium|high"}
  ],
  "_meta": {
    "overall_confidence": 0.85,
    "sections_extracted": 8
  }
}"""

    def _build_extraction_prompt(self, text: str,
                                  level1_entities: Optional[Dict[str, Any]] = None) -> str:
        """Строит промпт для извлечения"""
        prompt_parts = ["Извлеки структурированные данные из следующего договора:\n\n"]

        # Добавляем Level 1 entities как контекст (если есть)
        if level1_entities:
            prompt_parts.append("**Контекст (Level 1 extraction):**\n")

            if level1_entities.get('dates'):
                dates_str = ", ".join(e.value for e in level1_entities['dates'][:5])
                prompt_parts.append(f"- Найденные даты: {dates_str}\n")

            if level1_entities.get('amounts'):
                amounts_str = ", ".join(f"{e.value}" for e in level1_entities['amounts'][:3])
                prompt_parts.append(f"- Найденные суммы: {amounts_str}\n")

            if level1_entities.get('inns'):
                inns_str = ", ".join(e.value for e in level1_entities['inns'])
                prompt_parts.append(f"- ИНН: {inns_str}\n")

            if level1_entities.get('contract_numbers'):
                num = level1_entities['contract_numbers'][0].value
                prompt_parts.append(f"- Номер договора: {num}\n")

            prompt_parts.append("\n")

        # Добавляем текст договора (ограничиваем до 8000 символов для GPT-4o-mini)
        max_chars = 8000
        contract_text = text[:max_chars]
        if len(text) > max_chars:
            contract_text += "\n\n[...текст обрезан...]"

        prompt_parts.append(f"**Текст договора:**\n\n{contract_text}\n\n")
        prompt_parts.append("Верни JSON со всеми извлеченными данными.")

        return "".join(prompt_parts)

    def _calculate_cost(self, tokens_input: int, tokens_output: int) -> float:
        """Рассчитывает стоимость запроса"""
        costs = self.costs.get(self.model, {"input": 0, "output": 0})

        cost_input = (tokens_input / 1_000_000) * costs["input"]
        cost_output = (tokens_output / 1_000_000) * costs["output"]

        return cost_input + cost_output
