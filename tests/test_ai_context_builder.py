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


# ── Маршрут AI-панели (POST /ai/sessions/{id}/messages) ───────────────────────
# Он вызывает LLM напрямую, минуя AICollaboratorService, — контекст документа
# должен собираться тем же сборщиком и попадать в системный промпт.
import asyncio
from types import SimpleNamespace

from src.api.v2 import ai_sessions
from src.core.ai_collaboration.session_service import render_document_context


def _context_with_contract() -> AIContext:
    return AIContext(
        document_id="doc-1",
        user_id="user-1",
        stage="review",
        document_metadata={"file_name": "Договор поставки 17-2026.docx"},
        document_text="ДОГОВОР ПОСТАВКИ № 17/2026. 5. Гарантийный срок на Товар составляет 14 дней.",
        findings=[
            {"kind": "risk", "severity": "high", "title": "Гарантийный срок 14 дней", "description": "Меньше разумного.", "section": "Пункт 5"},
        ],
    )


def test_ai_panel_prompt_puts_contract_before_legal_base():
    prompt = ai_sessions._compose_system_prompt(render_document_context(_context_with_contract()), "ст. 470 ГК РФ …")
    assert prompt.startswith(ai_sessions.AI_PANEL_RULES)
    assert "цитируй нужные пункты дословно" in prompt
    assert "# Текст договора" in prompt and "Гарантийный срок на Товар составляет 14 дней" in prompt
    assert "# Риски по результатам анализа (1)" in prompt
    assert prompt.index("# Текст договора") < prompt.index("# Правовая база и база знаний")


def test_ai_panel_prompt_without_document_or_rag_is_just_rules():
    assert ai_sessions._compose_system_prompt("", "") == ai_sessions.AI_PANEL_RULES


def test_ai_panel_document_context_comes_from_shared_builder(monkeypatch):
    calls = {}

    class FakeBuilder:
        def __init__(self, db):
            calls["db"] = db

        async def build(self, **kwargs):
            calls["kwargs"] = kwargs
            return _context_with_contract()

    monkeypatch.setattr(ai_sessions, "AIContextBuilderService", FakeBuilder)
    session = SimpleNamespace(document_id="doc-1", stage="review")
    doc_context, hint = asyncio.run(ai_sessions._build_document_context("db", session, "user-1"))
    assert calls["db"] == "db"
    assert calls["kwargs"]["document_id"] == "doc-1" and calls["kwargs"]["user_id"] == "user-1"
    assert calls["kwargs"]["stage"] == "review"
    assert calls["kwargs"]["include_workflow"] is False and calls["kwargs"]["include_prior_actions"] is False
    assert "Гарантийный срок на Товар составляет 14 дней" in doc_context
    assert "[high] Гарантийный срок 14 дней (раздел: Пункт 5)" in doc_context
    assert hint == "Документ: Договор поставки 17-2026.docx"


def test_ai_panel_general_session_has_no_document_context():
    session = SimpleNamespace(document_id=None, stage="general")
    assert asyncio.run(ai_sessions._build_document_context("db", session, "user-1")) == ("", "")


def test_ai_panel_survives_builder_failure(monkeypatch):
    class BrokenBuilder:
        def __init__(self, db):
            pass

        async def build(self, **kwargs):
            raise RuntimeError("файл договора недоступен")

    monkeypatch.setattr(ai_sessions, "AIContextBuilderService", BrokenBuilder)
    session = SimpleNamespace(document_id="doc-1", stage="review")
    assert asyncio.run(ai_sessions._build_document_context("db", session, "user-1")) == ("", "")


def test_collaborator_prompt_reuses_shared_document_block():
    context = _context_with_contract()
    prompt = AICollaboratorService._build_system_prompt(None, context)
    assert prompt.startswith(render_document_context(context))
    assert "# Формат действий" in prompt
