# -*- coding: utf-8 -*-
"""
Tests for Graph-RAG Parsers.

Тесты парсинга договоров и НПА в графовое дерево.
"""
import os
import pytest
from pathlib import Path

from src.core.graph_rag.parser import ContractGraphParser, NPAGraphParser, ParsedNode, ParseResult
from src.core.graph_rag.enums import LayerType, NodeType, ParseStatus


FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"


class TestContractGraphParser:
    """Тесты ContractGraphParser."""

    def setup_method(self):
        self.parser = ContractGraphParser()

    def test_parse_text_basic(self):
        text = """1. ПРЕДМЕТ ДОГОВОРА
1.1 Поставщик обязуется передать товар.
1.2 Количество определяется в Приложении №1.

2. ЦЕНА
2.1 Стоимость 5 000 000 рублей.
"""
        result = self.parser.parse_text(text, title="Тест")

        assert result.parse_status == ParseStatus.FULLY_PARSED
        assert result.layer == LayerType.CONTRACT
        assert result.title == "Тест"
        assert result.nodes_count >= 5  # root + 2 sections + 3 clauses

    def test_parse_text_sections_hierarchy(self):
        text = """1. ПРЕДМЕТ ДОГОВОРА
1.1 Пункт один один.
1.2 Пункт один два.
1.1.1 Подпункт.

2. ЦЕНА
2.1 Стоимость.
"""
        result = self.parser.parse_text(text, title="Тест иерархия")
        root = result.root

        # Должны быть разделы 1 и 2 как дети root
        sections = [c for c in root.children if c.node_type == NodeType.SECTION]
        assert len(sections) == 2
        assert sections[0].number == "1"
        assert sections[1].number == "2"

        # У раздела 1 должны быть дочерние пункты
        section1 = sections[0]
        assert len(section1.children) >= 2

    def test_parse_text_preamble(self):
        text = """ООО "Альфа" именуемое Поставщик заключили договор.

1. ПРЕДМЕТ ДОГОВОРА
1.1 Товар.
"""
        result = self.parser.parse_text(text, title="С преамбулой")
        root = result.root
        preamble = [c for c in root.children if c.node_type == NodeType.PREAMBLE]
        assert len(preamble) == 1
        assert "Альфа" in preamble[0].text

    def test_parse_text_signature_block(self):
        text = """1. ПРЕДМЕТ
1.1 Товар.

Подписи сторон:
__________ / Иванов И.И.
М.П.
"""
        result = self.parser.parse_text(text, title="С подписями")
        root = result.root
        sigs = [c for c in root.children if c.node_type == NodeType.SIGNATURE_BLOCK]
        assert len(sigs) == 1

    def test_parse_text_appendix(self):
        text = """1. ПРЕДМЕТ
1.1 Товар.

Приложение №1
Спецификация товара.
"""
        result = self.parser.parse_text(text, title="С приложением")
        root = result.root
        appendices = [c for c in root.children if c.node_type == NodeType.APPENDIX]
        assert len(appendices) == 1
        assert appendices[0].number == "1"

    def test_parse_text_empty(self):
        result = self.parser.parse_text("", title="Пустой")
        assert result.parse_status == ParseStatus.FAILED
        assert "Empty" in result.parse_errors[0]

    def test_parse_text_numbering_without_dot(self):
        """Регрессия: пункты типа '1.1 Текст' (без точки после номера)."""
        text = """1. ПРЕДМЕТ
1.1 Первый подпункт.
1.2 Второй подпункт.
"""
        result = self.parser.parse_text(text, title="Нумерация без точки")
        flat = result.root.flatten()
        clauses = [n for n in flat if n.node_type == NodeType.CLAUSE]
        assert len(clauses) == 2
        assert clauses[0].number == "1.1"
        assert clauses[1].number == "1.2"

    def test_parse_real_fixture(self):
        """Парсинг реального тестового договора."""
        fixture = FIXTURES_DIR / "test_supply_contract.txt"
        if not fixture.exists():
            pytest.skip("Fixture not found")

        result = self.parser.parse_file(str(fixture))
        assert result.parse_status == ParseStatus.FULLY_PARSED
        assert result.nodes_count >= 20

        # Проверяем основные разделы
        flat = result.root.flatten()
        sections = [n for n in flat if n.node_type == NodeType.SECTION]
        assert len(sections) >= 9  # 10 разделов

    def test_flatten_and_total_nodes(self):
        root = ParsedNode(node_type=NodeType.DOCUMENT, text="root")
        c1 = root.add_child(ParsedNode(node_type=NodeType.SECTION, text="s1"))
        c1.add_child(ParsedNode(node_type=NodeType.CLAUSE, text="cl1"))
        c1.add_child(ParsedNode(node_type=NodeType.CLAUSE, text="cl2"))

        assert root.total_nodes() == 4
        assert len(root.flatten()) == 4


