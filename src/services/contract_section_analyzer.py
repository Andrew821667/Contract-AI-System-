"""
Contract Section Analyzer - Динамический анализ разделов договора

Автоматически определяет структуру документа и анализирует каждый раздел
"""

import logging
import json
from datetime import datetime
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from openai import AsyncOpenAI
import os

logger = logging.getLogger(__name__)


@dataclass
class ContractSection:
    """Раздел договора"""
    number: str  # Номер раздела (например, "1", "2.1")
    title: str  # Название раздела
    text: str  # Полный текст раздела
    start_pos: int  # Позиция начала в документе
    end_pos: int  # Позиция конца в документе


@dataclass
class Recommendation:
    """Структурированная рекомендация с предлагаемым текстом"""
    reason: str  # Почему нужно изменить
    proposed_text: str  # Предлагаемый текст пункта/положения договора
    action_type: str  # "add" | "modify" | "remove"
    priority: str  # "critical" | "important" | "optional"


@dataclass
class SectionAnalysis:
    """Результат анализа одного раздела"""
    section_number: str
    section_title: str

    # Сравнение с собственными договорами
    own_contracts_comparison: str  # "✅ Соответствует" / "⚠️ Есть замечания" / "❌ Не соответствует"
    own_contracts_details: List[Dict[str, str]]  # Детальные проверки

    # RAG проверка (правовая база)
    rag_legal_check: str  # Соответствие законодательству
    rag_legal_references: List[str]  # Ссылки на законы (ГК РФ, НК РФ и т.д.)

    # Вывод и рекомендации
    conclusion: str  # Итоговый вывод
    warnings: List[str]  # Предупреждения
    recommendations: List[Recommendation]  # Структурированные рекомендации с предлагаемым текстом


@dataclass
class ComplexAnalysis:
    """Комплексный анализ всего договора"""
    integrity_checks: List[Dict[str, str]]  # Проверки целостности
    risk_assessment: Dict[str, List[str]]  # Оценка рисков (low/medium/high)
    legal_compliance: List[Dict[str, str]]  # Соответствие законодательству
    best_practices: List[Dict[str, str]]  # Сравнение с лучшими практиками
    overall_score: int  # Общая оценка из 100
    legal_reliability: float  # Юридическая надежность из 10
    compliance_percent: int  # Процент соответствия
    strengths: List[str]  # Сильные стороны
    critical_improvements: List[str]  # Критичные доработки


