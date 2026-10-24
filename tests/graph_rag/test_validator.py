# -*- coding: utf-8 -*-
"""E5: маркер недоступности К+ отбраковывает заглушку, но не большой кодекс."""
from src.core.graph_rag.importers.validator import STUB_MAX_CHARS, validate_parse_result
from src.core.graph_rag.parser import NPAGraphParser

STUB = """Федеральный закон от 04.11.2006 N 186-ФЗ

Документ доступен [по расписанию](/about/) в некоммерческой версии КонсультантПлюс.
""" + "Тексты документов всегда доступны в коммерческой версии. " * 30

ARTICLE = """Статья {n}. Порядок перевозок
1. Перевозки на морской линии осуществляются на регулярной основе по расписанию.
2. Полный текст документа вы можете просмотреть в коммерческой версии КонсультантПлюс.
"""


def _check(text, title):
    parsed = NPAGraphParser().parse_text(text, title=title)
    return validate_parse_result(parsed, text, file_label="t.md")


def test_stub_is_rejected():
    assert len(STUB) < STUB_MAX_CHARS
    rep = _check(STUB, "Федеральный закон N 186-ФЗ")
    assert not rep.ok
    assert "E5" in {i.code for i in rep.errors}


def test_large_code_with_marker_is_loaded_with_warning():
    text = "КОДЕКС ТОРГОВОГО МОРЕПЛАВАНИЯ РОССИЙСКОЙ ФЕДЕРАЦИИ\n\n" + "\n".join(
        ARTICLE.format(n=n) for n in range(1, 200))
    assert len(text) >= STUB_MAX_CHARS
    rep = _check(text, "Кодекс торгового мореплавания РФ")
    assert rep.ok, rep.summary()
    assert "W3" in {i.code for i in rep.warnings}
