# -*- coding: utf-8 -*-
"""
Graph-RAG Ingestion Pipeline

Полный цикл загрузки документа в граф:
  1. Parse (файл/текст/XML → ParseResult)
  2. Build (ParseResult → GraphDocument + GraphNode + structural edges)
  3. Extract references (text → fact edges: references, regulated_by, ...)
  4. Extract entities (text → GraphEntity: monetary, dates, norm_ref, ...)

Использование:
    pipeline = GraphRAGPipeline(db)
    result = pipeline.ingest_file("contract.docx", layer="contract")
    # result.document — GraphDocument
    # result.nodes_count, result.edges_count, result.entities_count
"""
from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass, field
from typing import List, Optional, Dict

from sqlalchemy.orm import Session

from .enums import (
    LayerType, EdgeType, EdgeClass, EdgeStatus, ExtractedBy, AuditAction,
)
from .models import GraphDocument, GraphNode, GraphEdge, GraphEntity
from .repository import GraphRepository
from .parser import ContractGraphParser, NPAGraphParser, GraphBuilder, ParseResult
from .extraction import ReferenceExtractor, EntityExtractor, ExtractedReference, ExtractedEntity

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────
# Pipeline result
# ──────────────────────────────────────────────

@dataclass
class IngestionResult:
    """Результат загрузки документа в граф."""
    document: GraphDocument
    nodes_count: int = 0
    edges_count: int = 0
    entities_count: int = 0
    fact_edges_count: int = 0
    parse_errors: List[str] = field(default_factory=list)
    extraction_warnings: List[str] = field(default_factory=list)


# ──────────────────────────────────────────────
# Mapping: reference type → edge type
# ──────────────────────────────────────────────

REF_TYPE_TO_EDGE = {
    'norm_ref': EdgeType.REGULATED_BY,
    'clause_ref': EdgeType.REFERENCES,
    'appendix_ref': EdgeType.APPENDIX_REF,
    'table_ref': EdgeType.TABLE_REF,
    'gost_ref': EdgeType.REGULATED_BY,
    'defined_in': EdgeType.DEFINED_IN,
}


