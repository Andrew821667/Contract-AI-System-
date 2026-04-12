# -*- coding: utf-8 -*-
"""
Analysis Filters — вспомогательные предикаты для фильтрации рисков и полей.

Выделены из contract_analyzer_agent.py для переиспользования и тестируемости.
"""
from typing import Any, Dict, Optional


def should_ignore_future_date_risk(text: str, analysis_date_iso: Optional[str]) -> bool:
    """
    Возвращает True, если риск связан с будущей датой относительно даты анализа.

    Типичный случай: LLM замечает, что срок договора уже истёк, хотя на момент
    анализа договор ещё действует (пользователь указал более раннюю дату анализа).
    """
    if not analysis_date_iso:
        return False

    text_lower = text.lower()
    date_expiry_markers = [
        'срок истёк', 'срок истек', 'договор истёк', 'договор истек',
        'срок действия истёк', 'срок действия истек',
        'истечение срока', 'просроченный',
        'expired', 'expiry passed', 'term expired',
    ]
    return any(marker in text_lower for marker in date_expiry_markers)


def should_ignore_required_field(item: Dict[str, Any]) -> bool:
    """
    Возвращает True, если незаполненное поле является техническим артефактом
    и не должно показываться пользователю.

    Технические артефакты: UUID-поля, метаданные парсера, служебные атрибуты XML.
    """
    technical_markers = [
        'uuid', 'parsed_at', 'metadata', 'file_name', 'docx',
        'автор', 'author', 'title', 'без названия',
    ]
    combined = ' '.join([
        str(item.get('title', '')),
        str(item.get('snippet', '')),
        str(item.get('section_name', '')),
        str(item.get('xpath_location', '')),
    ]).lower()

    return any(marker in combined for marker in technical_markers)


def should_ignore_signatory_authority_risk(text: str) -> bool:
    """
    Возвращает True, если риск касается полномочий подписанта при наличии
    стандартной формулировки о действии по уставу/доверенности.

    LLM иногда помечает как риск отсутствие явного указания полномочий,
    даже когда в договоре есть стандартная фраза «действует на основании Устава».
    """
    text_lower = text.lower()

    # Признаки, что риск о полномочиях подписанта
    authority_markers = [
        'полномочи', 'доверенност', 'устав', 'учредительн',
        'signatory', 'authority', 'authorized',
        'действует на основании', 'уполномочен',
    ]
    is_authority_risk = any(marker in text_lower for marker in authority_markers)
    if not is_authority_risk:
        return False

    # Если в тексте уже есть ссылка на документ-основание — игнорируем
    basis_markers = [
        'на основании устава', 'на основании доверенности',
        'действует на основании', 'уполномочен на основании',
        'based on charter', 'power of attorney',
    ]
    has_basis = any(marker in text_lower for marker in basis_markers)
    return has_basis
