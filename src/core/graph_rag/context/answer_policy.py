# -*- coding: utf-8 -*-
"""
Answer Policy

Политика формирования ответа на основе Graph-RAG контекста.
Разделяет факты (точно из документа) и аналитику (выводы LLM).

КЛЮЧЕВОЙ ПРИНЦИП: LLM-выводы ≠ verified facts.
  - Факт: «Неустойка составляет 0.1% за каждый день просрочки» (дословно из п. 7.3)
  - Аналитика: «Размер неустойки ниже среднерыночного» (вывод LLM)

Пользователь ВСЕГДА должен видеть:
  1. Из какого документа/пункта взят факт
  2. Какие утверждения — факты, а какие — аналитика
  3. Уровень уверенности в ответе
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Dict

from .context_builder import AssembledContext


class AnswerConfidence(str, Enum):
    """Уровень уверенности в ответе."""
    HIGH = "high"           # Прямой ответ найден в документе
    MEDIUM = "medium"       # Ответ собран из нескольких мест / требует интерпретации
    LOW = "low"             # Нет прямого ответа, только косвенные данные
    NO_DATA = "no_data"     # Данных для ответа нет


@dataclass
class AnswerPolicy:
    """
    Политика ответа: что можно утверждать, а что нет.

    Использование:
        policy = AnswerPolicy.from_context(assembled_context, query)
        system_prompt = policy.to_system_prompt()
    """
    confidence: AnswerConfidence = AnswerConfidence.MEDIUM
    has_direct_answer: bool = False
    fact_sources: List[Dict] = field(default_factory=list)  # [{node_id, number, document}]
    disclaimers: List[str] = field(default_factory=list)
    instruction: str = ""

    @classmethod
    def from_context(
        cls,
        context: AssembledContext,
        query: str = "",
    ) -> AnswerPolicy:
        """Определить политику ответа на основе контекста."""
        policy = cls()

        if not context.blocks:
            policy.confidence = AnswerConfidence.NO_DATA
            policy.instruction = (
                "В предоставленных документах не найдено информации по запросу. "
                "Сообщи пользователю, что данных для ответа нет. "
                "НЕ придумывай информацию."
            )
            policy.disclaimers.append(
                "Информация по данному запросу не найдена в загруженных документах."
            )
            return policy

        # Анализируем блоки
        primary_blocks = [b for b in context.blocks if b.role == "primary"]
        reference_blocks = [b for b in context.blocks if b.role == "reference"]
        entity_blocks = [b for b in context.blocks if b.role == "entity"]

        # Заполняем источники
        for source in context.sources:
            policy.fact_sources.append(source)

        # Определяем confidence
        if primary_blocks:
            policy.has_direct_answer = True
            if len(primary_blocks) >= 1 and not context.truncated:
                policy.confidence = AnswerConfidence.HIGH
            else:
                policy.confidence = AnswerConfidence.MEDIUM
        elif reference_blocks or entity_blocks:
            policy.confidence = AnswerConfidence.MEDIUM
        else:
            policy.confidence = AnswerConfidence.LOW

        # Формируем instruction
        policy.instruction = cls._build_instruction(policy)

        # Disclaimers
        if context.truncated:
            policy.disclaimers.append(
                "Контекст был сокращён из-за ограничения размера. "
                "Возможно, не все релевантные фрагменты включены."
            )

        if policy.confidence == AnswerConfidence.LOW:
            policy.disclaimers.append(
                "Прямой ответ в документах не найден. "
                "Представленная информация носит справочный характер."
            )

        return policy

    @staticmethod
    def _build_instruction(policy: AnswerPolicy) -> str:
        """Сформировать инструкцию для LLM."""
        parts = []

        parts.append(
            "Ты — юридический ассистент. Отвечай на основе предоставленного контекста."
        )

        if policy.confidence == AnswerConfidence.HIGH:
            parts.append(
                "Контекст содержит прямой ответ. Цитируй точно из документа. "
                "Указывай номер пункта/статьи и название документа."
            )
        elif policy.confidence == AnswerConfidence.MEDIUM:
            parts.append(
                "Ответ требует объединения информации из нескольких мест. "
                "Чётко разделяй: что ПРЯМО сказано в документе (факт) "
                "и что является твоим выводом (аналитика). "
                "Каждый факт сопровождай ссылкой на пункт."
            )
        elif policy.confidence == AnswerConfidence.LOW:
            parts.append(
                "Прямого ответа в документах нет. Можешь дать общую справку, "
                "но ОБЯЗАТЕЛЬНО предупреди, что это не из документа. "
                "НЕ выдумывай факты. НЕ цитируй несуществующие пункты."
            )

        parts.append(
            "ПРАВИЛА:\n"
            "- Факты из документа оформляй со ссылкой: (п. X.X Документа)\n"
            "- Аналитические выводы помечай: «По нашей оценке...», «Обратите внимание...»\n"
            "- Если данных недостаточно — прямо скажи об этом\n"
            "- НЕ придумывай номера пунктов или статей\n"
            "- НЕ ссылайся на документы, которых нет в контексте"
        )

        return "\n\n".join(parts)

    def to_system_prompt(self) -> str:
        """Сформировать system prompt для LLM."""
        prompt_parts = [self.instruction]

        if self.disclaimers:
            prompt_parts.append(
                "ДИСКЛЕЙМЕРЫ (включи в ответ если релевантно):\n" +
                "\n".join(f"- {d}" for d in self.disclaimers)
            )

        if self.fact_sources:
            sources_text = []
            for s in self.fact_sources:
                doc = s.get('document', 'Документ')
                number = s.get('number', '')
                ntype = s.get('node_type', '')
                score = s.get('score', 0)
                sources_text.append(
                    f"- {doc}: {ntype} {number} (релевантность: {score:.0%})"
                )
            prompt_parts.append(
                "ИСТОЧНИКИ:\n" + "\n".join(sources_text)
            )

        return "\n\n---\n\n".join(prompt_parts)

    def to_metadata(self) -> Dict:
        """Метаданные для API response."""
        return {
            "confidence": self.confidence.value,
            "has_direct_answer": self.has_direct_answer,
            "sources_count": len(self.fact_sources),
            "disclaimers": self.disclaimers,
            "truncated": any("сокращён" in d for d in self.disclaimers),
        }
