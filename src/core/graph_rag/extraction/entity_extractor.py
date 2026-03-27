# -*- coding: utf-8 -*-
"""
Entity Extractor

Извлечение нормализованных сущностей из текста узлов:
- NormReference (ст. 330 ГК РФ) → GraphEntity(entity_type='norm_ref')
- MonetaryValue (75 000 000 рублей) → GraphEntity(entity_type='monetary')
- DateReference (01.09.2026) → GraphEntity(entity_type='date_ref')
- ClauseType (неустойка, поставка) → GraphEntity(entity_type='clause_type')
- ContractType (поставка, аренда) → GraphEntity(entity_type='contract_type')

Сущности сохраняются в таблицу graph_entities и позволяют строить
связи через нормализованные объекты, а не свободный текст.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional, Dict


# ──────────────────────────────────────────────
# Data classes
# ──────────────────────────────────────────────

@dataclass
class ExtractedEntity:
    """Извлечённая сущность из текста."""
    entity_type: str        # norm_ref, monetary, date_ref, clause_type, contract_type
    entity_value: str       # Нормализованное значение
    raw_text: str           # Оригинальный текст
    start: int              # Позиция начала
    end: int                # Позиция конца

    # NormReference
    norm_code: Optional[str] = None
    norm_article: Optional[str] = None
    norm_part: Optional[str] = None

    # MonetaryValue
    amount: Optional[float] = None
    currency: Optional[str] = None

    # DateReference
    date_value: Optional[datetime] = None
    date_type: Optional[str] = None     # deadline, start, end, signing, effective

    # Confidence
    extracted_by: str = "parser"
    confidence: float = 1.0


# ──────────────────────────────────────────────
# Regex patterns
# ──────────────────────────────────────────────

# Денежные суммы: "75 000 000 рублей", "15 000 руб.", "$1,000,000", "100 000 EUR"
RE_MONEY_RUB = re.compile(
    r'(\d[\d\s]*(?:[,\.]\d+)?)\s*'
    r'(?:рубл\w+|руб\.?|₽)',
    re.IGNORECASE
)

RE_MONEY_USD = re.compile(
    r'(?:\$\s*(\d[\d\s,]*(?:\.\d+)?)|'
    r'(\d[\d\s]*(?:[,\.]\d+)?)\s*(?:доллар\w+|USD|\$))',
    re.IGNORECASE
)

RE_MONEY_EUR = re.compile(
    r'(?:€\s*(\d[\d\s,]*(?:\.\d+)?)|'
    r'(\d[\d\s]*(?:[,\.]\d+)?)\s*(?:евро|EUR|€))',
    re.IGNORECASE
)

# Даты: "01.09.2026", "1 сентября 2026", "2026-09-01"
RE_DATE_DMY = re.compile(r'(\d{1,2})\.(\d{1,2})\.(\d{4})')

RE_DATE_ISO = re.compile(r'(\d{4})-(\d{2})-(\d{2})')

MONTHS_RU = {
    'января': 1, 'февраля': 2, 'марта': 3, 'апреля': 4,
    'мая': 5, 'июня': 6, 'июля': 7, 'августа': 8,
    'сентября': 9, 'октября': 10, 'ноября': 11, 'декабря': 12,
}
_months_alt = '|'.join(MONTHS_RU.keys())

RE_DATE_RU = re.compile(
    rf'(\d{{1,2}})\s+({_months_alt})\s+(\d{{4}})',
    re.IGNORECASE
)

# Контекст даты: "до 01.09.2026", "с 01.09.2026 по 30.11.2026", "не позднее"
RE_DATE_CONTEXT = re.compile(
    r'(?:до|не\s+позднее|по)\s+\d{1,2}\.\d{1,2}\.\d{4}',
    re.IGNORECASE
)

RE_DATE_FROM = re.compile(r'с\s+(\d{1,2}\.\d{1,2}\.\d{4})', re.IGNORECASE)
RE_DATE_TO = re.compile(r'(?:до|по)\s+(\d{1,2}\.\d{1,2}\.\d{4})', re.IGNORECASE)

# Проценты: "0,1%", "10%", "ставка рефинансирования"
RE_PERCENT = re.compile(r'(\d+(?:[,\.]\d+)?)\s*%')

# Типы клаузул (ключевые слова)
CLAUSE_TYPE_KEYWORDS = {
    'penalty': ['неустойк', 'штраф', 'пени', 'пеня'],
    'warranty': ['гарант', 'заверен'],
    'indemnity': ['возмещ', 'компенсац', 'убытк'],
    'force_majeure': ['форс-мажор', 'непреодолим'],
    'confidentiality': ['конфиденциальн', 'тайн'],
    'limitation_of_liability': ['ограничен.*ответственност'],
    'insurance': ['страхован'],
    'intellectual_property': ['интеллектуальн.*собственност', 'авторск'],
    'arbitration': ['арбитраж', 'третейск'],
    'termination': ['расторж', 'прекращ'],
}

# Типы договоров
CONTRACT_TYPE_KEYWORDS = {
    'supply': ['поставк', 'поставщик'],
    'service': ['оказан.*услуг', 'исполнител'],
    'lease': ['аренд', 'арендодател'],
    'storage': ['хранен', 'хранител'],
    'processing': ['переработк'],
    'purchase': ['купл.*продаж', 'продавец.*покупатель'],
    'loan': ['займ', 'кредит', 'заёмщик'],
    'agency': ['агентск', 'принципал'],
    'construction': ['подряд', 'строительств', 'генподряд'],
}


def _parse_amount(text: str, currency: str = 'RUB') -> Optional[float]:
    """Парсинг суммы из текста: '75 000 000' → 75000000.0"""
    cleaned = text.replace(' ', '')
    # Для USD/EUR запятая — тысячный разделитель, точка — десятичная
    if currency in ('USD', 'EUR'):
        cleaned = cleaned.replace(',', '')
    else:
        # Для рублей: запятая может быть десятичным разделителем
        cleaned = cleaned.replace(',', '.')
    try:
        return float(cleaned)
    except ValueError:
        return None


def _parse_date_dmy(day: str, month: str, year: str) -> Optional[datetime]:
    """Парсинг даты DD.MM.YYYY."""
    try:
        return datetime(int(year), int(month), int(day))
    except ValueError:
        return None


# ──────────────────────────────────────────────
# EntityExtractor
# ──────────────────────────────────────────────

class EntityExtractor:
    """
    Извлечение нормализованных сущностей из текста.

    Использование:
        extractor = EntityExtractor()
        entities = extractor.extract("Сумма 75 000 000 рублей, срок до 01.09.2026")
        # → [monetary(75000000, RUB), date_ref(2026-09-01, deadline)]
    """

    def extract(self, text: str) -> List[ExtractedEntity]:
        """Извлечь все сущности из текста."""
        entities: List[ExtractedEntity] = []

        entities.extend(self._extract_monetary(text))
        entities.extend(self._extract_dates(text))
        entities.extend(self._extract_clause_types(text))
        entities.extend(self._extract_contract_types(text))

        return entities

    # ──────────────────────────────────────────
    # Monetary
    # ──────────────────────────────────────────

    def _extract_monetary(self, text: str) -> List[ExtractedEntity]:
        """Денежные суммы."""
        entities = []

        # Рубли
        for m in RE_MONEY_RUB.finditer(text):
            amount = _parse_amount(m.group(1))
            if amount and amount > 0:
                entities.append(ExtractedEntity(
                    entity_type='monetary',
                    entity_value=f"{amount:.2f} RUB",
                    raw_text=m.group(0),
                    start=m.start(), end=m.end(),
                    amount=amount, currency='RUB',
                ))

        # Доллары
        for m in RE_MONEY_USD.finditer(text):
            amt_str = m.group(1) or m.group(2)
            if amt_str:
                amount = _parse_amount(amt_str, 'USD')
                if amount and amount > 0:
                    entities.append(ExtractedEntity(
                        entity_type='monetary',
                        entity_value=f"{amount:.2f} USD",
                        raw_text=m.group(0),
                        start=m.start(), end=m.end(),
                        amount=amount, currency='USD',
                    ))

        # Евро
        for m in RE_MONEY_EUR.finditer(text):
            amt_str = m.group(1) or m.group(2)
            if amt_str:
                amount = _parse_amount(amt_str, 'EUR')
                if amount and amount > 0:
                    entities.append(ExtractedEntity(
                        entity_type='monetary',
                        entity_value=f"{amount:.2f} EUR",
                        raw_text=m.group(0),
                        start=m.start(), end=m.end(),
                        amount=amount, currency='EUR',
                    ))

        return entities

    # ──────────────────────────────────────────
    # Dates
    # ──────────────────────────────────────────

    def _extract_dates(self, text: str) -> List[ExtractedEntity]:
        """Даты с определением контекста (начало, конец, дедлайн)."""
        entities = []

        # DD.MM.YYYY
        for m in RE_DATE_DMY.finditer(text):
            dt = _parse_date_dmy(m.group(1), m.group(2), m.group(3))
            if dt:
                date_type = self._determine_date_type(text, m.start())
                entities.append(ExtractedEntity(
                    entity_type='date_ref',
                    entity_value=dt.strftime('%Y-%m-%d'),
                    raw_text=m.group(0),
                    start=m.start(), end=m.end(),
                    date_value=dt, date_type=date_type,
                ))

        # "1 сентября 2026"
        for m in RE_DATE_RU.finditer(text):
            month_num = MONTHS_RU.get(m.group(2).lower())
            if month_num:
                dt = _parse_date_dmy(m.group(1), str(month_num), m.group(3))
                if dt:
                    date_type = self._determine_date_type(text, m.start())
                    entities.append(ExtractedEntity(
                        entity_type='date_ref',
                        entity_value=dt.strftime('%Y-%m-%d'),
                        raw_text=m.group(0),
                        start=m.start(), end=m.end(),
                        date_value=dt, date_type=date_type,
                    ))

        # YYYY-MM-DD (ISO)
        for m in RE_DATE_ISO.finditer(text):
            dt = _parse_date_dmy(m.group(3), m.group(2), m.group(1))
            if dt:
                entities.append(ExtractedEntity(
                    entity_type='date_ref',
                    entity_value=dt.strftime('%Y-%m-%d'),
                    raw_text=m.group(0),
                    start=m.start(), end=m.end(),
                    date_value=dt, date_type='general',
                ))

        return entities

    @staticmethod
    def _determine_date_type(text: str, pos: int) -> str:
        """Определить тип даты по контексту (30 символов до даты)."""
        context = text[max(0, pos - 30):pos].lower()
        if any(w in context for w in ['до ', 'не позднее', 'по ']):
            return 'deadline'
        if any(w in context for w in ['с ', 'начиная с', 'от ']):
            return 'start'
        if any(w in context for w in ['подписан', 'заключен']):
            return 'signing'
        if any(w in context for w in ['вступа', 'действ']):
            return 'effective'
        return 'general'

    # ──────────────────────────────────────────
    # Clause types
    # ──────────────────────────────────────────

    def _extract_clause_types(self, text: str) -> List[ExtractedEntity]:
        """Типы клаузул (неустойка, гарантия и т.д.)."""
        entities = []
        text_lower = text.lower()

        for clause_type, keywords in CLAUSE_TYPE_KEYWORDS.items():
            for kw in keywords:
                pattern = re.compile(kw, re.IGNORECASE)
                m = pattern.search(text)
                if m:
                    entities.append(ExtractedEntity(
                        entity_type='clause_type',
                        entity_value=clause_type,
                        raw_text=m.group(0),
                        start=m.start(), end=m.end(),
                        confidence=0.9,
                    ))
                    break  # Один тип на один набор keywords

        return entities

    # ──────────────────────────────────────────
    # Contract types
    # ──────────────────────────────────────────

    def _extract_contract_types(self, text: str) -> List[ExtractedEntity]:
        """Типы договоров (поставка, аренда и т.д.)."""
        entities = []

        for contract_type, keywords in CONTRACT_TYPE_KEYWORDS.items():
            for kw in keywords:
                pattern = re.compile(kw, re.IGNORECASE)
                m = pattern.search(text)
                if m:
                    entities.append(ExtractedEntity(
                        entity_type='contract_type',
                        entity_value=contract_type,
                        raw_text=m.group(0),
                        start=m.start(), end=m.end(),
                        confidence=0.85,
                    ))
                    break

        return entities
