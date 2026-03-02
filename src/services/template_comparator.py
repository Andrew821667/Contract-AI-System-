"""
Template Comparator - Сравнение черновика договора с эталонным шаблоном

Этап Stage 2.2: Pre-Execution
- Загрузка эталонного шаблона (DOCX/PDF/TXT)
- Посекционное сравнение черновика с шаблоном через LLM
- Выявление отклонений, пропущенных разделов, рисков
"""

import logging
import json
import asyncio
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from openai import AsyncOpenAI
import os

logger = logging.getLogger(__name__)


@dataclass
class DeviationItem:
    """Одно отклонение от шаблона"""
    section: str           # Раздел договора
    severity: str          # "critical" | "high" | "medium" | "low"
    deviation_type: str    # "missing" | "modified" | "added" | "weakened" | "contradicts"
    template_text: str     # Текст из шаблона (эталон)
    draft_text: str        # Текст из черновика
    description: str       # Описание отклонения
    risk: str              # Какой риск несёт отклонение
    recommendation: str    # Что рекомендуется сделать


@dataclass
class TemplateComparisonResult:
    """Результат сравнения черновика с шаблоном"""
    # Общая статистика
    total_deviations: int
    critical_count: int
    high_count: int
    medium_count: int
    low_count: int

    # Детали
    deviations: List[DeviationItem]
    missing_sections: List[str]       # Разделы шаблона, отсутствующие в черновике
    extra_sections: List[str]         # Разделы черновика, отсутствующие в шаблоне

    # Итог
    compliance_score: int             # 0-100, насколько черновик соответствует шаблону
    summary: str                      # Краткий итог сравнения
    verdict: str                      # "approved" | "minor_changes" | "major_changes" | "reject"