class GraphRAGPipeline:
    """
    Полный pipeline загрузки документа в граф.

    Использование:
        pipeline = GraphRAGPipeline(db)

        # Из файла
        result = pipeline.ingest_file("contract.docx", layer="contract")

        # Из текста
        result = pipeline.ingest_text(text, title="Договор поставки", layer="contract")

        # Из XML (от существующего DocumentParser)
        result = pipeline.ingest_xml(xml_content, title="...", contract_id="...")
    """

    def __init__(self, db: Session):
        self.db = db
        self.repo = GraphRepository(db)
        self.contract_parser = ContractGraphParser()
        self.npa_parser = NPAGraphParser()
        self.builder = GraphBuilder(db)
        self.ref_extractor = ReferenceExtractor()
        self.entity_extractor = EntityExtractor()

    # ──────────────────────────────────────────
    # Public API
    # ──────────────────────────────────────────

    def ingest_file(
        self,
        file_path: str,
        layer: str = "contract",
        contract_id: Optional[str] = None,
        legal_document_id: Optional[str] = None,
    ) -> IngestionResult:
        """Загрузить файл в граф."""
        parser = self._get_parser(layer)
        parse_result = parser.parse_file(file_path)
        return self._ingest(
            parse_result,
            source_file=file_path,
            contract_id=contract_id,
            legal_document_id=legal_document_id,
        )

    def ingest_text(
        self,
        text: str,
        title: str = "Без названия",
        layer: str = "contract",
        contract_id: Optional[str] = None,
        legal_document_id: Optional[str] = None,
    ) -> IngestionResult:
        """Загрузить текст в граф."""
        parser = self._get_parser(layer)
        parse_result = parser.parse_text(text, title=title)
        return self._ingest(
            parse_result,
            contract_id=contract_id,
            legal_document_id=legal_document_id,
        )

    def ingest_xml(
        self,
        xml_content: str,
        title: str = "Без названия",
        contract_id: Optional[str] = None,
    ) -> IngestionResult:
        """Загрузить XML от существующего DocumentParser в граф."""
        parse_result = self.contract_parser.parse_xml(xml_content, title=title)
        return self._ingest(
            parse_result,
            contract_id=contract_id,
        )

    # ──────────────────────────────────────────
    # Internal: основной pipeline
    # ──────────────────────────────────────────

    def _ingest(
        self,
        parse_result: ParseResult,
        source_file: Optional[str] = None,
        contract_id: Optional[str] = None,
        legal_document_id: Optional[str] = None,
    ) -> IngestionResult:
        """Полный цикл: parse result → graph + extraction."""
        result = IngestionResult(document=None)  # type: ignore
        result.parse_errors = parse_result.parse_errors

        # Re-ingestion protection: check if document already exists
        if source_file:
            existing = (self.db.query(GraphDocument)
                        .filter(GraphDocument.source_file == source_file,
                                GraphDocument.status == 'active')
                        .first())
            if existing:
                logger.warning(f"Document already ingested: {source_file} (id={existing.id})")
                result.document = existing
                result.extraction_warnings.append(
                    f"Документ уже загружен (id={existing.id}). Повторная загрузка пропущена."
                )
                return result

        # Wrap entire pipeline in try/except for atomicity
        try:
            # Step 1: Build graph (document + nodes + structural edges)
            doc = self.builder.build(
                parse_result,
                source_file=source_file,
                contract_id=contract_id,
                legal_document_id=legal_document_id,
            )
            result.document = doc
            result.nodes_count = parse_result.nodes_count

            logger.info(f"Graph built: doc={doc.id}, nodes={result.nodes_count}")

            # Step 2: Collect all leaf/text nodes for extraction
            db_nodes = self.repo.nodes.get_by_document(doc.id)
            node_texts = [
                {'node_id': n.id, 'text': n.text, 'number': n.number, 'node_type': n.node_type}
                for n in db_nodes
                if n.text and n.node_type not in ('document',)
            ]

            # Step 3: Extract references → fact edges
            fact_edges = self._extract_and_create_edges(doc, node_texts, db_nodes)
            result.fact_edges_count = fact_edges

            # Step 4: Extract entities → GraphEntity
            entities = self._extract_and_create_entities(node_texts)
            result.entities_count = entities

            # Step 5: Update stats
            self.repo.documents.update_stats(doc.id)

            # Refresh counts from DB
            doc_refreshed = self.repo.documents.get_by_id(doc.id)
            if doc_refreshed:
                result.edges_count = doc_refreshed.edges_count

            # Commit
            self.repo.commit()

        except Exception as e:
            logger.error(f"Ingestion failed, rolling back: {e}")
            self.db.rollback()
            raise

        logger.info(
            f"Ingestion complete: doc={doc.id}, nodes={result.nodes_count}, "
            f"edges={result.edges_count}, fact_edges={result.fact_edges_count}, "
            f"entities={result.entities_count}"
        )

        return result

    # ──────────────────────────────────────────
    # Step 3: References → fact edges
    # ──────────────────────────────────────────

    def _extract_and_create_edges(
        self,
        doc: GraphDocument,
        node_texts: List[Dict],
        db_nodes: List[GraphNode],
    ) -> int:
        """Извлечь ссылки и создать fact edges."""
        # Индексы для быстрого поиска
        number_to_node: Dict[str, GraphNode] = {}
        appendix_to_node: Dict[str, GraphNode] = {}
        table_to_node: Dict[str, GraphNode] = {}

        for n in db_nodes:
            if n.number:
                number_to_node[n.number] = n
            if n.node_type == 'appendix' and n.number:
                appendix_to_node[n.number] = n
            if n.node_type == 'table' and n.number:
                table_to_node[n.number] = n

        created = 0

        for node_info in node_texts:
            refs = self.ref_extractor.extract(node_info['text'])
            source_id = node_info['node_id']

            for ref in refs:
                target_node = self._resolve_reference_target(
                    ref, number_to_node, appendix_to_node, table_to_node
                )

                edge_type = REF_TYPE_TO_EDGE.get(ref.ref_type)
                if not edge_type:
                    continue

                if target_node:
                    # Intra-document edge: source → target
                    if source_id != target_node.id:
                        self.repo.edges.create(
                            actor="parser",
                            source_id=source_id,
                            target_id=target_node.id,
                            edge_type=edge_type.value,
                            edge_class=EdgeClass.FACT.value,
                            status=EdgeStatus.MACHINE_EXTRACTED.value,
                            extracted_by=ExtractedBy.RULE.value,
                            confidence=ref.confidence,
                            evidence=ref.raw_text,
                            rationale=f"Reference extracted: {ref.ref_type}",
                        )
                        created += 1
                else:
                    # External reference (e.g., norm_ref to an NPA not in the graph)
                    # Store as entity for now, edge will be created when NPA is ingested
                    if ref.ref_type == 'norm_ref' and ref.norm_code:
                        self.repo.entities.create(
                            node_id=source_id,
                            entity_type='norm_ref',
                            entity_value=f"{ref.norm_code} ст. {ref.article}" if ref.article else ref.norm_code,
                            raw_text=ref.raw_text,
                            norm_code=ref.norm_code,
                            norm_article=ref.article,
                            norm_part=ref.part,
                            extracted_by=ExtractedBy.RULE.value,
                            confidence=ref.confidence,
                        )

        return created

    def _resolve_reference_target(
        self,
        ref: ExtractedReference,
        number_to_node: Dict[str, GraphNode],
        appendix_to_node: Dict[str, GraphNode],
        table_to_node: Dict[str, GraphNode],
    ) -> Optional[GraphNode]:
        """Разрешить ссылку в конкретный узел графа."""
        if ref.ref_type == 'clause_ref' and ref.clause_number:
            return number_to_node.get(ref.clause_number)

        if ref.ref_type == 'appendix_ref' and ref.ref_number:
            return appendix_to_node.get(ref.ref_number)

        if ref.ref_type == 'table_ref' and ref.ref_number:
            return table_to_node.get(ref.ref_number)

        # norm_ref и gost_ref — внешние ссылки, target разрешается позже
        return None

    # ──────────────────────────────────────────
    # Step 4: Entities → GraphEntity
    # ──────────────────────────────────────────

    def _extract_and_create_entities(self, node_texts: List[Dict]) -> int:
        """Извлечь сущности и сохранить в БД."""
        created = 0

        for node_info in node_texts:
            entities = self.entity_extractor.extract(node_info['text'])

            for ent in entities:
                self.repo.entities.create(
                    node_id=node_info['node_id'],
                    entity_type=ent.entity_type,
                    entity_value=ent.entity_value,
                    raw_text=ent.raw_text,
                    norm_code=ent.norm_code,
                    norm_article=ent.norm_article,
                    amount=ent.amount,
                    currency=ent.currency,
                    date_value=ent.date_value,
                    date_type=ent.date_type,
                    extracted_by=ent.extracted_by,
                    confidence=ent.confidence,
                )
                created += 1

        return created

    # ──────────────────────────────────────────
    # Helpers
    # ──────────────────────────────────────────

    def _get_parser(self, layer: str):
        """Получить парсер по типу слоя."""
        if layer == LayerType.NPA or layer == 'npa':
            return self.npa_parser
        return self.contract_parser
