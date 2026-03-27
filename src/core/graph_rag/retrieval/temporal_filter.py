# -*- coding: utf-8 -*-
"""
Temporal Filter

Фильтрация узлов и документов по временным критериям:
- Дата документа (подписания, принятия)
- Дата редакции НПА (edition_date)
- Temporal validity рёбер (valid_from / valid_to)
- Версии узлов (NodeVersion.valid_from / valid_to)

ПРИНЦИП: не смешивать редакции. Если запрос про текущую редакцию —
показывать только актуальные версии. Если про историческую — явно
указывать, что это старая версия.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from ..models import GraphDocument, GraphNode, GraphEdge, NodeVersion
from ..enums import DocumentStatus


class TemporalFilter:
    """
    Фильтрация по временным критериям.

    Использование:
        tf = TemporalFilter(db)

        # Только актуальные документы
        docs = tf.filter_active_documents(documents)

        # Версия узла на дату
        version = tf.get_node_version_at(node_id, date)

        # Действующие рёбра
        edges = tf.filter_valid_edges(edges, at_date)
    """

    def __init__(self, db: Session):
        self.db = db

    def filter_active_documents(
        self,
        documents: List[GraphDocument],
        at_date: Optional[datetime] = None,
    ) -> List[GraphDocument]:
        """
        Оставить только активные документы.
        Если at_date задана — только документы, существовавшие на эту дату.
        """
        result = []
        for doc in documents:
            if doc.status != DocumentStatus.ACTIVE:
                continue
            if at_date and doc.created_at and doc.created_at > at_date:
                continue
            result.append(doc)
        return result

    def filter_current_edition(
        self,
        documents: List[GraphDocument],
    ) -> List[GraphDocument]:
        """
        Для НПА: оставить только последнюю редакцию каждого документа.
        Группируем по title, берём с максимальной edition_date.
        """
        by_title = {}
        for doc in documents:
            if doc.layer != 'npa':
                by_title[doc.id] = doc
                continue

            key = doc.title
            existing = by_title.get(key)
            if not existing:
                by_title[key] = doc
            elif doc.edition_date and existing.edition_date:
                if doc.edition_date > existing.edition_date:
                    by_title[key] = doc
            elif doc.edition_date:
                by_title[key] = doc

        return list(by_title.values())

    def get_node_version_at(
        self,
        node_id: str,
        at_date: datetime,
    ) -> Optional[NodeVersion]:
        """
        Получить версию узла, действовавшую на указанную дату.
        valid_from <= at_date AND (valid_to IS NULL OR valid_to > at_date)
        """
        version = (self.db.query(NodeVersion)
                    .filter(
                        NodeVersion.node_id == node_id,
                        NodeVersion.valid_from <= at_date,
                        or_(
                            NodeVersion.valid_to == None,
                            NodeVersion.valid_to > at_date,
                        ),
                    )
                    .order_by(NodeVersion.version_number.desc())
                    .first())
        return version

    def get_current_version(self, node_id: str) -> Optional[NodeVersion]:
        """Получить текущую (действующую) версию узла."""
        return (self.db.query(NodeVersion)
                .filter(
                    NodeVersion.node_id == node_id,
                    NodeVersion.valid_to == None,
                )
                .first())

    def filter_valid_edges(
        self,
        edges: List[GraphEdge],
        at_date: Optional[datetime] = None,
    ) -> List[GraphEdge]:
        """
        Оставить только действующие рёбра.
        Ребро действует если:
        - valid_from IS NULL OR valid_from <= at_date
        - valid_to IS NULL OR valid_to > at_date
        - status != 'deprecated'
        """
        if at_date is None:
            at_date = datetime.now(timezone.utc)

        result = []
        for edge in edges:
            if edge.status == 'deprecated':
                continue
            if edge.valid_from and edge.valid_from > at_date:
                continue
            if edge.valid_to and edge.valid_to <= at_date:
                continue
            result.append(edge)
        return result

    def annotate_temporal_status(
        self,
        node: GraphNode,
    ) -> dict:
        """
        Аннотировать узел временным статусом для контекста.
        Возвращает метаданные о версионности.
        """
        versions = (self.db.query(NodeVersion)
                     .filter(NodeVersion.node_id == node.id)
                     .order_by(NodeVersion.version_number)
                     .all())

        current = next((v for v in versions if v.valid_to is None), None)
        total_versions = len(versions)

        return {
            'total_versions': total_versions,
            'is_current': current is not None,
            'current_version': current.version_number if current else None,
            'last_change_type': versions[-1].change_type if versions else None,
            'last_changed_at': versions[-1].created_at.isoformat() if versions else None,
            'has_history': total_versions > 1,
        }
