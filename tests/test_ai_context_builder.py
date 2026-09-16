# -*- coding: utf-8 -*-
"""Контекст AI-помощника: текст договора и реальные риски, а не служебные счётчики."""
from src.core.ai_collaboration.context_builder import _plain_text, DOCUMENT_TEXT_LIMIT
from src.core.ai_collaboration.session_service import AICollaboratorService
from src.core.base import AIContext


def test_xml_from_parser_becomes_readable_text():
    xml = "<contract><clause id='1'><title>1. Предмет</title><paragraph>Поставщик &laquo;Ромашка&raquo; обязуется</paragraph></clause><clause><paragraph>2. Цена</paragraph></clause></contract>"
    text = _plain_text(xml)
    assert "<" not in text
    assert "1. Предмет" in text and "«Ромашка»" in text
    assert text.index("1. Предмет") < text.index("2. Цена")
    assert "\n" in text


def test_plain_text_passes_through():
    assert _plain_text("  Договор   поставки  ") == "Договор поставки"


def test_system_prompt_carries_contract_text_and_findings():
    context = AIContext(
        document_id="doc-1",
        user_id="user-1",
        stage="analysis",
        document_text="ДОГОВОР ПОСТАВКИ № 17/2026. Поставщик вправе изменить цену в одностороннем порядке.",
        findings=[
            {"kind": "risk", "severity": "critical", "title": "Одностороннее изменение цены", "description": "Пункт 2 позволяет поставщику менять цену после предоплаты.", "section": "Пункт 2"},
            {"kind": "recommendation", "severity": "high", "title": "Зафиксировать цену", "description": "Исключить право одностороннего изменения."},
        ],
    )
    prompt = AICollaboratorService._build_system_prompt(None, context)  # метод не использует self
    assert "# Текст договора" in prompt
    assert "изменить цену в одностороннем порядке" in prompt
    assert "# Риски по результатам анализа (1)" in prompt
    assert "[critical] Одностороннее изменение цены (раздел: Пункт 2): Пункт 2 позволяет" in prompt
    assert "# Рекомендации (1)" in prompt
    assert "[high] Зафиксировать цену: Исключить" in prompt
    assert prompt.index("# Риски") < prompt.index("# Текст договора")


def test_document_text_limit_is_reasonable_for_a_full_contract():
    assert 15_000 <= DOCUMENT_TEXT_LIMIT <= 60_000