class ContractSectionAnalyzer:
    """Анализатор разделов договора через LLM"""

    def __init__(self, model: str = "deepseek-chat", api_key: str = None,
                 base_url: str = None):
        self.model = model
        client_kwargs = {"api_key": api_key or os.getenv("OPENAI_API_KEY")}
        if base_url:
            client_kwargs["base_url"] = base_url
        self.client = AsyncOpenAI(**client_kwargs)

    async def extract_sections(self, contract_text: str) -> List[ContractSection]:
        """
        Извлекает структуру документа (разделы и подразделы) через regex.
        Быстрый парсер без LLM-вызова (~0 сек вместо ~70 сек).
        """
        logger.info("Extracting contract sections (regex)...")
        import re

        sections = []

        # Паттерны заголовков разделов:
        # "1. ПРЕДМЕТ ДОГОВОРА", "2. ЦЕНА И ПОРЯДОК РАСЧЕТОВ"
        # "Раздел 1. ПРЕДМЕТ", "РАЗДЕЛ I. ПРЕДМЕТ"
        # "I. ПРЕДМЕТ ДОГОВОРА", "II. ЦЕНА"
        # Также: "1. Предмет договора" (смешанный регистр)
        patterns = [
            # "1. НАЗВАНИЕ" или "1. Название" — цифра + точка + текст (>= 2 слов заглавных ИЛИ первое слово заглавное)
            r'^[ \t]*(\d+)\.\s+([А-ЯЁA-Z][А-ЯЁа-яёA-Za-z\s,\-\(\)]+)',
            # "Раздел 1. НАЗВАНИЕ"
            r'^[ \t]*[Рр]аздел\s+(\d+)[\.\)]\s*([А-ЯЁA-Z][А-ЯЁа-яёA-Za-z\s,\-\(\)]+)',
            # Римские цифры: "I. НАЗВАНИЕ", "II. НАЗВАНИЕ"
            r'^[ \t]*((?:X{0,3}(?:IX|IV|V?I{0,3})))\.\s+([А-ЯЁA-Z][А-ЯЁа-яёA-Za-z\s,\-\(\)]+)',
        ]

        # Пробуем каждый паттерн, берём тот, что даёт >= 3 совпадений
        best_matches = []
        best_pattern = None

        for pattern in patterns:
            matches = list(re.finditer(pattern, contract_text, re.MULTILINE))
            # Фильтруем — заголовок должен быть >= 3 символов и не быть подпунктом
            filtered = []
            for m in matches:
                title = m.group(2).strip()
                # Пропускаем слишком короткие (подпункты типа "1.1")
                if len(title) >= 3:
                    filtered.append(m)
            if len(filtered) > len(best_matches):
                best_matches = filtered
                best_pattern = pattern

        if not best_matches:
            logger.warning("No section headers found by regex, trying LLM fallback...")
            return await self._llm_extract_sections(contract_text)

        logger.info(f"Found {len(best_matches)} section headers with pattern: {best_pattern}")

        for i, match in enumerate(best_matches):
            number = match.group(1).strip()
            title = match.group(2).strip().rstrip('.')

            start_pos = match.start()
            if i + 1 < len(best_matches):
                end_pos = best_matches[i + 1].start()
            else:
                end_pos = len(contract_text)

            section_text = contract_text[start_pos:end_pos].strip()

            sections.append(ContractSection(
                number=number,
                title=title,
                text=section_text,
                start_pos=start_pos,
                end_pos=end_pos
            ))

        logger.info(f"Extracted {len(sections)} sections via regex")
        return sections

    async def _llm_extract_sections(self, contract_text: str) -> List[ContractSection]:
        """LLM-fallback для извлечения разделов (если regex не сработал)"""
        logger.info("Using LLM fallback for section extraction...")

        prompt = f"""Проанализируй структуру договора и извлеки все разделы.

ДОГОВОР:
{contract_text}

Верни JSON:
{{
  "sections": [
    {{"number": "1", "title": "ПРЕДМЕТ ДОГОВОРА", "text": "полный текст раздела...", "start_pos": 0, "end_pos": 100}},
    ...
  ]
}}

ВАЖНО: только основные разделы (не подпункты 1.1, 1.2), полный текст каждого раздела.
"""

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "Ты эксперт по анализу юридических документов."},
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"},
                temperature=0.1
            )

            result = json.loads(response.choices[0].message.content)
            sections = []
            for s in result.get("sections", []):
                sections.append(ContractSection(
                    number=s.get("number", ""),
                    title=s.get("title", ""),
                    text=s.get("text", ""),
                    start_pos=s.get("start_pos", 0),
                    end_pos=s.get("end_pos", 0)
                ))
            logger.info(f"LLM extracted {len(sections)} sections")
            return sections

        except Exception as e:
            logger.error(f"LLM section extraction failed: {e}")
            return []

    async def analyze_section(
        self,
        section: ContractSection,
        similar_contracts: List[Dict[str, Any]],
        full_contract_text: str
    ) -> SectionAnalysis:
        """
        Анализирует один раздел договора

        Args:
            section: Раздел для анализа
            similar_contracts: Похожие договоры из RAG базы
            full_contract_text: Полный текст договора для контекста

        Returns:
            Детальный анализ раздела
        """
        logger.info(f"Analyzing section {section.number}: {section.title}")

        # Формируем контекст похожих договоров
        similar_context = ""
        if similar_contracts:
            similar_context = f"\nПОХОЖИЕ ДОГОВОРЫ В БАЗЕ ({len(similar_contracts)}):\n"
            for c in similar_contracts[:3]:
                similar_context += f"- {c.get('contract_number', 'N/A')}: {c.get('doc_type', 'N/A')}, сумма {c.get('amount', 0):,.0f}₽\n"

        prompt = f"""Проведи детальный юридический анализ раздела договора.

📅 ТЕКУЩАЯ ДАТА: {datetime.now().strftime('%d.%m.%Y')} — учитывай при проверке сроков и дат в договоре!

РАЗДЕЛ {section.number}: {section.title}
{section.text}

ПОЛНЫЙ ТЕКСТ ДОГОВОРА (для системного контекста):
{full_contract_text}

{similar_context}

ПОРЯДОК АНАЛИЗА:
1️⃣ СИСТЕМНЫЙ анализ раздела В КОНТЕКСТЕ ВСЕГО ДОГОВОРА (не изолированно!)
2️⃣ Сравни с типовыми/эталонными договорами
3️⃣ Проверь по актуальной правовой базе РФ (ГК РФ, НК РФ, АПК РФ, отраслевые законы)
4️⃣ Проверь арифметическую корректность (суммы, проценты, итоги должны сходиться)
5️⃣ Проверь актуальность дат (текущая дата: {datetime.now().strftime('%d.%m.%Y')})

⚠️ ПРИНЦИПЫ СИСТЕМНОГО АНАЛИЗА:
- Предмет договора часто РАСКРЫВАЕТСЯ в других разделах и приложениях. Если в разделе "Предмет" есть ссылка на приложение — НЕ считай предмет неопределённым!
- При обнаружении неполноты в любом разделе — ПРОВЕРЬ, не раскрыта ли информация в других частях договора
- Суммы этапов ДОЛЖНЫ совпадать с общей суммой. Если не сходятся — это арифметическая ошибка
- Даты: если срок уже истёк (раньше {datetime.now().strftime('%d.%m.%Y')}) — отметь это
- НЕ предлагай добавлять условия, которые УЖЕ ЕСТЬ в других разделах договора

ТРЕБУЕТСЯ:
1. Оценка соответствия эталонным договорам (✅/⚠️/❌)
2. Детальные проверки элементов раздела (3-5 ключевых элементов)
3. Проверка по законодательству РФ
4. Ссылки на конкретные статьи законов
5. Арифметическая проверка (суммы, проценты, итоги)
6. Проверка актуальности дат
7. Итоговый вывод
8. Предупреждения (если есть)
9. Рекомендации по улучшению С ПРЕДЛАГАЕМЫМ ТЕКСТОМ ПУНКТА

⚠️ ВАЖНО ДЛЯ РЕКОМЕНДАЦИЙ:
- Каждая рекомендация должна включать КОНКРЕТНЫЙ текст пункта/положения договора
- Формат: "reason" (почему нужно), "proposed_text" (что именно добавить/изменить), "action_type", "priority"
- Предлагаемый текст должен быть готов к использованию (юридически корректен, конкретен)
- НЕ предлагай добавлять то, что уже есть в других разделах/приложениях договора

Верни результат в JSON:
{{
  "own_contracts_comparison": "✅ Соответствует" | "⚠️ Есть замечания" | "❌ Не соответствует",
  "own_contracts_details": [
    {{"element": "Название элемента", "fact": "✅ Что есть", "recommendation": "Рекомендация"}},
    ...
  ],
  "rag_legal_check": "✅ Соответствует ГК РФ...",
  "rag_legal_references": ["ГК РФ ст. 454", "НК РФ ст. 164", ...],
  "conclusion": "Раздел проработан хорошо / требует доработки / ...",
  "warnings": ["Предупреждение 1", ...],
  "recommendations": [
    {{
      "reason": "Почему нужно изменить (например: отсутствует порядок приемки, требуемый ГК РФ ст. 513)",
      "proposed_text": "4.2. Приемка товара осуществляется Покупателем в течение 5 рабочих дней с момента доставки. Покупатель обязан провести осмотр товара и подписать акт приемки-передачи либо мотивированный отказ от приемки.",
      "action_type": "add",
      "priority": "critical"
    }},
    ...
  ]
}}

⚠️ ВАЖНО ДЛЯ action_type - РАЗЛИЧАЙ ТОЧНО:
- "add" - ДОПОЛНИТЬ к существующему разделу (в разделе УЖЕ ЕСТЬ текст, но нужно добавить дополнительное условие/пункт)
  Пример: Раздел "Ответственность" есть, но отсутствует пункт о неустойке → action_type="add"

- "modify" - ЗАМЕНИТЬ/ИЗМЕНИТЬ существующий пункт (пункт УЖЕ ЕСТЬ, но сформулирован некорректно/неполно)
  Пример: Срок поставки указан 30 дней, но по ГК РФ должен быть конкретный → action_type="modify"

- "remove" - УДАЛИТЬ пункт (пункт противоречит закону или ущемляет права)
  Пример: Штраф 50% - незаконно по ГК РФ → action_type="remove"

priority: "critical" | "important" | "optional" (см. матрицу ниже)

⚠️ МАТРИЦА ПРИОРИТЕТОВ (СТРОГО СОБЛЮДАЙ):

🔴 "critical" — ТОЛЬКО если:
  - Нарушает императивную норму закона (ничтожность/оспоримость сделки по ст. 168, 432 ГК РФ)
  - Делает договор юридически недействительным
  - Создаёт реальный финансовый ущерб > 30% суммы договора
  Примеры: отсутствие существенных условий, противоречие закону, кабальные условия

🟡 "important" — если:
  - Создаёт умеренный юридический/финансовый риск
  - Отсутствует рекомендуемый (но не обязательный по закону) раздел
  - Формулировка двусмысленна и может привести к спорам
  Примеры: нет порядка приёмки, нечёткие сроки, слабая ответственность

🟢 "optional" — если:
  - Опечатки, орфографические ошибки (напр. "Мсква" → "Москва")
  - Незаполненные данные сторон (адрес, ИНН, ОГРН) — это НЕ риск, а необходимость дозаполнить
  - Стилистические улучшения, best practices, форматирование
  Примеры: опечатка в фамилии, пустое поле реквизитов, отсутствие нумерации страниц

⛔ НЕ ПУТАЙ "отсутствие данных" и "юридический дефект":
- Пустое поле ИНН/адреса/реквизитов = optional (просто нужно заполнить перед подписанием)
- Отсутствие целого раздела об ответственности = important или critical
- Опечатка в названии города = optional (не влияет на юридическую силу)
"""

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "Ты опытный юрист-эксперт по договорному праву РФ. Проводишь детальный анализ разделов договоров."},
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"},
                temperature=0.2
            )

            result = json.loads(response.choices[0].message.content)

            # Парсим рекомендации как структурированные объекты
            recommendations_raw = result.get("recommendations", [])
            recommendations = []
            for rec in recommendations_raw:
                if isinstance(rec, dict):
                    recommendations.append(Recommendation(
                        reason=rec.get("reason", ""),
                        proposed_text=rec.get("proposed_text", ""),
                        action_type=rec.get("action_type", "modify"),
                        priority=rec.get("priority", "optional")
                    ))
                else:
                    # Fallback для старого формата (простые строки)
                    recommendations.append(Recommendation(
                        reason=str(rec),
                        proposed_text="",
                        action_type="modify",
                        priority="optional"
                    ))

            return SectionAnalysis(
                section_number=section.number,
                section_title=section.title,
                own_contracts_comparison=result.get("own_contracts_comparison", "⚠️ Не проверено"),
                own_contracts_details=result.get("own_contracts_details", []),
                rag_legal_check=result.get("rag_legal_check", ""),
                rag_legal_references=result.get("rag_legal_references", []),
                conclusion=result.get("conclusion", ""),
                warnings=result.get("warnings", []),
                recommendations=recommendations
            )

        except Exception as e:
            logger.error(f"Error analyzing section {section.number}: {e}")
            return SectionAnalysis(
                section_number=section.number,
                section_title=section.title,
                own_contracts_comparison="❌ Ошибка анализа",
                own_contracts_details=[],
                rag_legal_check="Ошибка анализа",
                rag_legal_references=[],
                conclusion=f"Не удалось проанализировать раздел: {str(e)}",
                warnings=[],
                recommendations=[]
            )

    async def complex_analysis(
        self,
        contract_text: str,
        sections: List[ContractSection],
        section_analyses: List[SectionAnalysis],
        extracted_data: Dict[str, Any]
    ) -> ComplexAnalysis:
        """
        Комплексный анализ всего договора с учетом взаимосвязей разделов

        Args:
            contract_text: Полный текст договора
            sections: Список всех разделов
            section_analyses: Анализы отдельных разделов
            extracted_data: Извлеченные структурированные данные

        Returns:
            Комплексный анализ
        """
        logger.info("Performing complex contract analysis...")

        # Подготовка контекста
        sections_summary = "\n".join([f"{s.number}. {s.title}" for s in sections])
        warnings_count = sum(len(a.warnings) for a in section_analyses)

        prompt = f"""Проведи КОМПЛЕКСНЫЙ анализ договора с учетом взаимосвязей между разделами.

СТРУКТУРА ДОГОВОРА:
{sections_summary}

КОЛИЧЕСТВО РАЗДЕЛОВ: {len(sections)}
ПРЕДУПРЕЖДЕНИЙ ПО РАЗДЕЛАМ: {warnings_count}

ИЗВЛЕЧЕННЫЕ ДАННЫЕ:
{json.dumps(extracted_data, ensure_ascii=False, indent=2)}

ЗАДАЧА:
Проанализируй договор ЦЕЛИКОМ и оцени:
1. Целостность и согласованность (проверь взаимосвязи между разделами)
2. Юридические риски (низкий/средний/высокий)
3. Соответствие законодательству РФ
4. Сравнение с лучшими практиками
5. Общую оценку и рекомендации

Верни результат в JSON:
{{
  "integrity_checks": [
    {{"check": "Суммы в разделах совпадают", "result": "✅ Да", "comment": "Комментарий"}},
    ...
  ],
  "risk_assessment": {{
    "low": ["Риск 1", ...],
    "medium": ["Риск 1", ...],
    "high": ["Критичный риск", ...]
  }},
  "legal_compliance": [
    {{"law": "ГК РФ (Купля-продажа)", "status": "✅ Полное соответствие", "references": "ст. 454-491"}},
    ...
  ],
  "best_practices": [
    {{"aspect": "Структура договора", "current": "9 разделов", "best": "9-11 разделов", "score": "✅"}},
    ...
  ],
  "overall_score": 87,
  "legal_reliability": 8.5,
  "compliance_percent": 90,
  "strengths": ["Сильная сторона 1", ...],
  "critical_improvements": ["ОБЯЗАТЕЛЬНО: Доработка 1", ...]
}}
"""

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "Ты главный юрист с 20-летним опытом. Проводишь экспертизу договоров на высшем уровне."},
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"},
                temperature=0.3
            )

            result = json.loads(response.choices[0].message.content)

            return ComplexAnalysis(
                integrity_checks=result.get("integrity_checks", []),
                risk_assessment=result.get("risk_assessment", {"low": [], "medium": [], "high": []}),
                legal_compliance=result.get("legal_compliance", []),
                best_practices=result.get("best_practices", []),
                overall_score=result.get("overall_score", 0),
                legal_reliability=result.get("legal_reliability", 0.0),
                compliance_percent=result.get("compliance_percent", 0),
                strengths=result.get("strengths", []),
                critical_improvements=result.get("critical_improvements", [])
            )

        except Exception as e:
            logger.error(f"Error in complex analysis: {e}")
            return ComplexAnalysis(
                integrity_checks=[],
                risk_assessment={"low": [], "medium": [], "high": []},
                legal_compliance=[],
                best_practices=[],
                overall_score=0,
                legal_reliability=0.0,
                compliance_percent=0,
                strengths=[],
                critical_improvements=[f"Ошибка комплексного анализа: {str(e)}"]
            )

    async def analyze_full_contract(
        self,
        contract_text: str,
        similar_contracts: List[Dict[str, Any]],
        extracted_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Полный анализ договора: структура + разделы + комплексный анализ

        Returns:
            Dict с ключами:
            - sections: List[ContractSection]
            - section_analyses: List[SectionAnalysis]
            - complex_analysis: ComplexAnalysis
        """
        # 1. Извлекаем разделы
        sections = await self.extract_sections(contract_text)

        # 2. Анализируем все разделы ПАРАЛЛЕЛЬНО (asyncio.gather)
        import asyncio
        logger.info(f"Starting parallel analysis of {len(sections)} sections...")
        section_analyses = await asyncio.gather(
            *[self.analyze_section(section, similar_contracts, contract_text)
              for section in sections]
        )
        section_analyses = list(section_analyses)
        logger.info(f"Parallel analysis completed: {len(section_analyses)} sections analyzed")

        # 3. Комплексный анализ
        complex_analysis = await self.complex_analysis(
            contract_text,
            sections,
            section_analyses,
            extracted_data
        )

        return {
            "sections": sections,
            "section_analyses": section_analyses,
            "complex_analysis": complex_analysis
        }
