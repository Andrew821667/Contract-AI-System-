# -*- coding: utf-8 -*-
"""
Tests for Graph-RAG Pipeline.

Integration тесты: полный цикл parse → build → extract → edges/entities.
"""
import pytest
from pathlib import Path

from src.core.graph_rag.pipeline import GraphRAGPipeline
from src.core.graph_rag.repository import GraphRepository
from src.core.graph_rag.models import GraphEntity, GraphEdge


FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"

SAMPLE_CONTRACT = """ДОГОВОР ПОСТАВКИ № 2024-001

ООО "Альфа" именуемое Поставщик и ООО "Бета" именуемое Покупатель заключили настоящий договор.

1. ПРЕДМЕТ ДОГОВОРА
1.1 Поставщик обязуется передать товар согласно Приложению №1.
1.2 Количество и цена определяются в Приложении №1.

2. ЦЕНА
2.1 Общая стоимость составляет 5 000 000 рублей.
2.2 Оплата до 01.09.2026.

3. ОТВЕТСТВЕННОСТЬ
3.1 Неустойка в размере 0,1% за каждый день просрочки.
3.2 Ответственность определяется в соответствии со ст. 330 ГК РФ.
3.3 См. также п. 2.1 настоящего Договора.
"""

SAMPLE_NPA = """ГРАЖДАНСКИЙ КОДЕКС РОССИЙСКОЙ ФЕДЕРАЦИИ

Глава 23. Обеспечение исполнения обязательств

Статья 330. Понятие неустойки
1. Неустойкой признается денежная сумма, которую должник обязан уплатить кредитору.
2. По требованию об уплате неустойки кредитор не обязан доказывать убытки.
"""


class TestGraphRAGPipeline:
    """Integration тесты GraphRAGPipeline."""

    def test_ingest_contract_text(self, test_db):
        pipeline = GraphRAGPipeline(test_db)
        result = pipeline.ingest_text(
            text=SAMPLE_CONTRACT,
            title="Договор поставки №2024-001",
            layer="contract",
        )

        assert result.document is not None
        assert result.document.layer == "contract"
        assert result.nodes_count >= 8  # root + preamble + 3 sections + clauses
        assert result.edges_count > 0   # structural edges

    def test_ingest_creates_entities(self, test_db):
        pipeline = GraphRAGPipeline(test_db)
        result = pipeline.ingest_text(
            text=SAMPLE_CONTRACT,
            title="Entities test",
            layer="contract",
        )

        # Должны быть извлечены сущности
        assert result.entities_count > 0

        # Проверяем monetary entity
        entities = test_db.query(GraphEntity).filter(
            GraphEntity.entity_type == "monetary"
        ).all()
        assert len(entities) >= 1
        amounts = [e.amount for e in entities]
        assert 5000000.0 in amounts

    def test_ingest_creates_date_entities(self, test_db):
        pipeline = GraphRAGPipeline(test_db)
        result = pipeline.ingest_text(
            text=SAMPLE_CONTRACT,
            title="Dates test",
            layer="contract",
        )

        dates = test_db.query(GraphEntity).filter(
            GraphEntity.entity_type == "date_ref"
        ).all()
        assert len(dates) >= 1

    def test_ingest_creates_fact_edges(self, test_db):
        pipeline = GraphRAGPipeline(test_db)
        result = pipeline.ingest_text(
            text=SAMPLE_CONTRACT,
            title="Fact edges test",
            layer="contract",
        )

        # п. 3.3 ссылается на п. 2.1 → должен создаться fact edge
        assert result.fact_edges_count >= 1

        fact_edges = test_db.query(GraphEdge).filter(
            GraphEdge.edge_class == "fact"
        ).all()
        assert len(fact_edges) >= 1

    def test_ingest_creates_norm_ref_entities(self, test_db):
        pipeline = GraphRAGPipeline(test_db)
        result = pipeline.ingest_text(
            text=SAMPLE_CONTRACT,
            title="Norm ref test",
            layer="contract",
        )

        # ст. 330 ГК РФ → norm_ref entity
        norm_refs = test_db.query(GraphEntity).filter(
            GraphEntity.entity_type == "norm_ref"
        ).all()
        assert len(norm_refs) >= 1
        codes = [e.norm_code for e in norm_refs]
        assert any("ГК" in c for c in codes if c)

    def test_ingest_npa_text(self, test_db):
        pipeline = GraphRAGPipeline(test_db)
        result = pipeline.ingest_text(
            text=SAMPLE_NPA,
            title="ГК РФ (выдержка)",
            layer="npa",
        )

        assert result.document is not None
        assert result.document.layer == "npa"
        assert result.nodes_count >= 4  # root + chapter + article + parts

    def test_ingest_real_fixture(self, test_db):
        """Integration: парсинг реального тестового договора."""
        fixture = FIXTURES_DIR / "test_supply_contract.txt"
        if not fixture.exists():
            pytest.skip("Fixture not found")

        pipeline = GraphRAGPipeline(test_db)
        result = pipeline.ingest_file(
            str(fixture),
            layer="contract",
        )

        assert result.document is not None
        assert result.nodes_count >= 20
        assert result.entities_count >= 5  # суммы + даты
        assert result.edges_count > 0

    def test_ingest_updates_document_stats(self, test_db):
        pipeline = GraphRAGPipeline(test_db)
        result = pipeline.ingest_text(
            text=SAMPLE_CONTRACT,
            title="Stats test",
            layer="contract",
        )

        doc = GraphRepository(test_db).documents.get_by_id(result.document.id)
        assert doc.nodes_count > 0
        assert doc.edges_count > 0


class TestGraphRAGPipelineRetrieval:
    """Тесты retrieval после ingestion."""

    def test_search_after_ingest(self, test_db):
        from src.core.graph_rag.tools import GraphReadTools

        pipeline = GraphRAGPipeline(test_db)
        pipeline.ingest_text(
            text=SAMPLE_CONTRACT,
            title="Search test",
            layer="contract",
        )

        tools = GraphReadTools(test_db)
        # SQLite LIKE case-sensitive для Cyrillic, ищем с учётом регистра
        result = tools.search("стоимость составляет")

        assert result["count"] > 0
        # Должен найти п. 2.1 (стоимость)
        numbers = [r["number"] for r in result["results"] if r["number"]]
        assert "2.1" in numbers or any("2" in n for n in numbers if n)

    def test_search_by_clause_number(self, test_db):
        from src.core.graph_rag.tools import GraphReadTools

        pipeline = GraphRAGPipeline(test_db)
        pipeline.ingest_text(
            text=SAMPLE_CONTRACT,
            title="Clause number test",
            layer="contract",
        )

        tools = GraphReadTools(test_db)
        result = tools.search("п. 2.1")

        assert result["count"] > 0

    def test_ask_returns_context(self, test_db):
        from src.core.graph_rag.tools import GraphReadTools

        pipeline = GraphRAGPipeline(test_db)
        pipeline.ingest_text(
            text=SAMPLE_CONTRACT,
            title="Ask test",
            layer="contract",
        )

        tools = GraphReadTools(test_db)
        result = tools.ask("Какова стоимость договора?")

        assert result["confidence"] != "no_data"
        assert len(result["context_text"]) > 0
        assert "5 000 000" in result["context_text"] or "5000000" in result["context_text"]
