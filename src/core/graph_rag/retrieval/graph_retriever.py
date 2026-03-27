# -*- coding: utf-8 -*-
"""
Graph Retriever

Hybrid search по графу документов:
  1. Exact match — поиск по номеру пункта/статьи
  2. Text search — LIKE/ILIKE по тексту узлов (BM25-заменитель для MVP)
  3. Vector search — через существующий RAGSystem (ChromaDB)
  4. Entity search — по нормализованным сущностям (norm_ref, monetary, date_ref)

Возвращает ранжированный список GraphNode с метаданными.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any, Set

from sqlalchemy import func, or_, and_
from sqlalchemy.orm import Session

from ..models import GraphDocument, GraphNode, GraphEdge, GraphEntity
from ..repository import GraphRepository
from ..enums import LayerType, NodeType, EdgeType, EdgeClass

logger = logging.getLogger(__name__)


@dataclass
class RetrievedNode:
    """Результат поиска: узел графа + метаданные релевантности."""
    node: GraphNode
    score: float = 0.0
    match_type: str = "text"        # exact, text, vector, entity, graph_expand
    highlight: Optional[str] = None  # Фрагмент текста с найденным совпадением
    depth: int = 0                   # Глубина при graph expansion (0 = прямой hit)

    @property
    def node_id(self) -> str:
        return self.node.id

    @property
    def document_id(self) -> str:
        return self.node.document_id


@dataclass
class RetrievalQuery:
    """Параметры поискового запроса."""
    text: str                                   # Текст запроса
    document_ids: Optional[List[str]] = None    # Ограничение по документам
    layers: Optional[List[str]] = None          # contract, npa
    node_types: Optional[List[str]] = None      # clause, article, section...
    norm_code: Optional[str] = None             # Поиск по коду НПА (ГК РФ)
    article: Optional[str] = None               # Поиск по статье
    clause_number: Optional[str] = None         # Поиск по номеру пункта
    entity_type: Optional[str] = None           # Фильтр по типу сущности
    top_k: int = 10                             # Максимум результатов
    expand_graph: bool = True                   # Расширять контекст по графу
    expand_depth: int = 1                       # Глубина расширения


# ──────────────────────────────────────────────
# Regex для определения типа запроса
# ──────────────────────────────────────────────

RE_CLAUSE_QUERY = re.compile(r'(?:п(?:ункт)?\.?\s*)(\d+(?:\.\d+)+)', re.IGNORECASE)
RE_ARTICLE_QUERY = re.compile(r'(?:ст(?:атья|\.)?\.?\s*)(\d+(?:\.\d+)?)', re.IGNORECASE)
RE_NPA_QUERY = re.compile(r'(ГК|ТК|НК|ЗК|АПК|ГПК|БК|ЖК|СК|УК|КоАП)\s*РФ', re.IGNORECASE)


class GraphRetriever:
    """
    Hybrid retriever по графу документов.

    Использование:
        retriever = GraphRetriever(db)
        results = retriever.search(RetrievalQuery(
            text="неустойка по ст. 330 ГК РФ",
            layers=["contract"],
        ))
    """

    def __init__(self, db: Session, rag_system=None):
        """
        Args:
            db: SQLAlchemy Session
            rag_system: Опциональный RAGSystem для vector search
        """
        self.db = db
        self.repo = GraphRepository(db)
        self.rag_system = rag_system

    def search(self, query: RetrievalQuery) -> List[RetrievedNode]:
        """
        Комбинированный поиск по графу.

        Порядок:
        1. Exact match (номер пункта/статьи) — score 1.0
        2. Entity search (нормы, суммы) — score 0.9
        3. Text search (LIKE) — score 0.5-0.8
        4. Vector search (ChromaDB) — score по cosine similarity

        Результаты дедуплицируются и ранжируются.
        """
        results: List[RetrievedNode] = []

        # 1. Exact match
        exact = self._exact_search(query)
        results.extend(exact)

        # 2. Entity search
        if query.norm_code or query.entity_type:
            entity_results = self._entity_search(query)
            results.extend(entity_results)
        else:
            # Auto-detect norm references in query
            auto_entity = self._auto_entity_search(query.text, query.document_ids)
            results.extend(auto_entity)

        # 3. Text search
        text_results = self._text_search(query)
        results.extend(text_results)

        # 4. Vector search (if available)
        if self.rag_system:
            vector_results = self._vector_search(query)
            results.extend(vector_results)

        # Deduplicate and rank
        results = self._deduplicate_and_rank(results, query.top_k)

        return results

    # ──────────────────────────────────────────
    # 1. Exact match
    # ──────────────────────────────────────────

    def _exact_search(self, query: RetrievalQuery) -> List[RetrievedNode]:
        """Точный поиск по номеру пункта/статьи."""
        results = []

        # Из параметров запроса
        if query.clause_number:
            results.extend(self._find_by_number(query.clause_number, query.document_ids))

        if query.article:
            results.extend(self._find_by_number(query.article, query.document_ids, layers=['npa']))

        # Авто-детект из текста запроса
        for m in RE_CLAUSE_QUERY.finditer(query.text):
            clause_num = m.group(1)
            results.extend(self._find_by_number(clause_num, query.document_ids))

        for m in RE_ARTICLE_QUERY.finditer(query.text):
            article_num = m.group(1)
            results.extend(self._find_by_number(article_num, query.document_ids, layers=['npa']))

        return results

    def _find_by_number(
        self,
        number: str,
        document_ids: Optional[List[str]] = None,
        layers: Optional[List[str]] = None,
    ) -> List[RetrievedNode]:
        """Найти узлы по номеру."""
        q = (self.db.query(GraphNode)
             .filter(GraphNode.number == number, GraphNode.is_archived == False))

        if document_ids:
            q = q.filter(GraphNode.document_id.in_(document_ids))
        if layers:
            q = q.filter(GraphNode.layer.in_(layers))

        nodes = q.limit(5).all()
        return [
            RetrievedNode(node=n, score=1.0, match_type="exact")
            for n in nodes
        ]

    # ──────────────────────────────────────────
    # 2. Entity search
    # ──────────────────────────────────────────

    def _entity_search(self, query: RetrievalQuery) -> List[RetrievedNode]:
        """Поиск по нормализованным сущностям."""
        results = []

        q = self.db.query(GraphEntity)

        if query.norm_code:
            q = q.filter(GraphEntity.norm_code.ilike(f"%{query.norm_code}%"))
        if query.article:
            q = q.filter(GraphEntity.norm_article == query.article)
        if query.entity_type:
            q = q.filter(GraphEntity.entity_type == query.entity_type)

        entities = q.limit(query.top_k * 2).all()

        # Получаем узлы
        node_ids = list(set(e.node_id for e in entities))
        if node_ids:
            nodes = (self.db.query(GraphNode)
                     .filter(GraphNode.id.in_(node_ids), GraphNode.is_archived == False))
            if query.document_ids:
                nodes = nodes.filter(GraphNode.document_id.in_(query.document_ids))
            nodes = nodes.all()

            node_map = {n.id: n for n in nodes}
            for e in entities:
                node = node_map.get(e.node_id)
                if node:
                    results.append(RetrievedNode(
                        node=node, score=0.9, match_type="entity",
                        highlight=f"{e.entity_type}: {e.entity_value}",
                    ))

        return results

    def _auto_entity_search(
        self,
        text: str,
        document_ids: Optional[List[str]] = None,
    ) -> List[RetrievedNode]:
        """Автоматический поиск по сущностям из текста запроса."""
        results = []

        # Ищем упоминания кодексов
        npa_match = RE_NPA_QUERY.search(text)
        article_match = RE_ARTICLE_QUERY.search(text)

        if npa_match:
            norm_code = f"{npa_match.group(1)} РФ"
            article = article_match.group(1) if article_match else None

            q = self.db.query(GraphEntity).filter(
                GraphEntity.entity_type == 'norm_ref',
                GraphEntity.norm_code.ilike(f"%{norm_code}%"),
            )
            if article:
                q = q.filter(GraphEntity.norm_article == article)

            entities = q.limit(10).all()
            node_ids = list(set(e.node_id for e in entities))

            if node_ids:
                nodes_q = (self.db.query(GraphNode)
                           .filter(GraphNode.id.in_(node_ids), GraphNode.is_archived == False))
                if document_ids:
                    nodes_q = nodes_q.filter(GraphNode.document_id.in_(document_ids))
                nodes = nodes_q.all()

                node_map = {n.id: n for n in nodes}
                for e in entities:
                    node = node_map.get(e.node_id)
                    if node:
                        results.append(RetrievedNode(
                            node=node, score=0.85, match_type="entity",
                            highlight=f"Ссылка на {e.entity_value}",
                        ))

        return results

    # ──────────────────────────────────────────
    # 3. Text search
    # ──────────────────────────────────────────

    def _text_search(self, query: RetrievalQuery) -> List[RetrievedNode]:
        """Полнотекстовый поиск (LIKE для MVP, можно заменить на FTS)."""
        # Разбиваем запрос на ключевые слова (>= 3 символов)
        words = [w for w in query.text.split() if len(w) >= 3]
        if not words:
            return []

        q = self.db.query(GraphNode).filter(GraphNode.is_archived == False)

        if query.document_ids:
            q = q.filter(GraphNode.document_id.in_(query.document_ids))
        if query.layers:
            q = q.filter(GraphNode.layer.in_(query.layers))
        if query.node_types:
            q = q.filter(GraphNode.node_type.in_(query.node_types))

        # Ищем узлы, содержащие хотя бы одно ключевое слово
        word_filters = [GraphNode.text.ilike(f"%{w}%") for w in words]
        q = q.filter(or_(*word_filters))

        nodes = q.limit(query.top_k * 3).all()

        # Ранжируем по количеству совпавших слов
        results = []
        for node in nodes:
            text_lower = node.text.lower()
            matched = sum(1 for w in words if w.lower() in text_lower)
            score = 0.5 + (0.3 * matched / len(words))  # 0.5-0.8

            # Формируем highlight
            highlight = node.text[:150]
            if len(node.text) > 150:
                highlight += "..."

            results.append(RetrievedNode(
                node=node, score=score, match_type="text",
                highlight=highlight,
            ))

        return results

    # ──────────────────────────────────────────
    # 4. Vector search
    # ──────────────────────────────────────────

    def _vector_search(self, query: RetrievalQuery) -> List[RetrievedNode]:
        """Vector search через существующий RAGSystem."""
        if not self.rag_system:
            return []

        try:
            docs = self.rag_system.search(
                query=query.text,
                top_k=query.top_k,
            )
        except Exception as e:
            logger.warning(f"Vector search failed: {e}")
            return []

        results = []
        for doc in docs:
            # Пытаемся найти соответствующий GraphNode
            node_id = doc.metadata.get('graph_node_id')
            if node_id:
                node = self.repo.nodes.get_by_id(node_id)
                if node:
                    results.append(RetrievedNode(
                        node=node,
                        score=doc.score * 0.9,  # Масштабируем к общему рейтингу
                        match_type="vector",
                        highlight=doc.content[:150],
                    ))

        return results

    # ──────────────────────────────────────────
    # Deduplication and ranking
    # ──────────────────────────────────────────

    def _deduplicate_and_rank(
        self,
        results: List[RetrievedNode],
        top_k: int,
    ) -> List[RetrievedNode]:
        """Дедупликация по node_id, оставляя максимальный score."""
        seen: Dict[str, RetrievedNode] = {}

        for r in results:
            nid = r.node_id
            if nid not in seen or r.score > seen[nid].score:
                seen[nid] = r

        ranked = sorted(seen.values(), key=lambda r: r.score, reverse=True)
        return ranked[:top_k]
