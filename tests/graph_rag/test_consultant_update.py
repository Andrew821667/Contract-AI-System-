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
from src.core.graph_rag.models import GraphDocument, GraphEdge, GraphEntity, GraphNode, NodeVersion
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


def test_phase2_links_norm_refs_of_replaced_document(test_db):
    """Фаза 2 от залитых в прогоне: «ст. 330 ГК РФ» → статья 330 ГК."""
    importer = ConsultantImporter(db=test_db)
    code = _ingest(importer, CODE_V1, "Гражданский кодекс РФ", CODE_URL)
    law_text = LAW.replace("по правилам Гражданского кодекса", "по правилам ст. 330 ГК РФ")
    law = _ingest(importer, law_text, "Федеральный закон N 777-ФЗ", LAW_URL)
    importer._docid_to_gdoc = {"777": law.id}

    assert importer.resolve_cross_document_edges() >= 1
    art_330 = _node(test_db, code.id, "article", "330")
    law_nodes = {n.id for n in test_db.query(GraphNode).filter(GraphNode.document_id == law.id)}
    edges = test_db.query(GraphEdge).filter(GraphEdge.edge_type == "regulated_by",
                                            GraphEdge.target_id == art_330.id).all()
    assert any(e.source_id in law_nodes for e in edges)
    # повторный прогон не плодит дублей
    assert importer.resolve_cross_document_edges() == 0


def test_phase2_prefers_code_over_law_mentioning_it(test_db):
    """Новая редакция ГК залита позже ФЗ «О введении в действие … ГК» —
    «ст. 330 ГК РФ» всё равно ведёт в ГК, а не в закон о введении."""
    importer = ConsultantImporter(db=test_db)
    intro = _ingest(importer, LAW, 'Федеральный закон N 52-ФЗ "О введении в действие части '
                    'первой Гражданского кодекса Российской Федерации"',
                    "https://www.consultant.ru/document/cons_doc_LAW_52/")
    code = _ingest(importer, CODE_V1, "Гражданский кодекс РФ", CODE_URL)
    law_text = LAW.replace("по правилам Гражданского кодекса", "по правилам ст. 330 ГК РФ")
    law = _ingest(importer, law_text, "Федеральный закон N 777-ФЗ", LAW_URL)
    importer._docid_to_gdoc = {"777": law.id}

    importer.resolve_cross_document_edges()
    law_nodes = {n.id for n in test_db.query(GraphNode).filter(GraphNode.document_id == law.id)}
    targets = {e.target_id for e in test_db.query(GraphEdge).filter(
        GraphEdge.edge_type == "regulated_by", GraphEdge.source_id.in_(law_nodes))}
    assert _node(test_db, code.id, "article", "330").id in targets
    intro_nodes = {n.id for n in test_db.query(GraphNode).filter(GraphNode.document_id == intro.id)}
    assert not targets & intro_nodes


def test_phase2_finds_article_in_its_part_of_code(test_db):
    """«ст. 506 ГК РФ» — статья второй части: ищется во всех частях кодекса."""
    importer = ConsultantImporter(db=test_db)
    _ingest(importer, CODE_V1, "Гражданский кодекс РФ часть 1", CODE_URL)
    part2 = _ingest(importer, """ГРАЖДАНСКИЙ КОДЕКС РОССИЙСКОЙ ФЕДЕРАЦИИ (ЧАСТЬ ВТОРАЯ)

Статья 506. Договор поставки
1. По договору поставки поставщик обязуется передать товары покупателю.
""", "Гражданский кодекс РФ часть 2", "https://www.consultant.ru/document/cons_doc_LAW_9027/")
    law_text = LAW.replace("по правилам Гражданского кодекса", "по правилам ст. 506 ГК РФ")
    law = _ingest(importer, law_text, "Федеральный закон N 777-ФЗ", LAW_URL)
    importer._docid_to_gdoc = {"777": law.id}

    importer.resolve_cross_document_edges()
    law_nodes = {n.id for n in test_db.query(GraphNode).filter(GraphNode.document_id == law.id)}
    targets = {e.target_id for e in test_db.query(GraphEdge).filter(
        GraphEdge.edge_type == "regulated_by", GraphEdge.source_id.in_(law_nodes))}
    assert _node(test_db, part2.id, "article", "506").id in targets


def test_phase2_links_fz_by_date_and_number(test_db):
    """ФЗ связывается по дате и номеру: «от 28.12.2013 N 425-ФЗ» ведёт в
    свой закон и не цепляет N 4-ФЗ (было ILIKE '%ФЗ-4%'); «от 06.04.2011
    N 63-ФЗ» — в закон 2011 года, а не 2002-го; номер без даты не
    связывается вовсе."""
    importer = ConsultantImporter(db=test_db)
    fz425 = _ingest(importer, LAW, "Федеральный закон от 28.12.2013 N 425-ФЗ",
                    "https://www.consultant.ru/document/cons_doc_LAW_156571/")
    fz4 = _ingest(importer, LAW, "Федеральный закон от 10.01.2003 N 4-ФЗ",
                  "https://www.consultant.ru/document/cons_doc_LAW_4/")
    fz63a = _ingest(importer, LAW, "Федеральный закон от 31.05.2002 N 63-ФЗ",
                    "https://www.consultant.ru/document/cons_doc_LAW_63/")
    fz63b = _ingest(importer, LAW, "Федеральный закон от 06.04.2011 N 63-ФЗ",
                    "https://www.consultant.ru/document/cons_doc_LAW_112701/")
    law_text = LAW.replace("по правилам Гражданского кодекса",
                           "по правилам Федерального закона от 28.12.2013 N 425-ФЗ.\n"
                           "2. Подпись — по Федеральному закону от 06.04.2011 N 63-ФЗ.\n"
                           "3. Иное — по Федеральному закону N 4-ФЗ")
    law = _ingest(importer, law_text, "Федеральный закон N 777-ФЗ", LAW_URL)
    codes = {e.norm_code for e in test_db.query(GraphEntity).filter(GraphEntity.entity_type == "norm_ref")}
    assert {"ФЗ-425", "ФЗ-63", "ФЗ-4"} <= codes
    importer._docid_to_gdoc = {"777": law.id}

    importer.resolve_cross_document_edges()
    law_nodes = {n.id for n in test_db.query(GraphNode).filter(GraphNode.document_id == law.id)}
    target_docs = {n.document_id for n in test_db.query(GraphNode).join(
        GraphEdge, GraphEdge.target_id == GraphNode.id).filter(
        GraphEdge.edge_type == "regulated_by", GraphEdge.source_id.in_(law_nodes))}
    assert {fz425.id, fz63b.id} <= target_docs
    assert not target_docs & {fz4.id, fz63a.id}


def test_code_titles_map_to_their_own_norm_codes():
    """КАС не перехватывает код КоАП; КоАП («КоАП РФ» в выгрузке) и кодексы
    через дефис («Уголовно-процессуальный») получают свои коды."""
    from src.core.graph_rag.importers.consultant_importer import _normcode_from_title
    assert _normcode_from_title("Кодекс административного судопроизводства РФ") == "КАС РФ"
    assert _normcode_from_title("КоАП РФ") == "КоАП РФ"
    assert _normcode_from_title(
        "Кодекс Российской Федерации об административных правонарушениях") == "КоАП РФ"
    assert _normcode_from_title("Уголовно-процессуальный кодекс РФ") == "УПК РФ"
    assert _normcode_from_title("Уголовно-исполнительный кодекс РФ") == "УИК РФ"
    assert _normcode_from_title("Уголовный кодекс РФ") == "УК РФ"
