# -*- coding: utf-8 -*-
"""
Graph Builder

Сохраняет ParseResult (дерево ParsedNode) в БД как GraphDocument + GraphNode + GraphEdge.
Автоматически создаёт structural edges: parent_child, adjacent_to, contains.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional, List, Dict

from sqlalchemy.orm import Session

from .base_parser import ParseResult, ParsedNode
from ..models import GraphDocument, GraphNode, GraphEdge
from ..repository import GraphRepository
from ..enums import (
    EdgeType, EdgeClass, EdgeStatus, ExtractedBy,
    AuditAction, DocumentStatus,
)


class GraphBuilder:
    """
    Строит граф в БД из результата парсинга.

    Использование:
        parser = ContractGraphParser()
        result = parser.parse_file("contract.docx")

        builder = GraphBuilder(db)
        document = builder.build(result, source_file="contract.docx")
        builder.commit()
    """

    def __init__(self, db: Session):
        self.db = db
        self.repo = GraphRepository(db)

    def build(
        self,
        parse_result: ParseResult,
        source_file: Optional[str] = None,
        contract_id: Optional[str] = None,
        legal_document_id: Optional[str] = None,
    ) -> GraphDocument:
        """
        Сохранить дерево в БД.

        Args:
            parse_result: Результат парсинга
            source_file: Путь к исходному файлу
            contract_id: ID существующего Contract (если связываем)
            legal_document_id: ID существующего LegalDocument (если связываем)

        Returns:
            Созданный GraphDocument
        """
        # 1. Создаём GraphDocument
        doc = self.repo.documents.create(
            layer=parse_result.layer.value,
            title=parse_result.title,
            document_date=self._parse_date(parse_result.document_date),
            edition_date=self._parse_date(parse_result.edition_date),
            document_type=parse_result.document_type,
            source_file=source_file,
            source_format=parse_result.source_format,
            parse_status=parse_result.parse_status.value,
            parse_errors=parse_result.parse_errors or None,
            status=DocumentStatus.ACTIVE.value,
            contract_id=contract_id,
            legal_document_id=legal_document_id,
        )

        # 2. Рекурсивно сохраняем дерево узлов
        node_map: Dict[int, GraphNode] = {}  # id(ParsedNode) → GraphNode
        self._save_node_tree(doc, parse_result.root, parent_id=None, node_map=node_map)

        # 3. Создаём structural edges
        self._create_structural_edges(parse_result.root, node_map)

        # 4. Обновляем статистику документа
        self.repo.documents.update_stats(doc.id)

        return doc

    def commit(self):
        """Зафиксировать транзакцию."""
        self.repo.commit()

    def _save_node_tree(
        self,
        doc: GraphDocument,
        parsed_node: ParsedNode,
        parent_id: Optional[str],
        node_map: Dict[int, GraphNode],
    ) -> GraphNode:
        """Рекурсивно сохранить дерево ParsedNode → GraphNode."""
        db_node = self.repo.nodes.create(
            actor="parser",
            document_id=doc.id,
            layer=doc.layer,
            node_type=parsed_node.node_type.value,
            title=parsed_node.title,
            number=parsed_node.number,
            text=parsed_node.text,
            parent_id=parent_id,
            level=parsed_node.level,
            position=parsed_node.position,
            meta_info=parsed_node.metadata or None,
        )

        node_map[id(parsed_node)] = db_node

        # Рекурсия по дочерним
        for child in parsed_node.children:
            self._save_node_tree(doc, child, parent_id=db_node.id, node_map=node_map)

        return db_node

    def _create_structural_edges(
        self,
        root: ParsedNode,
        node_map: Dict[int, GraphNode],
    ):
        """
        Создание structural edges для всего дерева:
        - parent_child: между родителем и дочерним
        - adjacent_to: между соседними узлами (одного родителя)
        - contains: от document/section к вложенным элементам
        """
        self._create_edges_recursive(root, node_map)

    def _create_edges_recursive(
        self,
        parsed_node: ParsedNode,
        node_map: Dict[int, GraphNode],
    ):
        """Рекурсивное создание structural edges."""
        db_node = node_map.get(id(parsed_node))
        if not db_node:
            return

        children = parsed_node.children
        prev_child_db: Optional[GraphNode] = None

        for child in children:
            child_db = node_map.get(id(child))
            if not child_db:
                continue

            # parent_child edge
            self.repo.edges.create(
                actor="parser",
                source_id=db_node.id,
                target_id=child_db.id,
                edge_type=EdgeType.PARENT_CHILD.value,
                edge_class=EdgeClass.STRUCTURAL.value,
                status=EdgeStatus.VERIFIED.value,
                extracted_by=ExtractedBy.PARSER.value,
                confidence=1.0,
            )

            # adjacent_to edge (между соседними)
            if prev_child_db is not None:
                self.repo.edges.create(
                    actor="parser",
                    source_id=prev_child_db.id,
                    target_id=child_db.id,
                    edge_type=EdgeType.ADJACENT_TO.value,
                    edge_class=EdgeClass.STRUCTURAL.value,
                    status=EdgeStatus.VERIFIED.value,
                    extracted_by=ExtractedBy.PARSER.value,
                    confidence=1.0,
                )

            prev_child_db = child_db

            # Рекурсия
            self._create_edges_recursive(child, node_map)

        # contains edge: section/document содержит все дочерние
        if db_node.node_type in ('document', 'section', 'chapter', 'title', 'article') and children:
            for child in children:
                child_db = node_map.get(id(child))
                if child_db:
                    self.repo.edges.create(
                        actor="parser",
                        source_id=db_node.id,
                        target_id=child_db.id,
                        edge_type=EdgeType.CONTAINS.value,
                        edge_class=EdgeClass.STRUCTURAL.value,
                        status=EdgeStatus.VERIFIED.value,
                        extracted_by=ExtractedBy.PARSER.value,
                        confidence=1.0,
                    )

    @staticmethod
    def _parse_date(date_str: Optional[str]) -> Optional[datetime]:
        """Попытка парсинга даты из строки."""
        if not date_str:
            return None
        for fmt in ('%d.%m.%Y', '%Y-%m-%d', '%d/%m/%Y'):
            try:
                return datetime.strptime(date_str, fmt).replace(tzinfo=timezone.utc)
            except ValueError:
                continue
        return None
