# -*- coding: utf-8 -*-
"""
Справочник типов договоров и их переводов
"""
from __future__ import annotations

import re
from typing import Any, Dict, Iterable, List, Optional

# Словарь типов договоров
CONTRACT_TYPES = {
    "supply": "Договор поставки",
    "service": "Договор оказания услуг",
    "lease": "Договор аренды",
    "purchase": "Договор купли-продажи",
    "confidentiality": "Соглашение о конфиденциальности (NDA)",
    "employment": "Трудовой договор",
    "contract_work": "Договор подряда",
    "agency": "Агентский договор",
    "commission": "Договор комиссии",
    "loan": "Договор займа",
    "credit": "Кредитный договор",
    "insurance": "Договор страхования",
    "franchise": "Договор франчайзинга",
    "partnership": "Договор о совместной деятельности",
    "licensing": "Лицензионный договор",
    "distribution": "Дистрибьюторский договор",
    "transportation": "Договор перевозки",
    "storage": "Договор хранения",
    "warranty": "Договор поручительства",
    "pledge": "Договор залога",
}

# Обратный словарь (русское название -> английский код)
CONTRACT_TYPES_REVERSE = {v: k for k, v in CONTRACT_TYPES.items()}

_NORMALIZED_CONTRACT_NAMES = {
    re.sub(r"\s+", " ", name).strip().lower(): code
    for code, name in CONTRACT_TYPES.items()
}

UNKNOWN_CONTRACT_TYPES = {
    "",
    "unknown",
    "неизвестный",
    "не определен",
    "не определён",
    "автоопределение",
    "другое",
    "contract",
}

CONTRACT_TYPE_HINTS = {
    "supply": [
        "договор поставки",
        "поставка",
        "поставщик",
    ],
    "service": [
        "договор оказания услуг",
        "оказания услуг",
        "возмездного оказания услуг",
    ],
    "lease": [
        "договор аренды",
        "аренды",
        "арендодатель",
        "арендатор",
    ],
    "purchase": [
        "договор купли-продажи",
        "договор купли продажи",
        "купли-продажи",
        "купли продажи",
    ],
    "confidentiality": [
        "соглашение о конфиденциальности",
        "соглашение о неразглашении",
        "nda",
        "конфиденциальности",
        "неразглашении",
    ],
    "employment": [
        "трудовой договор",
        "трудового договора",
    ],
    "contract_work": [
        "договор подряда",
        "подряда",
        "подрядчик",
    ],
    "agency": [
        "агентский договор",
        "агентского договора",
    ],
    "commission": [
        "договор комиссии",
        "комиссионер",
        "комитент",
    ],
    "loan": [
        "договор займа",
        "займа",
        "заемщик",
        "заёмщик",
        "займодавец",
    ],
    "credit": [
        "кредитный договор",
        "кредитор",
    ],
    "insurance": [
        "договор страхования",
        "страхования",
        "страховщик",
        "страхователь",
    ],
    "franchise": [
        "договор франчайзинга",
        "договор коммерческой концессии",
        "франчайзинга",
    ],
    "partnership": [
        "договор о совместной деятельности",
        "договор простого товарищества",
        "совместной деятельности",
    ],
    "licensing": [
        "лицензионный договор",
        "лицензионного договора",
        "лицензии",
        "предоставления права использования",
    ],
    "distribution": [
        "дистрибьюторский договор",
        "дистрибьютор",
    ],
    "transportation": [
        "договор перевозки",
        "перевозки",
        "перевозчик",
    ],
    "storage": [
        "договор хранения",
        "хранения",
        "хранитель",
    ],
    "warranty": [
        "договор поручительства",
        "поручительства",
        "поручитель",
    ],
    "pledge": [
        "договор залога",
        "залога",
        "залогодатель",
        "залогодержатель",
    ],
}

# Категории договоров
CONTRACT_CATEGORIES = {
    "Торговые": ["supply", "purchase", "distribution", "commission"],
    "Услуги": ["service", "contract_work", "agency", "transportation", "storage"],
    "Недвижимость": ["lease", "pledge"],
    "Финансовые": ["loan", "credit", "warranty", "insurance"],
    "Интеллектуальная собственность": ["licensing", "franchise", "confidentiality"],
    "Трудовые": ["employment"],
    "Корпоративные": ["partnership"],
}


