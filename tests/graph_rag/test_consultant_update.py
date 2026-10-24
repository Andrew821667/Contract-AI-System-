# -*- coding: utf-8 -*-
"""
Замена редакции НПА в графе (consultant_importer --update).

Новая редакция кодекса в К+ — под тем же номером документа, поэтому граф
документа удаляется и строится заново. Ссылки на кодекс из ДРУГИХ документов
недельный прогон сам не восстановит (Фаза 2 строится только от залитых в нём
документов) — их переносит замена: на тот же адрес в новой редакции, а если
такого узла больше нет — на ближайшего предка.
"""
from src.core.graph_rag.importers.consultant_importer import ConsultantImporter
from src.core.graph_rag.models import GraphDocument, GraphEdge, GraphNode, NodeVersion
from src.core.graph_rag.parser import NPAGraphParser

CODE_URL = "https://www.consultant.ru/document/cons_doc_LAW_5142/"
LAW_URL = "https://www.consultant.ru/document/cons_doc_LAW_777/"

CODE_V1 = """ГРАЖДАНСКИЙ КОДЕКС РОССИЙСКОЙ ФЕДЕРАЦИИ

Глава 23. Обеспечение исполнения обязательств

Статья 330. Понятие неустойки
1. Неустойкой признается денежная сумма.
2. По требованию об уплате неустойки кредитор не обязан доказывать убытки.

Статья 331. Форма соглашения о неустойке
1. Соглашение о неустойке должно быть в письменной форме.
"""

# Новая редакция: статья 330 изменена, статья 331 исключена.
CODE_V2 = """ГРАЖДАНСКИЙ КОДЕКС РОССИЙСКОЙ ФЕДЕРАЦИИ

Глава 23. Обеспечение исполнения обязательств

Статья 330. Понятие неустойки
1. Неустойкой (штрафом, пеней) признается определенная законом или договором денежная сумма.
2. По требованию об уплате неустойки кредитор не обязан доказывать причинение ему убытков.
"""

LAW = """ФЕДЕРАЛЬНЫЙ ЗАКОН

Статья 1. Предмет
1. Неустойка взыскивается по правилам Гражданского кодекса.
"""


def _ingest(importer, text, title, url):
    parsed = NPAGraphParser().parse_text(text, title=title)
    return importer.pipeline._ingest(parsed, source_file=url).document


def _node(db, doc_id, node_type, number=None):
    q = db.query(GraphNode).filter(GraphNode.document_id == doc_id,
                                   GraphNode.node_type == node_type)
    if number is not None:
        q = q.filter(GraphNode.number == number)
    return q.order_by(GraphNode.level, GraphNode.position).first()


def _link(importer, src, tgt):
    importer.pipeline.repo.edges.create(
        actor="test", source_id=src.id, target_id=tgt.id, edge_type="regulated_by",
        edge_class="fact", status="machine_extracted", extracted_by="rule",
        confidence=0.8, evidence="ст. 330 ГК РФ", rationale="norm_ref")


def test_replace_moves_inbound_links_to_new_edition(test_db):
    importer = ConsultantImporter(db=test_db)
    code = _ingest(importer, CODE_V1, "Гражданский кодекс РФ", CODE_URL)
    law = _ingest(importer, LAW, "Федеральный закон N 777-ФЗ", LAW_URL)
    src = _node(test_db, law.id, "article", "1")
    old_330 = _node(test_db, code.id, "article", "330")
    old_331 = _node(test_db, code.id, "article", "331")
    _link(importer, src, old_330)
    _link(importer, src, old_331)
    _link(importer, src, _node(test_db, code.id, "document"))
    importer.pipeline.repo.commit()

    inbound = importer._purge_by_source(CODE_URL)
    assert len(inbound) == 3
    new = _ingest(importer, CODE_V2, "Гражданский кодекс РФ", CODE_URL)
    assert importer._restore_inbound(inbound, new.id) == 3

    targets = {e.target_id for e in test_db.query(GraphEdge).filter(GraphEdge.source_id == src.id)}
    new_330 = _node(test_db, new.id, "article", "330")
    new_root = _node(test_db, new.id, "document")
    assert new_330.id in targets
    # статьи 331 в новой редакции нет — ссылка ушла на ближайшего предка (главу)
    assert _node(test_db, new.id, "chapter", "23").id in targets
    assert new_root.id in targets
    new_text = " ".join(n.text for n in test_db.query(GraphNode).filter(GraphNode.document_id == new.id))
    assert "Неустойкой (штрафом, пеней)" in new_text


def test_replace_leaves_no_orphans(test_db):
    importer = ConsultantImporter(db=test_db)
    code_id = _ingest(importer, CODE_V1, "Гражданский кодекс РФ", CODE_URL).id
    old_ids = {n.id for n in test_db.query(GraphNode).filter(GraphNode.document_id == code_id)}
    assert test_db.query(NodeVersion).filter(NodeVersion.node_id.in_(old_ids)).count() > 0

    assert importer._purge_by_source(CODE_URL) == []
    importer.pipeline.repo.commit()

    assert test_db.query(GraphDocument).filter(GraphDocument.id == code_id).count() == 0
    assert test_db.query(NodeVersion).filter(NodeVersion.node_id.in_(old_ids)).count() == 0
    assert test_db.query(GraphEdge).filter(
        GraphEdge.source_id.in_(old_ids) | GraphEdge.target_id.in_(old_ids)).count() == 0


def test_purge_of_unknown_document_is_none(test_db):
    importer = ConsultantImporter(db=test_db)
    assert importer._purge_by_source(CODE_URL) is None
