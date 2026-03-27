# -*- coding: utf-8 -*-
"""
Tests for Graph-RAG Extractors.

Тесты reference_extractor и entity_extractor.
"""
import pytest
from datetime import datetime

from src.core.graph_rag.extraction import ReferenceExtractor, EntityExtractor


class TestReferenceExtractor:
    """Тесты ReferenceExtractor."""

    def setup_method(self):
        self.extractor = ReferenceExtractor()

    def test_norm_ref_article(self):
        refs = self.extractor.extract("в соответствии со ст. 330 ГК РФ")
        norm_refs = [r for r in refs if r.ref_type == "norm_ref"]
        assert len(norm_refs) >= 1
        ref = norm_refs[0]
        assert ref.article == "330"
        assert "ГК РФ" in ref.norm_code

    def test_norm_ref_article_with_part(self):
        refs = self.extractor.extract("ст. 15 ч. 2 п. 3 ГК РФ")
        norm_refs = [r for r in refs if r.ref_type == "norm_ref"]
        assert len(norm_refs) >= 1
        ref = norm_refs[0]
        assert ref.article == "15"

    def test_clause_ref(self):
        refs = self.extractor.extract("см. п. 7.3 настоящего Договора")
        clause_refs = [r for r in refs if r.ref_type == "clause_ref"]
        assert len(clause_refs) == 1
        assert clause_refs[0].clause_number == "7.3"

    def test_clause_ref_subclause(self):
        refs = self.extractor.extract("согласно п.п. 2.1.1 Договора")
        clause_refs = [r for r in refs if r.ref_type == "clause_ref"]
        assert len(clause_refs) == 1
        assert clause_refs[0].clause_number == "2.1.1"

    def test_appendix_ref(self):
        refs = self.extractor.extract("в Приложении №1 к настоящему Договору")
        app_refs = [r for r in refs if r.ref_type == "appendix_ref"]
        assert len(app_refs) == 1
        assert app_refs[0].ref_number == "1"

    def test_table_ref(self):
        refs = self.extractor.extract("расценки указаны в Таблице 2")
        tbl_refs = [r for r in refs if r.ref_type == "table_ref"]
        assert len(tbl_refs) == 1
        assert tbl_refs[0].ref_number == "2"

    def test_gost_ref(self):
        refs = self.extractor.extract("в соответствии с ГОСТ 9353-2016")
        gost_refs = [r for r in refs if r.ref_type == "gost_ref"]
        assert len(gost_refs) == 1
        assert "9353" in gost_refs[0].gost_code

    def test_federal_law_ref(self):
        refs = self.extractor.extract("Федеральный закон от 05.04.2013 N 44-ФЗ")
        norm_refs = [r for r in refs if r.ref_type == "norm_ref"]
        assert len(norm_refs) >= 1
        assert "ФЗ" in norm_refs[0].norm_code

    def test_term_definition(self):
        refs = self.extractor.extract('«Товар» означает комплектующие для оборудования')
        term_refs = [r for r in refs if r.ref_type == "defined_in"]
        assert len(term_refs) == 1
        assert "Товар" in term_refs[0].clause_number

    def test_multiple_refs(self):
        text = "Неустойка по ст. 330 ГК РФ, см. п. 4.2 и Приложение №1"
        refs = self.extractor.extract(text)
        types = {r.ref_type for r in refs}
        assert "norm_ref" in types
        assert "clause_ref" in types
        assert "appendix_ref" in types

    def test_deduplicate_overlapping(self):
        text = "ст. 330 ГК РФ"
        refs = self.extractor.extract(text)
        # Не должно быть перекрывающихся ссылок
        for i in range(len(refs) - 1):
            assert refs[i].end <= refs[i + 1].start

    def test_extract_from_nodes(self):
        nodes = [
            {"node_id": "n1", "text": "ст. 330 ГК РФ"},
            {"node_id": "n2", "text": "обычный текст без ссылок"},
            {"node_id": "n3", "text": "п. 2.1 Договора"},
        ]
        result = self.extractor.extract_from_nodes(nodes)
        assert "n1" in result
        assert "n2" not in result  # нет ссылок
        assert "n3" in result


class TestEntityExtractor:
    """Тесты EntityExtractor."""

    def setup_method(self):
        self.extractor = EntityExtractor()

    def test_monetary_rubles(self):
        entities = self.extractor.extract("Стоимость 5 000 000 рублей")
        monetary = [e for e in entities if e.entity_type == "monetary"]
        assert len(monetary) == 1
        assert monetary[0].amount == 5000000.0
        assert monetary[0].currency == "RUB"

    def test_monetary_rubles_short(self):
        entities = self.extractor.extract("Сумма 150 000 руб.")
        monetary = [e for e in entities if e.entity_type == "monetary"]
        assert len(monetary) == 1
        assert monetary[0].amount == 150000.0

    def test_monetary_usd(self):
        entities = self.extractor.extract("Оплата $100,000")
        monetary = [e for e in entities if e.entity_type == "monetary"]
        assert len(monetary) >= 1

    def test_date_dmy(self):
        entities = self.extractor.extract("срок до 15.02.2024")
        dates = [e for e in entities if e.entity_type == "date_ref"]
        assert len(dates) == 1
        assert dates[0].date_value.year == 2024
        assert dates[0].date_value.month == 2
        assert dates[0].date_value.day == 15
        assert dates[0].date_type == "deadline"

    def test_date_russian(self):
        entities = self.extractor.extract("подписан 15 января 2024")
        dates = [e for e in entities if e.entity_type == "date_ref"]
        assert len(dates) == 1
        assert dates[0].date_value.month == 1

    def test_date_context_start(self):
        entities = self.extractor.extract("с 01.03.2024 действует")
        dates = [e for e in entities if e.entity_type == "date_ref"]
        assert len(dates) == 1
        assert dates[0].date_type == "start"

    def test_clause_type_penalty(self):
        entities = self.extractor.extract("неустойка в размере 0,1% за каждый день")
        types = [e for e in entities if e.entity_type == "clause_type"]
        assert any(e.entity_value == "penalty" for e in types)

    def test_clause_type_force_majeure(self):
        entities = self.extractor.extract("обстоятельства форс-мажора")
        types = [e for e in entities if e.entity_type == "clause_type"]
        assert any(e.entity_value == "force_majeure" for e in types)

    def test_contract_type_supply(self):
        entities = self.extractor.extract("договор поставки товаров")
        types = [e for e in entities if e.entity_type == "contract_type"]
        assert any(e.entity_value == "supply" for e in types)

    def test_contract_type_lease(self):
        entities = self.extractor.extract("договор аренды помещения")
        types = [e for e in entities if e.entity_type == "contract_type"]
        assert any(e.entity_value == "lease" for e in types)

    def test_multiple_entities(self):
        text = "Сумма 1 500 000 рублей, срок до 15.02.2024, неустойка 0,1%"
        entities = self.extractor.extract(text)
        types = {e.entity_type for e in entities}
        assert "monetary" in types
        assert "date_ref" in types
        assert "clause_type" in types
