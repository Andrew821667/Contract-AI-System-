# -*- coding: utf-8 -*-
"""
Graph-RAG Analyze Tools

Аналитические инструменты для AI-агента:
- graph_stats — статистика документа/графа
- graph_compare — сравнить два узла/документа
- graph_find_references — найти все ссылки на НПА в документе
- graph_entity_summary — сводка сущностей документа (суммы, даты, нормы)
"""
from __future__ import annotations

import logging
from collections import Counter
from typing import Any, Optional, List, Dict

from sqlalchemy import func
from sqlalchemy.orm import Session

from ..models import GraphDocument, GraphNode, GraphEdge, GraphEntity, CandidateEdge
from ..repository import GraphRepository

logger = logging.getLogger(__name__)


class GraphAnalyzeTools:
    """
    Аналитические tools для графа.
    Read-only: не изменяют данные.
    """

    def __init__(self, db: Session):
        self.db = db
        self.repo = GraphRepository(db)

    def stats(self, document_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Статистика графа или конкретного документа.

        Returns:
            {documents, nodes_total, edges_total, entities_total, by_layer, by_node_type}
        """
        if document_id:
            return self._document_stats(document_id)
        return self._global_stats()

    def entity_summary(
        self,
        document_id: str,
    ) -> Dict[str, Any]:
        """
        Сводка сущностей документа: суммы, даты, ссылки на нормы.

        Returns:
            {monetary: [...], dates: [...], norm_refs: [...], clause_types: [...]}
        """
        nodes = self.repo.nodes.get_by_document(document_id)
        node_ids = [n.id for n in nodes]

        if not node_ids:
            return {"error": "Document not found or empty"}

        entities = (self.db.query(GraphEntity)
                    .filter(GraphEntity.node_id.in_(node_ids))
                    .all())

        result = {
            "monetary": [],
            "dates": [],
            "norm_refs": [],
            "clause_types": [],
            "contract_types": [],
        }

        for e in entities:
            entry = {
                "value": e.entity_value,
                "raw_text": e.raw_text,
                "node_id": e.node_id,
                "confidence": e.confidence,
            }

            if e.entity_type == 'monetary':
                entry["amount"] = e.amount
                entry["currency"] = e.currency
                result["monetary"].append(entry)
            elif e.entity_type == 'date_ref':
                entry["date"] = e.date_value.isoformat() if e.date_value else None
                entry["date_type"] = e.date_type
                result["dates"].append(entry)
            elif e.entity_type == 'norm_ref':
                entry["norm_code"] = e.norm_code
                entry["article"] = e.norm_article
                result["norm_refs"].append(entry)
            elif e.entity_type == 'clause_type':
                result["clause_types"].append(entry)
            elif e.entity_type == 'contract_type':
                result["contract_types"].append(entry)

        return result

    def find_norm_references(
        self,
        document_id: str,
        norm_code: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Найти все ссылки на НПА в документе.

        Args:
            document_id: ID документа
            norm_code: Фильтр по коду НПА (например, "ГК РФ")
        """
        nodes = self.repo.nodes.get_by_document(document_id)
        node_ids = [n.id for n in nodes]
        node_map = {n.id: n for n in nodes}

        q = (self.db.query(GraphEntity)
             .filter(
                 GraphEntity.node_id.in_(node_ids),
                 GraphEntity.entity_type == 'norm_ref',
             ))

        if norm_code:
            q = q.filter(GraphEntity.norm_code.ilike(f"%{norm_code}%"))

        entities = q.all()

        references = []
        for e in entities:
            node = node_map.get(e.node_id)
            references.append({
                "norm_code": e.norm_code,
                "article": e.norm_article,
                "part": e.norm_part,
                "raw_text": e.raw_text,
                "node_number": node.number if node else None,
                "node_text_preview": node.text[:100] if node else None,
            })

        # Группировка по НПА
        by_npa = Counter(e.norm_code for e in entities if e.norm_code)

        return {
            "references": references,
            "count": len(references),
            "by_npa": dict(by_npa.most_common()),
        }

    def pending_reviews(self, limit: int = 20) -> Dict[str, Any]:
        """Список кандидатов, ожидающих ревью."""
        candidates = self.repo.candidates.get_pending(limit=limit)

        return {
            "candidates": [
                {
                    "id": c.id,
                    "source_id": c.source_id,
                    "target_id": c.target_id,
                    "proposed_type": c.proposed_type,
                    "proposed_class": c.proposed_class,
                    "rationale": c.rationale,
                    "confidence": c.confidence,
                    "created_at": c.created_at.isoformat() if c.created_at else None,
                }
                for c in candidates
            ],
            "count": len(candidates),
        }

    def compare_nodes(
        self,
        node_id_a: str,
        node_id_b: str,
    ) -> Optional[Dict[str, Any]]:
        """
        Сравнить два узла: текст, сущности, ссылки.
        Полезно для сравнения пунктов из разных договоров.
        """
        node_a = self.repo.nodes.get_by_id(node_id_a)
        node_b = self.repo.nodes.get_by_id(node_id_b)

        if not node_a or not node_b:
            return None

        entities_a = self.repo.entities.get_by_node(node_id_a)
        entities_b = self.repo.entities.get_by_node(node_id_b)

        return {
            "node_a": {
                "id": node_a.id,
                "number": node_a.number,
                "type": node_a.node_type,
                "text": node_a.text,
                "document_id": node_a.document_id,
                "entities": [{"type": e.entity_type, "value": e.entity_value} for e in entities_a],
            },
            "node_b": {
                "id": node_b.id,
                "number": node_b.number,
                "type": node_b.node_type,
                "text": node_b.text,
                "document_id": node_b.document_id,
                "entities": [{"type": e.entity_type, "value": e.entity_value} for e in entities_b],
            },
            "same_type": node_a.node_type == node_b.node_type,
            "same_document": node_a.document_id == node_b.document_id,
        }

    # ──────────────────────────────────────────
    # Private
    # ──────────────────────────────────────────

    def _document_stats(self, document_id: str) -> Dict[str, Any]:
        doc = self.repo.documents.get_by_id(document_id)
        if not doc:
            return {"error": "Document not found"}

        nodes = self.repo.nodes.get_by_document(document_id)
        node_types = Counter(n.node_type for n in nodes)

        node_ids = [n.id for n in nodes]
        entities_count = (self.db.query(func.count(GraphEntity.id))
                          .filter(GraphEntity.node_id.in_(node_ids))
                          .scalar()) if node_ids else 0

        candidates_count = (self.db.query(func.count(CandidateEdge.id))
                            .filter(
                                CandidateEdge.source_id.in_(node_ids),
                                CandidateEdge.reviewed == False,
                            )
                            .scalar()) if node_ids else 0

        return {
            "document_id": doc.id,
            "title": doc.title,
            "layer": doc.layer,
            "status": doc.status,
            "nodes_count": doc.nodes_count,
            "edges_count": doc.edges_count,
            "entities_count": entities_count,
            "pending_candidates": candidates_count,
            "by_node_type": dict(node_types),
        }

    def _global_stats(self) -> Dict[str, Any]:
        docs_count = self.db.query(func.count(GraphDocument.id)).scalar()
        nodes_count = self.db.query(func.count(GraphNode.id)).filter(
            GraphNode.is_archived == False
        ).scalar()
        edges_count = self.db.query(func.count(GraphEdge.id)).scalar()
        entities_count = self.db.query(func.count(GraphEntity.id)).scalar()

        by_layer = dict(
            self.db.query(GraphDocument.layer, func.count(GraphDocument.id))
            .group_by(GraphDocument.layer)
            .all()
        )

        return {
            "documents_total": docs_count,
            "nodes_total": nodes_count,
            "edges_total": edges_count,
            "entities_total": entities_count,
            "by_layer": by_layer,
        }
