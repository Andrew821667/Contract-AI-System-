# -*- coding: utf-8 -*-
"""Индекс номера статьи и план поиска по всем НПА."""

from sqlalchemy import inspect, text

from src.core.graph_rag.models import GraphDocument, GraphNode


def test_number_index_created(test_db):
    indexes = {
        idx["name"]: idx
        for idx in inspect(test_db.connection()).get_indexes("graph_nodes")
    }
    assert "ix_graph_nodes_number" in indexes
    idx = indexes["ix_graph_nodes_number"]
    assert idx["column_names"] == ["number"]
    assert not idx["unique"]


def test_number_lookup_uses_index(test_db):
    doc = GraphDocument(layer="npa", title="Тестовый НПА")
    test_db.add(doc)
    test_db.flush()
    test_db.execute(
        GraphNode.__table__.insert(),
        [
            {
                "document_id": doc.id,
                "layer": "npa",
                "node_type": "article",
                "number": str(i),
                "text": f"Текст статьи {i}",
                "is_archived": False,
            }
            for i in range(1, 5001)
        ],
    )
    query = text(
        "EXPLAIN QUERY PLAN SELECT * FROM graph_nodes "
        "WHERE number=:number AND is_archived=0 AND layer IN ('npa') LIMIT 5"
    )
    test_db.execute(text("ANALYZE"))
    plan = test_db.execute(query, {"number": "506"}).all()
    assert any(
        "USING INDEX ix_graph_nodes_number (number=?)" in row[3] for row in plan
    ), plan