def get_contract_type_name(code: str) -> str:
    """Получить русское название типа договора"""
    return CONTRACT_TYPES.get(code, code)


def get_contract_type_code(name: str) -> str:
    """Получить код типа договора по русскому названию"""
    return CONTRACT_TYPES_REVERSE.get(name, name)


def get_contracts_by_category(category: str) -> list:
    """Получить список договоров по категории"""
    codes = CONTRACT_CATEGORIES.get(category, [])
    return [(code, CONTRACT_TYPES[code]) for code in codes if code in CONTRACT_TYPES]


def get_all_contract_types() -> list:
    """Получить все типы договоров в виде списка (код, название)"""
    return [(code, name) for code, name in CONTRACT_TYPES.items()]


def get_all_contract_names() -> list:
    """Получить все названия договоров на русском"""
    return list(CONTRACT_TYPES.values())


def get_all_categories() -> list:
    """Получить все категории договоров"""
    return list(CONTRACT_CATEGORIES.keys())


def is_meaningful_contract_type(value: Optional[str]) -> bool:
    """Проверить, что тип договора непустой и не служебный."""
    if value is None:
        return False
    normalized = re.sub(r"\s+", " ", str(value)).strip().lower()
    return normalized not in UNKNOWN_CONTRACT_TYPES


def canonical_contract_type_key(value: Optional[str]) -> Optional[str]:
    """Получить канонический ключ типа договора для дедупликации."""
    if not is_meaningful_contract_type(value):
        return None

    normalized = re.sub(r"\s+", " ", str(value)).strip()
    lowered = normalized.lower()

    if lowered in CONTRACT_TYPES:
        return lowered

    if lowered in _NORMALIZED_CONTRACT_NAMES:
        return _NORMALIZED_CONTRACT_NAMES[lowered]

    return lowered


def prettify_contract_type_name(value: Optional[str]) -> str:
    """Преобразовать произвольный тип договора в читаемое название."""
    if not is_meaningful_contract_type(value):
        return "Неизвестный тип договора"

    normalized = re.sub(r"\s+", " ", str(value)).strip()
    if normalized in CONTRACT_TYPES:
        return CONTRACT_TYPES[normalized]

    code = _NORMALIZED_CONTRACT_NAMES.get(normalized.lower())
    if code:
        return CONTRACT_TYPES[code]

    cleaned = normalized.replace("_", " ").replace("-", " ")
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" \t\r\n-_:;,.")
    if not cleaned:
        return normalized
    return cleaned[0].upper() + cleaned[1:]


def infer_contract_type_from_xml(
    xml_content: str,
    fallback: Optional[str] = None,
    file_name: Optional[str] = None,
) -> str:
    """
    Определить тип договора по XML и, при необходимости, по имени файла.

    Возвращает:
    - builtin code (`supply`, `service`, ...)
    - или человекочитаемое название для нового типа (`Соглашение об урегулировании`)
    - или `fallback/unknown`, если определить не удалось
    """
    if is_meaningful_contract_type(fallback):
        canonical = canonical_contract_type_key(fallback)
        if canonical in CONTRACT_TYPES:
            return canonical
        return prettify_contract_type_name(fallback)

    candidates: List[str] = []

    try:
        from src.utils.xml_security import parse_xml_safely

        root = parse_xml_safely(xml_content)
        metadata_title = root.findtext(".//metadata/title") or ""
        metadata_file_name = root.findtext(".//metadata/file_name") or ""
        clause_titles = [text.strip() for text in root.xpath(".//clause/title/text()")[:5] if text and text.strip()]
        paragraphs = [text.strip() for text in root.xpath(".//clause/content/paragraph/text()")[:10] if text and text.strip()]
        full_text = " ".join(text.strip() for text in root.itertext() if text and text.strip())

        candidates.extend([metadata_title, metadata_file_name, *clause_titles, *paragraphs])
        if full_text:
            first_lines = [line.strip() for line in full_text.splitlines() if line.strip()][:10]
            candidates.extend(first_lines)
    except Exception:
        plain_text = re.sub(r"<[^>]+>", " ", xml_content)
        plain_text = re.sub(r"\s+", " ", plain_text).strip()
        if plain_text:
            candidates.extend([plain_text[:600]])

    if file_name:
        normalized_file_name = re.sub(r"\.[A-Za-z0-9]+$", "", file_name)
        normalized_file_name = normalized_file_name.replace("_", " ").replace("-", " ")
        candidates.append(normalized_file_name)

    builtin_code = _match_builtin_contract_type(candidates)
    if builtin_code:
        return builtin_code

    title = _extract_custom_contract_title(candidates)
    if title:
        return title

    return fallback or "unknown"


