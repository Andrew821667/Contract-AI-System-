# -*- coding: utf-8 -*-
"""
Graph Expander

Расширение контекста вокруг найденных узлов по рёбрам графа.
Берёт результаты поиска (RetrievedNode) и обогащает их
структурным контекстом: предки, потомки, связанные узлы.

Это ключевое преимущество Graph-RAG над flat RAG:
  - Flat RAG: нашёл чанк "Неустойка 0.1%..." — и всё
  - Graph-RAG: + родительский раздел "Ответственность" + связанные пункты
    + ссылка на ст. 330 ГК РФ + определение термина из преамбулы
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Set

from sqlalchemy.orm import Session

from ..models import GraphNode, GraphEdge
from ..repository import GraphRepository
from ..enums import EdgeType, EdgeClass, EdgeStatus
from .graph_retriever import RetrievedNode

logger = logging.getLogger(__name__)


@dataclass
class ExpandedContext:
    """Расширенный контекст для одного найденного узла."""
    primary_node: RetrievedNode         # Исходный найденный узел
    ancestors: List[GraphNode] = field(default_factory=list)     # Предки (до корня)
    siblings: List[GraphNode] = field(default_factory=list)      # Соседние пункты
    children: List[GraphNode] = field(default_factory=list)      # Дочерние узлы
    referenced_nodes: List[GraphNode] = field(default_factory=list)  # Связанные через fact edges
    referenced_by: List[GraphNode] = field(default_factory=list)     # Кто ссылается на этот узел
    entities_summary: List[str] = field(default_factory=list)    # Сводка сущностей

    @property
    def all_context_nodes(self) -> List[GraphNode]:
        """Все узлы контекста (без дублей)."""
        seen: Set[str] = set()
        result = []
        for node in (self.ancestors + self.siblings + self.children +
                     self.referenced_nodes + self.referenced_by):
            if node.id not in seen:
                seen.add(node.id)
                result.append(node)
        return result


class GraphExpander:
    """
    Расширяет контекст вокруг найденных узлов.

    Стратегии расширения:
    1. Structural: предки + дочерние (по parent_child)
    2. Fact: связанные через references, regulated_by, defined_in
    3. Sibling: соседние пункты того же раздела

    Использование:
        expander = GraphExpander(db)
        contexts = expander.expand(search_results, depth=1)
    """

    def __init__(self, db: Session):
        self.db = db
        self.repo = GraphRepository(db)

    def expand(
        self,
        results: List[RetrievedNode],
        depth: int = 1,
        include_siblings: bool = True,
        include_children: bool = True,
        max_children: int = 10,
        max_siblings: int = 5,
    ) -> List[ExpandedContext]:
        """
        Расширить контекст для каждого найденного узла.

        Args:
            results: Результаты поиска
            depth: Глубина расширения по рёбрам
            include_siblings: Включать соседние пункты
            include_children: Включать дочерние узлы
            max_children: Максимум дочерних узлов
            max_siblings: Максимум соседних узлов

        Returns:
            Список ExpandedContext для каждого найденного узла
        """
        contexts = []

        for result in results:
            ctx = self._expand_single(
                result,
                depth=depth,
                include_siblings=include_siblings,
                include_children=include_children,
                max_children=max_children,
                max_siblings=max_siblings,
            )
            contexts.append(ctx)

        return contexts

    def _expand_single(
        self,
        result: RetrievedNode,
        depth: int,
        include_siblings: bool,
        include_children: bool,
        max_children: int,
        max_siblings: int,
    ) -> ExpandedContext:
        """Расширить контекст одного узла."""
        node = result.node
        ctx = ExpandedContext(primary_node=result)

        # 1. Ancestors (всегда — даёт структурный контекст)
        ctx.ancestors = self.repo.nodes.get_ancestors(node.id, max_depth=5)

        # 2. Children (опционально)
        if include_children:
            children = self.repo.nodes.get_children(node.id)
            ctx.children = children[:max_children]

        # 3. Siblings (опционально)
        if include_siblings:
            siblings = self.repo.nodes.get_siblings(node.id)
            ctx.siblings = siblings[:max_siblings]

        # 4. Fact edges — referenced nodes
        ctx.referenced_nodes = self._get_referenced_nodes(node.id, depth)

        # 5. Reverse fact edges — who references this node
        ctx.referenced_by = self._get_referencing_nodes(node.id)

        # 6. Entities summary
        entities = self.repo.entities.get_by_node(node.id)
        ctx.entities_summary = [
            f"{e.entity_type}: {e.entity_value}" for e in entities
        ]

        return ctx

    def _get_referenced_nodes(self, node_id: str, depth: int) -> List[GraphNode]:
        """Получить узлы, на которые ссылается данный узел через fact edges."""
        fact_edge_types = [
            EdgeType.REFERENCES.value,
            EdgeType.REGULATED_BY.value,
            EdgeType.DEFINED_IN.value,
            EdgeType.APPENDIX_REF.value,
            EdgeType.TABLE_REF.value,
            EdgeType.AMENDS.value,
            EdgeType.SUPERSEDES.value,
        ]

        edges = self.repo.edges.get_outgoing(
            node_id,
            edge_types=fact_edge_types,
            edge_classes=[EdgeClass.FACT.value],
        )

        target_ids = [e.target_id for e in edges if e.target_id != node_id]
        if not target_ids:
            return []

        nodes = (self.db.query(GraphNode)
                 .filter(GraphNode.id.in_(target_ids), GraphNode.is_archived == False)
                 .all())
        return nodes

    def _get_referencing_nodes(self, node_id: str) -> List[GraphNode]:
        """Получить узлы, которые ссылаются на данный узел."""
        fact_edge_types = [
            EdgeType.REFERENCES.value,
            EdgeType.REGULATED_BY.value,
        ]

        edges = self.repo.edges.get_incoming(
            node_id,
            edge_types=fact_edge_types,
            edge_classes=[EdgeClass.FACT.value],
        )

        source_ids = [e.source_id for e in edges if e.source_id != node_id]
        if not source_ids:
            return []

        nodes = (self.db.query(GraphNode)
                 .filter(GraphNode.id.in_(source_ids), GraphNode.is_archived == False)
                 .limit(10)
                 .all())
        return nodes