class TestNPAGraphParser:
    """Тесты NPAGraphParser."""

    def setup_method(self):
        self.parser = NPAGraphParser()

    def test_parse_npa_articles(self):
        text = """ГРАЖДАНСКИЙ КОДЕКС РОССИЙСКОЙ ФЕДЕРАЦИИ

Глава 23. Обеспечение исполнения обязательств

Статья 330. Понятие неустойки
1. Неустойкой признается денежная сумма.
2. По требованию об уплате неустойки кредитор не обязан доказывать убытки.

Статья 331. Форма соглашения о неустойке
1. Соглашение о неустойке должно быть в письменной форме.
"""
        result = self.parser.parse_text(text, title="ГК РФ (выдержка)")

        assert result.parse_status == ParseStatus.FULLY_PARSED
        assert result.layer == LayerType.NPA

        flat = result.root.flatten()
        articles = [n for n in flat if n.node_type == NodeType.ARTICLE]
        assert len(articles) == 2
        assert articles[0].number == "330"
        assert articles[1].number == "331"

    def test_parse_npa_chapter_structure(self):
        text = """Глава 23. Обеспечение исполнения обязательств

Статья 330. Понятие неустойки
1. Текст части 1.

Глава 30. Купля-продажа

Статья 506. Договор поставки
Текст статьи.
"""
        result = self.parser.parse_text(text, title="НПА с главами")
        flat = result.root.flatten()
        chapters = [n for n in flat if n.node_type == NodeType.CHAPTER]
        assert len(chapters) == 2
        assert chapters[0].number == "23"
        assert chapters[1].number == "30"

    def test_parse_npa_parts_and_subpoints(self):
        text = """Статья 330. Понятие неустойки
1. Неустойкой признается денежная сумма.
2. По требованию кредитор не обязан доказывать убытки.
3. Кредитор не вправе требовать неустойки, если:
а) должник не виноват
б) обстоятельства непреодолимой силы
"""
        result = self.parser.parse_text(text, title="Статья с частями")
        flat = result.root.flatten()
        parts = [n for n in flat if n.node_type == NodeType.PART]
        assert len(parts) >= 2

    def test_parse_npa_preamble(self):
        text = """ФЕДЕРАЛЬНЫЙ ЗАКОН
от 05.04.2013 N 44-ФЗ
О контрактной системе в сфере закупок

Статья 1. Сфера применения
Текст статьи.
"""
        result = self.parser.parse_text(text, title="ФЗ-44")
        flat = result.root.flatten()
        preamble = [n for n in flat if n.node_type == NodeType.PREAMBLE]
        assert len(preamble) >= 1

    def test_npa_type_detection(self):
        result = self.parser.parse_text("Текст.", title="Гражданский кодекс РФ")
        assert result.document_type == "codex"

        result2 = self.parser.parse_text("Текст.", title="Федеральный закон N 44-ФЗ")
        assert result2.document_type == "federal_law"

    def test_parse_npa_empty(self):
        result = self.parser.parse_text("", title="Пустой НПА")
        assert result.parse_status == ParseStatus.FAILED