def get_generation_contract_types(
    db_session,
    *,
    user_id: Optional[str] = None,
    include_all: bool = False,
) -> List[Dict[str, Any]]:
    """Получить список типов договоров для генерации: статические + найденные в анализе."""
    from src.models.database import Contract, Template

    template_types = {
        row[0]
        for row in db_session.query(Template.contract_type)
        .filter(Template.active == True)  # noqa: E712
        .distinct()
        .all()
        if row[0]
    }

    result: List[Dict[str, Any]] = []
    seen_keys = set()

    for code, name in CONTRACT_TYPES.items():
        seen_keys.add(code)
        result.append(
            {
                "code": code,
                "name": name,
                "source": "builtin",
                "has_template": code in template_types,
            }
        )

    query = db_session.query(Contract.contract_type, Contract.file_name).filter(
        Contract.status == "completed",
    )
    if user_id and not include_all:
        query = query.filter(Contract.assigned_to == user_id)

    inferred_dynamic_values = set()
    for row in query.distinct().all():
        inferred_value = infer_contract_type_from_xml("", fallback=row[0], file_name=row[1])
        if is_meaningful_contract_type(inferred_value):
            inferred_dynamic_values.add(inferred_value)

    dynamic_values = sorted(
        inferred_dynamic_values,
        key=lambda value: prettify_contract_type_name(value).lower(),
    )

    for raw_value in dynamic_values:
        canonical = canonical_contract_type_key(raw_value)
        if canonical in seen_keys:
            continue
        seen_keys.add(canonical)
        result.append(
            {
                "code": raw_value,
                "name": prettify_contract_type_name(raw_value),
                "source": "analysis",
                "has_template": raw_value in template_types or canonical in template_types,
            }
        )

    return result


def _match_builtin_contract_type(candidates: Iterable[str]) -> Optional[str]:
    """Найти builtin-тип договора по заголовку или первым строкам."""
    search_space = " \n".join(
        re.sub(r"\s+", " ", candidate).strip().lower()
        for candidate in candidates
        if candidate and candidate.strip()
    )
    if not search_space:
        return None

    for code, hints in CONTRACT_TYPE_HINTS.items():
        for hint in hints:
            if hint in search_space:
                return code

    return None


def _extract_custom_contract_title(candidates: Iterable[str]) -> Optional[str]:
    """Извлечь осмысленное название нетипового договора из начала документа."""
    title_pattern = re.compile(
        r"(?i)\b(договор|соглашение|контракт)\b[^\n]{0,90}"
    )

    for candidate in candidates:
        if not candidate:
            continue
        for raw_line in str(candidate).splitlines():
            line = re.sub(r"\s+", " ", raw_line).strip(" \t\r\n-_:;,.")
            if not line or len(line) < 8:
                continue
            match = title_pattern.search(line)
            if not match:
                continue
            title = match.group(0)
            title = re.sub(r"\s+№\s*[\w\-./]+", "", title, flags=re.IGNORECASE)
            title = re.sub(
                r"\s+от\s+\d{1,2}[./-]\d{1,2}[./-]\d{2,4}.*$",
                "",
                title,
                flags=re.IGNORECASE,
            )
            title = re.sub(r"\s+[0-9a-f]{8,}$", "", title, flags=re.IGNORECASE)
            title = re.sub(r"\s+v?\d+$", "", title, flags=re.IGNORECASE)
            title = re.sub(r"\s+", " ", title).strip(" \t\r\n-_:;,.")
            if len(title) >= 8:
                return title[0].upper() + title[1:]

    return None