class TemplateComparator:
    """Сравнивает черновик договора с эталонным шаблоном через LLM"""

    def __init__(self, model: str = "deepseek-chat", api_key: str = None,
                 base_url: str = None):
        self.model = model
        client_kwargs = {"api_key": api_key or os.getenv("OPENAI_API_KEY")}
        if base_url:
            client_kwargs["base_url"] = base_url
        self.client = AsyncOpenAI(**client_kwargs)

    async def compare(
        self,
        draft_text: str,
        template_text: str,
        contract_type: str = "неизвестный"
    ) -> TemplateComparisonResult:
        """
        Сравнивает черновик с шаблоном

        Args:
            draft_text: Текст черновика договора
            template_text: Текст эталонного шаблона
            contract_type: Тип договора (для контекста)

        Returns:
            TemplateComparisonResult с детальным анализом отклонений
        """
        logger.info(f"Starting template comparison: draft={len(draft_text)} chars, template={len(template_text)} chars")

        # Обрезаем текст если слишком длинный (лимит контекста LLM)
        # DeepSeek-chat: 64K токенов (~250K символов), оставляем запас на промпт и ответ
        max_chars = 50000
        draft_trimmed = draft_text[:max_chars]
        template_trimmed = template_text[:max_chars]

        from datetime import datetime
        current_date = datetime.now().strftime('%d.%m.%Y')

        prompt = f"""Проведи ДЕТАЛЬНОЕ семантико-юридическое сравнение черновика договора с эталонным шаблоном компании.

📅 ТЕКУЩАЯ ДАТА: {current_date} — учитывай при проверке сроков и дат!
ТИП ДОГОВОРА: {contract_type}

═══════════════════════════════════════
ЭТАЛОННЫЙ ШАБЛОН (как ДОЛЖНО быть):
═══════════════════════════════════════
{template_trimmed}

═══════════════════════════════════════
ЧЕРНОВИК ДОГОВОРА (что прислали / составлен):
═══════════════════════════════════════
{draft_trimmed}

═══════════════════════════════════════

ЗАДАЧА: Проведи СЕМАНТИКО-ЮРИДИЧЕСКОЕ сравнение черновика с шаблоном.

⚠️ ГЛАВНЫЙ ПРИНЦИП СРАВНЕНИЯ:
Сравнивай НЕ слово в слово, а ПО ЮРИДИЧЕСКОМУ СМЫСЛУ!
- Если черновик выражает ту же юридическую норму другими словами — это НЕ отклонение
- Если формулировка отличается, но юридический результат одинаков — это НЕ отклонение
- Отклонение = РАЗНИЦА В ЮРИДИЧЕСКОМ СМЫСЛЕ, правах, обязанностях или рисках сторон
- Перефразирование без изменения смысла = НЕ фиксировать как отклонение

Примеры НЕ-отклонений (не фиксируй!):
- Шаблон: "Исполнитель обязуется выполнить работы" → Черновик: "Исполнитель выполняет работы" (тот же смысл)
- Шаблон: "в течение 5 рабочих дней" → Черновик: "не позднее 5 рабочих дней" (тот же смысл)
- Разный порядок разделов (если все разделы присутствуют)

Примеры РЕАЛЬНЫХ отклонений (фиксируй!):
- Шаблон: "штраф 0.1% в день" → Черновик: "штраф 0.5% в день" (изменён размер ответственности)
- Шаблон: раздел "Ограничения изменений" → Черновик: раздел отсутствует (утрачена защита)
- Шаблон: "подсудность г. Москва" → Черновик: "подсудность г. Тамбов" (изменена юрисдикция)

ВИДЫ ОТКЛОНЕНИЙ:
- "missing" — юридически значимый раздел/условие из шаблона отсутствует в черновике
- "modified" — юридический смысл условия изменён (ослаблен или усилен)
- "added" — в черновике есть условие, которого нет в шаблоне (может нести дополнительные обязательства/риски)
- "weakened" — защита одной из сторон ослаблена по сравнению с шаблоном
- "contradicts" — черновик противоречит шаблону по юридическому смыслу или нарушает законодательство РФ

ТАКЖЕ ПРОВЕРЯЙ (но с адекватной severity):
- Опечатки в юридически значимых данных (ФИО, реквизиты, адреса, суммы) — severity "low", но фиксировать обязательно
- Несовпадение фактических данных (ИНН, БИК, р/с, адреса) между шаблоном и черновиком — severity "low"/"medium"
- Такие ошибки НЕ являются юридическими рисками, но ОБЯЗАТЕЛЬНЫ к исправлению перед подписанием

SEVERITY (СТРОГО СОБЛЮДАЙ ПРОПОРЦИОНАЛЬНОСТЬ!):
- "critical" — ТОЛЬКО: нарушает императивную норму закона, делает договор ничтожным/оспоримым (ст. 168, 432 ГК РФ), кабальные условия
- "high" — существенное изменение прав/обязанностей сторон, создающее реальный риск спора или финансовых потерь
- "medium" — заметное юридическое отклонение, рекомендуется согласовать, но не создаёт прямого риска
- "low" — опечатки, несовпадение реквизитов, стилистика, форматирование (обязательно к исправлению, но не юридический риск)

Верни JSON:
{{
  "deviations": [
    {{
      "section": "Название раздела",
      "severity": "critical|high|medium|low",
      "deviation_type": "missing|modified|added|weakened|contradicts",
      "template_text": "Текст из шаблона (если есть)",
      "draft_text": "Текст из черновика (если есть)",
      "description": "Описание отклонения",
      "risk": "Какой риск это несёт",
      "recommendation": "Что рекомендуется сделать"
    }}
  ],
  "missing_sections": ["Раздел 1", "Раздел 2"],
  "extra_sections": ["Раздел X"],
  "compliance_score": 75,
  "summary": "Краткий итог сравнения (2-3 предложения)",
  "verdict": "minor_changes|major_changes|approved|reject"
}}

ВАЖНО:
- Сравнивай ПО ЮРИДИЧЕСКОМУ СМЫСЛУ, не по буквальному совпадению слов!
- НЕ фиксируй как отклонение перефразирование без изменения юридического смысла
- Анализируй ВСЕ разделы — и юридический смысл, и фактические данные (реквизиты, ФИО, суммы)
- Ссылайся на конкретные статьи ГК РФ где применимо

📊 АРИФМЕТИЧЕСКАЯ ПРОВЕРКА (ОБЯЗАТЕЛЬНО!):
- Проверяй суммы этапов/фаз — они ДОЛЖНЫ совпадать с общей суммой договора
- Если суммы этапов не сходятся с итогом — это арифметическая ошибка, фиксируй как отклонение
- Проверяй в ОБОИХ документах (и в шаблоне, и в черновике) — ошибка может быть в любом из них
- Если ошибка есть в шаблоне — укажи это явно

📅 ПРОВЕРКА ДАТ:
- Текущая дата: {current_date}. Если сроки/даты в договоре уже истекли — отметь это
- Проверяй логику дат: дата начала < дата окончания, этапы идут последовательно

🔗 СИСТЕМНЫЙ АНАЛИЗ:
- Предмет договора часто раскрывается в приложениях и других разделах — учитывай это
- Если раздел ссылается на приложение — НЕ считай информацию отсутствующей
- compliance_score: 100 = полное соответствие, 0 = полное несоответствие
- verdict: "approved" (>90%), "minor_changes" (70-90%), "major_changes" (40-70%), "reject" (<40%)
"""

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "Ты ведущий юрист-эксперт по договорному праву РФ с 15-летним опытом. "
                                   "Проводишь экспертное сравнение договоров с эталонными шаблонами компании. "
                                   "Находишь все отклонения, оцениваешь риски, даёшь конкретные рекомендации."
                    },
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"},
                temperature=0.2
            )

            result = json.loads(response.choices[0].message.content)

            # Парсим отклонения
            deviations = []
            for d in result.get("deviations", []):
                deviations.append(DeviationItem(
                    section=d.get("section", ""),
                    severity=d.get("severity", "medium"),
                    deviation_type=d.get("deviation_type", "modified"),
                    template_text=d.get("template_text", ""),
                    draft_text=d.get("draft_text", ""),
                    description=d.get("description", ""),
                    risk=d.get("risk", ""),
                    recommendation=d.get("recommendation", "")
                ))

            # Считаем статистику
            critical = sum(1 for d in deviations if d.severity == "critical")
            high = sum(1 for d in deviations if d.severity == "high")
            medium = sum(1 for d in deviations if d.severity == "medium")
            low = sum(1 for d in deviations if d.severity == "low")

            comparison_result = TemplateComparisonResult(
                total_deviations=len(deviations),
                critical_count=critical,
                high_count=high,
                medium_count=medium,
                low_count=low,
                deviations=deviations,
                missing_sections=result.get("missing_sections", []),
                extra_sections=result.get("extra_sections", []),
                compliance_score=result.get("compliance_score", 0),
                summary=result.get("summary", ""),
                verdict=result.get("verdict", "major_changes")
            )

            logger.info(f"Template comparison completed: {len(deviations)} deviations, "
                       f"score={comparison_result.compliance_score}%, verdict={comparison_result.verdict}")

            return comparison_result

        except Exception as e:
            logger.error(f"Template comparison failed: {e}")
            return TemplateComparisonResult(
                total_deviations=0,
                critical_count=0,
                high_count=0,
                medium_count=0,
                low_count=0,
                deviations=[],
                missing_sections=[],
                extra_sections=[],
                compliance_score=0,
                summary=f"Ошибка сравнения: {str(e)}",
                verdict="major_changes"
            )
