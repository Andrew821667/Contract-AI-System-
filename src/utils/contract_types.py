# -*- coding: utf-8 -*-
"""
Справочник типов договоров и их переводов
"""
from __future__ import annotations

import re
from typing import Any, Dict, Iterable, List, Optional

# Словарь типов договоров (все поименованные в ГК РФ, Часть 2)
CONTRACT_TYPES = {
    # Купля-продажа (гл. 30)
    "purchase": "Договор купли-продажи",
    "retail_purchase": "Договор розничной купли-продажи",
    "supply": "Договор поставки",
    "supply_government": "Договор поставки для государственных нужд",
    "contracting": "Договор контрактации",
    "energy_supply": "Договор энергоснабжения",
    "real_estate_sale": "Договор купли-продажи недвижимости",
    "enterprise_sale": "Договор купли-продажи предприятия",
    # Мена (гл. 31)
    "exchange": "Договор мены",
    # Дарение (гл. 32)
    "gift": "Договор дарения",
    # Рента (гл. 33)
    "rent": "Договор ренты",
    "life_annuity": "Договор пожизненного содержания с иждивением",
    # Аренда (гл. 34)
    "lease": "Договор аренды",
    "rental": "Договор проката",
    "vehicle_lease": "Договор аренды транспортного средства",
    "building_lease": "Договор аренды зданий и сооружений",
    "enterprise_lease": "Договор аренды предприятия",
    "leasing": "Договор финансовой аренды (лизинг)",
    # Наём жилого помещения (гл. 35)
    "residential_lease": "Договор найма жилого помещения",
    # Безвозмездное пользование (гл. 36)
    "gratuitous_use": "Договор безвозмездного пользования (ссуда)",
    # Подряд (гл. 37)
    "contract_work": "Договор подряда",
    "household_work": "Договор бытового подряда",
    "construction_work": "Договор строительного подряда",
    "design_work": "Договор на выполнение проектных и изыскательских работ",
    "government_work": "Договор подряда для государственных нужд",
    # НИОКР (гл. 38)
    "research": "Договор на выполнение НИОКР",
    # Возмездное оказание услуг (гл. 39)
    "service": "Договор возмездного оказания услуг",
    # Перевозка (гл. 40)
    "transportation": "Договор перевозки",
    "freight": "Договор перевозки груза",
    "passenger_transport": "Договор перевозки пассажиров",
    # Транспортная экспедиция (гл. 41)
    "freight_forwarding": "Договор транспортной экспедиции",
    # Заём и кредит (гл. 42)
    "loan": "Договор займа",
    "credit": "Кредитный договор",
    # Финансирование под уступку (гл. 43)
    "factoring": "Договор финансирования под уступку денежного требования",
    # Банковский вклад (гл. 44)
    "bank_deposit": "Договор банковского вклада",
    # Банковский счёт (гл. 45)
    "bank_account": "Договор банковского счёта",
    # Хранение (гл. 47)
    "storage": "Договор хранения",
    "warehouse_storage": "Договор складского хранения",
    # Страхование (гл. 48)
    "insurance": "Договор страхования",
    # Поручение (гл. 49)
    "mandate": "Договор поручения",
    # Комиссия (гл. 51)
    "commission": "Договор комиссии",
    # Агентирование (гл. 52)
    "agency": "Агентский договор",
    # Доверительное управление (гл. 53)
    "trust_management": "Договор доверительного управления имуществом",
    # Коммерческая концессия / франчайзинг (гл. 54)
    "franchise": "Договор коммерческой концессии (франчайзинг)",
    # Простое товарищество (гл. 55)
    "partnership": "Договор простого товарищества",
    # Прочие распространённые типы
    "employment": "Трудовой договор",
    "licensing": "Лицензионный договор",
    "confidentiality": "Соглашение о конфиденциальности (NDA)",
    "distribution": "Дистрибьюторский договор",
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
    "purchase": ["договор купли-продажи", "купли-продажи", "купли продажи", "продавец и покупатель"],
    "retail_purchase": ["розничной купли-продажи", "розничная купля-продажа", "чек", "кассовый"],
    "supply": ["договор поставки", "поставка", "поставщик"],
    "supply_government": ["поставки для государственных нужд", "государственный контракт на поставку"],
    "contracting": ["договор контрактации", "контрактации", "сельскохозяйственн"],
    "energy_supply": ["энергоснабжени", "электроэнерги", "теплоснабжени", "газоснабжени"],
    "real_estate_sale": ["купли-продажи недвижимости", "купли-продажи квартиры", "купли-продажи земельного"],
    "enterprise_sale": ["купли-продажи предприятия"],
    "exchange": ["договор мены", "мены", "обмен имуществ"],
    "gift": ["договор дарения", "дарения", "даритель", "одаряемый"],
    "rent": ["договор ренты", "ренты", "рентный", "плательщик ренты", "получатель ренты"],
    "life_annuity": ["пожизненного содержания с иждивением", "пожизненное содержание"],
    "lease": ["договор аренды", "аренды", "арендодатель", "арендатор"],
    "rental": ["договор проката", "проката"],
    "vehicle_lease": ["аренды транспортного средства", "аренды автомобиля"],
    "building_lease": ["аренды здания", "аренды сооружения", "аренды помещения", "аренды нежилого"],
    "enterprise_lease": ["аренды предприятия"],
    "leasing": ["лизинг", "финансовой аренды", "лизингодатель", "лизингополучатель"],
    "residential_lease": ["найма жилого помещения", "найма квартиры", "наниматель", "наймодатель"],
    "gratuitous_use": ["безвозмездного пользования", "ссуды", "ссудодатель", "ссудополучатель"],
    "contract_work": ["договор подряда", "подряда", "подрядчик"],
    "household_work": ["бытового подряда"],
    "construction_work": ["строительного подряда", "строительный подряд", "генподрядчик", "субподрядчик"],
    "design_work": ["проектных и изыскательских", "проектных работ", "изыскательских работ"],
    "government_work": ["подряда для государственных нужд"],
    "research": ["ниокр", "научно-исследовательск", "опытно-конструкторск", "технологических работ"],
    "service": ["договор оказания услуг", "оказания услуг", "возмездного оказания услуг"],
    "transportation": ["договор перевозки", "перевозки", "перевозчик"],
    "freight": ["перевозки груза", "грузоотправитель", "грузополучатель"],
    "passenger_transport": ["перевозки пассажир", "пассажирск"],
    "freight_forwarding": ["транспортной экспедиции", "экспедитор", "экспедиторск"],
    "loan": ["договор займа", "займа", "заемщик", "заёмщик", "займодавец"],
    "credit": ["кредитный договор", "кредитор", "кредитного"],
    "factoring": ["финансирования под уступку", "факторинг", "фактор"],
    "bank_deposit": ["банковского вклада", "вкладчик", "депозит"],
    "bank_account": ["банковского счёта", "банковского счета", "расчётного счёта", "расчетного счета"],
    "storage": ["договор хранения", "хранения", "хранитель", "поклажедатель"],
    "warehouse_storage": ["складского хранения", "склад", "складское свидетельство"],
    "insurance": ["договор страхования", "страхования", "страховщик", "страхователь", "страховой полис"],
    "mandate": ["договор поручения", "поручения", "доверитель", "поверенный"],
    "commission": ["договор комиссии", "комиссионер", "комитент"],
    "agency": ["агентский договор", "агентского договора", "агент", "принципал"],
    "trust_management": ["доверительного управления", "управляющий", "учредитель управления", "выгодоприобретатель"],
    "franchise": ["коммерческой концессии", "франчайзинг", "правообладатель", "пользователь концессии"],
    "partnership": ["простого товарищества", "совместной деятельности", "товарищ"],
    "employment": ["трудовой договор", "трудового договора", "работодатель", "работник"],
    "licensing": ["лицензионный договор", "лицензии", "лицензиар", "лицензиат"],
    "confidentiality": ["соглашение о конфиденциальности", "неразглашении", "nda"],
    "distribution": ["дистрибьюторский договор", "дистрибьютор"],
    "warranty": ["договор поручительства", "поручительства", "поручитель"],
    "pledge": ["договор залога", "залога", "залогодатель", "залогодержатель"],
}

# Категории договоров
CONTRACT_CATEGORIES = {
    "Купля-продажа": ["purchase", "retail_purchase", "supply", "supply_government", "contracting", "energy_supply", "real_estate_sale", "enterprise_sale"],
    "Обмен и дарение": ["exchange", "gift"],
    "Рента": ["rent", "life_annuity"],
    "Аренда": ["lease", "rental", "vehicle_lease", "building_lease", "enterprise_lease", "leasing", "residential_lease", "gratuitous_use"],
    "Подряд": ["contract_work", "household_work", "construction_work", "design_work", "government_work", "research"],
    "Услуги": ["service"],
    "Перевозка и экспедиция": ["transportation", "freight", "passenger_transport", "freight_forwarding"],
    "Финансовые": ["loan", "credit", "factoring", "bank_deposit", "bank_account", "insurance"],
    "Хранение": ["storage", "warehouse_storage"],
    "Посредничество": ["mandate", "commission", "agency"],
    "Управление и концессия": ["trust_management", "franchise"],
    "Корпоративные": ["partnership"],
    "Трудовые": ["employment"],
    "Интеллектуальная собственность": ["licensing", "confidentiality", "distribution"],
    "Обеспечение": ["warranty", "pledge"],
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
