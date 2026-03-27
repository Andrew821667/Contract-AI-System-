# -*- coding: utf-8 -*-
"""
Graph-RAG Read Tools

Инструменты чтения графа для AI-агента:
- graph_search — поиск по графу (hybrid: exact + text + entity + vector)
- graph_get_node — получить узел по ID с контекстом
- graph_get_document — получить документ с деревом
- graph_ask — RAG-запрос: поиск + контекст + answer policy
"""
from __future__ import annotations

import logging
from typing import Any, Optional, List, Dict

from sqlalchemy.orm import Session

from ..repository import GraphRepository
from ..retrieval import GraphRetriever, RetrievalQuery, GraphExpander
from ..context import ContextBuilder, AnswerPolicy

logger = logging.getLogger(__name__)


class GraphReadTools:
    """
    Read-only tools для работы с графом.
    Используются агентом для поиска и чтения информации.
    """

    def __init__(self, db: Session, rag_system=None):
        self.db = db
        self.repo = GraphRepository(db)
        self.retriever = GraphRetriever(db, rag_system=rag_system)
        self.expander = GraphExpander(db)
        self.context_builder = ContextBuilder()

    def search(
        self,
        query: str,
        document_ids: Optional[List[str]] = None,
        layers: Optional[List[str]] = None,
        top_k: int = 5,
    ) -> Dict[str, Any]:
        """
        Поиск по графу документов.

        Args:
            query: Текст запроса (например, «неустойка по ст. 330 ГК РФ»)
            document_ids: Ограничить поиск конкретными документами
            layers: Ограничить по слоям (contract, npa)
            top_k: Количество результатов

        Returns:
            {results: [{node_id, number, type, text, score, match_type}], count}
        """
        retrieval_query = RetrievalQuery(
            text=query,
            document_ids=document_ids,
            layers=layers,
            top_k=top_k,
        )

        results = self.retriever.search(retrieval_query)

        return {
            "results": [
                {
                    "node_id": r.node_id,
                    "document_id": r.document_id,
                    "number": r.node.number,
                    "node_type": r.node.node_type,
                    "title": r.node.title,
                    "text": r.node.text[:300],
                    "score": round(r.score, 3),
                    "match_type": r.match_type,
                }
                for r in results
            ],
            "count": len(results),
            "query": query,
        }

    def get_node(
        self,
        node_id: str,
        include_context: bool = True,
    ) -> Optional[Dict[str, Any]]:
        """
        Получить узел графа по ID с контекстом.

        Args:
            node_id: ID узла
            include_context: Включить предков, детей, связи

        Returns:
            Полная информация об узле или None
        """
        node = self.repo.nodes.get_by_id(node_id)
        if not node:
            return None

        result = {
            "node_id": node.id,
            "document_id": node.document_id,
            "node_type": node.node_type,
            "number": node.number,
            "title": node.title,
            "text": node.text,
            "level": node.level,
        }

        if include_context:
            # Предки
            ancestors = self.repo.nodes.get_ancestors(node_id)
            result["path"] = [
                {"node_id": a.id, "type": a.node_type, "number": a.number, "title": a.title}
                for a in ancestors
            ]

            # Дети
            children = self.repo.nodes.get_children(node_id)
            result["children"] = [
                {"node_id": c.id, "type": c.node_type, "number": c.number,
                 "text": c.text[:100]}
                for c in children
            ]

            # Сущности
            entities = self.repo.entities.get_by_node(node_id)
            result["entities"] = [
                {"type": e.entity_type, "value": e.entity_value}
                for e in entities
            ]

            # Связи (fact edges)
            outgoing = self.repo.edges.get_outgoing(node_id, edge_classes=["fact"])
            result["references"] = [
                {"target_id": e.target_id, "edge_type": e.edge_type, "evidence": e.evidence}
                for e in outgoing
            ]

        return result

    def get_document(
        self,
        document_id: str,
        max_depth: int = 2,
    ) -> Optional[Dict[str, Any]]:
        """
        Получить документ с деревом узлов.

        Args:
            document_id: ID документа в графе
            max_depth: Максимальная глубина дерева

        Returns:
            {document: {...}, tree: [{...}]}
        """
        doc = self.repo.documents.get_by_id(document_id)
        if not doc:
            return None

        nodes = self.repo.nodes.get_by_document(document_id)

        # Строим дерево
        root_nodes = [n for n in nodes if n.parent_id is None]

        def build_tree(node, depth=0):
            item = {
                "node_id": node.id,
                "type": node.node_type,
                "number": node.number,
                "title": node.title,
                "text_preview": node.text[:100] if node.text else "",
            }
            if depth < max_depth:
                children = [n for n in nodes if n.parent_id == node.id]
                children.sort(key=lambda n: n.position)
                if children:
                    item["children"] = [build_tree(c, depth + 1) for c in children]
            return item

        return {
            "document": {
                "id": doc.id,
                "title": doc.title,
                "layer": doc.layer,
                "document_type": doc.document_type,
                "status": doc.status,
                "nodes_count": doc.nodes_count,
                "edges_count": doc.edges_count,
            },
            "tree": [build_tree(r) for r in root_nodes],
        }

    def ask(
        self,
        query: str,
        document_ids: Optional[List[str]] = None,
        layers: Optional[List[str]] = None,
        top_k: int = 5,
        max_context_chars: int = 8000,
    ) -> Dict[str, Any]:
        """
        RAG-запрос: поиск → расширение → контекст → policy.

        Это основной метод для агента.
        Возвращает всё необходимое для формирования ответа LLM.

        Args:
            query: Вопрос пользователя
            document_ids: Ограничить по документам
            layers: Ограничить по слоям
            top_k: Количество результатов поиска
            max_context_chars: Бюджет контекста

        Returns:
            {context_text, system_prompt, sources, confidence, metadata}
        """
        # 1. Search
        retrieval_query = RetrievalQuery(
            text=query,
            document_ids=document_ids,
            layers=layers,
            top_k=top_k,
            expand_graph=True,
        )
        search_results = self.retriever.search(retrieval_query)

        if not search_results:
            policy = AnswerPolicy()
            policy.confidence = policy.confidence.__class__("no_data")
            return {
                "context_text": "",
                "system_prompt": "В документах не найдено информации по запросу.",
                "sources": [],
                "confidence": "no_data",
                "metadata": {"has_direct_answer": False, "sources_count": 0},
            }

        # 2. Expand
        expanded = self.expander.expand(search_results)

        # 3. Build context
        self.context_builder.max_chars = max_context_chars
        assembled = self.context_builder.build(expanded, query=query)

        # 4. Answer policy
        policy = AnswerPolicy.from_context(assembled, query=query)

        return {
            "context_text": assembled.to_prompt_text(),
            "system_prompt": policy.to_system_prompt(),
            "sources": assembled.sources,
            "confidence": policy.confidence.value,
            "metadata": policy.to_metadata(),
        }

    def list_documents(
        self,
        layer: Optional[str] = None,
        limit: int = 20,
    ) -> Dict[str, Any]:
        """Список документов в графе."""
        docs = self.repo.documents.get_active(layer=layer, limit=limit)
        return {
            "documents": [
                {
                    "id": d.id,
                    "title": d.title,
                    "layer": d.layer,
                    "document_type": d.document_type,
                    "nodes_count": d.nodes_count,
                    "edges_count": d.edges_count,
                    "created_at": d.created_at.isoformat() if d.created_at else None,
                }
                for d in docs
            ],
            "count": len(docs),
        }
