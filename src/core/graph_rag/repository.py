# -*- coding: utf-8 -*-
"""
Graph-RAG Repository

CRUD-операции + graph traversal через recursive CTE.
Soft delete (архивация) вместо физического удаления.
Все изменения логируются в RAGAuditLog.
"""
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any, Tuple

from sqlalchemy import text, and_, or_, func, literal_column
from sqlalchemy.orm import Session, joinedload

from .models import (
    GraphDocument, GraphNode, NodeVersion, GraphEdge,
    CandidateEdge, GraphEntity, RAGAuditLog,
)
from .enums import (
    EdgeClass, EdgeStatus, ExtractedBy, ChangeType,
    ChangedBy, AuditAction, ParseStatus, DocumentStatus,
)


# ──────────────────────────────────────────────
# Audit helper
# ──────────────────────────────────────────────

def _audit(
    db: Session,
    action: str,
    entity_type: str,
    entity_id: str,
    actor: str = "system",
    user_id: Optional[str] = None,
    changes: Optional[Dict] = None,
    reason: Optional[str] = None,
    context: Optional[Dict] = None,
):
    """Создать запись аудита."""
    log = RAGAuditLog(
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        actor=actor,
        user_id=user_id,
        changes=changes,
        reason=reason,
        context=context,
    )
    db.add(log)


# ──────────────────────────────────────────────
# GraphDocumentRepository
# ──────────────────────────────────────────────

class GraphDocumentRepository:
    """Операции с документами в графе."""

    def __init__(self, db: Session):
        self.db = db

    def create(self, **kwargs) -> GraphDocument:
        doc = GraphDocument(**kwargs)
        self.db.add(doc)
        self.db.flush()
        _audit(self.db, AuditAction.DOCUMENT_INGESTED, "graph_document", doc.id,
               actor=kwargs.get("_actor", "system"),
               context={"layer": doc.layer, "title": doc.title})
        return doc

    def get_by_id(self, doc_id: str) -> Optional[GraphDocument]:
        return self.db.query(GraphDocument).filter(GraphDocument.id == doc_id).first()

    def get_active(self, layer: Optional[str] = None, limit: int = 100, offset: int = 0) -> List[GraphDocument]:
        q = self.db.query(GraphDocument).filter(GraphDocument.status == DocumentStatus.ACTIVE)
        if layer:
            q = q.filter(GraphDocument.layer == layer)
        return q.order_by(GraphDocument.created_at.desc()).offset(offset).limit(limit).all()

    def archive(self, doc_id: str, reason: str, actor: str = "system", user_id: Optional[str] = None) -> Optional[GraphDocument]:
        doc = self.get_by_id(doc_id)
        if not doc:
            return None
        doc.status = DocumentStatus.ARCHIVED
        self.db.flush()
        _audit(self.db, AuditAction.DOCUMENT_ARCHIVED, "graph_document", doc_id,
               actor=actor, user_id=user_id, reason=reason)
        return doc

    def update_stats(self, doc_id: str):
        """Пересчитать статистику узлов и рёбер документа."""
        doc = self.get_by_id(doc_id)
        if not doc:
            return
        doc.nodes_count = self.db.query(func.count(GraphNode.id)).filter(
            GraphNode.document_id == doc_id, GraphNode.is_archived == False
        ).scalar()
        doc.edges_count = self.db.query(func.count(GraphEdge.id)).filter(
            GraphEdge.source_id.in_(
                self.db.query(GraphNode.id).filter(GraphNode.document_id == doc_id)
            )
        ).scalar()


# ──────────────────────────────────────────────
# GraphNodeRepository
# ──────────────────────────────────────────────

class GraphNodeRepository:
    """Операции с узлами графа."""

    def __init__(self, db: Session):
        self.db = db

    def create(self, actor: str = "parser", **kwargs) -> GraphNode:
        node = GraphNode(**kwargs)
        self.db.add(node)
        self.db.flush()

        # Автоматически создаём первую версию
        version = NodeVersion(
            node_id=node.id,
            version_number=1,
            text=node.text,
            meta_info=node.meta_info,
            valid_from=datetime.now(timezone.utc),
            changed_by=ChangedBy.SYSTEM,
            change_type=ChangeType.NEW,
        )
        self.db.add(version)

        _audit(self.db, AuditAction.NODE_CREATED, "graph_node", node.id,
               actor=actor,
               context={"document_id": node.document_id, "node_type": node.node_type,
                         "number": node.number})
        return node

    def get_by_id(self, node_id: str, include_archived: bool = False) -> Optional[GraphNode]:
        q = self.db.query(GraphNode).filter(GraphNode.id == node_id)
        if not include_archived:
            q = q.filter(GraphNode.is_archived == False)
        return q.first()

    def get_by_document(self, document_id: str, include_archived: bool = False) -> List[GraphNode]:
        q = self.db.query(GraphNode).filter(GraphNode.document_id == document_id)
        if not include_archived:
            q = q.filter(GraphNode.is_archived == False)
        return q.order_by(GraphNode.level, GraphNode.position).all()

    def get_children(self, node_id: str) -> List[GraphNode]:
        return (self.db.query(GraphNode)
                .filter(GraphNode.parent_id == node_id, GraphNode.is_archived == False)
                .order_by(GraphNode.position)
                .all())

    def get_siblings(self, node_id: str) -> List[GraphNode]:
        """Получить соседние узлы (тот же parent)."""
        node = self.get_by_id(node_id)
        if not node or not node.parent_id:
            return []
        return (self.db.query(GraphNode)
                .filter(GraphNode.parent_id == node.parent_id,
                        GraphNode.id != node_id,
                        GraphNode.is_archived == False)
                .order_by(GraphNode.position)
                .all())

    def get_ancestors(self, node_id: str, max_depth: int = 10) -> List[GraphNode]:
        """
        Получить всех предков узла (от непосредственного родителя до корня).
        Использует recursive CTE для эффективного обхода.
        """
        cte = text("""
            WITH RECURSIVE ancestors AS (
                SELECT id, parent_id, node_type, title, number, text, level, position, 1 as depth
                FROM graph_nodes
                WHERE id = :node_id AND is_archived = 0

                UNION ALL

                SELECT gn.id, gn.parent_id, gn.node_type, gn.title, gn.number, gn.text, gn.level, gn.position, a.depth + 1
                FROM graph_nodes gn
                JOIN ancestors a ON gn.id = a.parent_id
                WHERE gn.is_archived = 0 AND a.depth < :max_depth
            )
            SELECT id FROM ancestors WHERE depth > 1 ORDER BY depth DESC
        """)
        result = self.db.execute(cte, {"node_id": node_id, "max_depth": max_depth})
        ancestor_ids = [row[0] for row in result]
        if not ancestor_ids:
            return []
        nodes = self.db.query(GraphNode).filter(GraphNode.id.in_(ancestor_ids)).all()
        # Сортируем в порядке от корня к узлу
        id_order = {aid: i for i, aid in enumerate(ancestor_ids)}
        nodes.sort(key=lambda n: id_order.get(n.id, 0))
        return nodes

    def get_subtree(self, node_id: str, max_depth: int = 5) -> List[GraphNode]:
        """
        Получить поддерево узла (все потомки до max_depth).
        Recursive CTE.
        """
        cte = text("""
            WITH RECURSIVE subtree AS (
                SELECT id, parent_id, node_type, level, position, 0 as depth
                FROM graph_nodes
                WHERE id = :node_id AND is_archived = 0

                UNION ALL

                SELECT gn.id, gn.parent_id, gn.node_type, gn.level, gn.position, s.depth + 1
                FROM graph_nodes gn
                JOIN subtree s ON gn.parent_id = s.id
                WHERE gn.is_archived = 0 AND s.depth < :max_depth
            )
            SELECT id FROM subtree WHERE depth > 0 ORDER BY depth, position
        """)
        result = self.db.execute(cte, {"node_id": node_id, "max_depth": max_depth})
        child_ids = [row[0] for row in result]
        if not child_ids:
            return []
        return self.db.query(GraphNode).filter(GraphNode.id.in_(child_ids)).all()

    def find_by_number(self, document_id: str, number: str) -> Optional[GraphNode]:
        """Найти узел по номеру пункта/статьи внутри документа."""
        return (self.db.query(GraphNode)
                .filter(GraphNode.document_id == document_id,
                        GraphNode.number == number,
                        GraphNode.is_archived == False)
                .first())

    def search_text(self, document_id: str, query: str, limit: int = 20) -> List[GraphNode]:
        """Полнотекстовый поиск по узлам документа (LIKE для MVP)."""
        pattern = f"%{query}%"
        return (self.db.query(GraphNode)
                .filter(GraphNode.document_id == document_id,
                        GraphNode.text.ilike(pattern),
                        GraphNode.is_archived == False)
                .limit(limit)
                .all())

    def archive(self, node_id: str, reason: str, actor: str = "system",
                user_id: Optional[str] = None) -> Optional[GraphNode]:
        """Архивировать узел (soft delete). Физическое удаление запрещено."""
        node = self.get_by_id(node_id)
        if not node:
            return None
        node.is_archived = True
        node.archived_at = datetime.now(timezone.utc)
        node.archived_reason = reason
        self.db.flush()
        _audit(self.db, AuditAction.NODE_ARCHIVED, "graph_node", node_id,
               actor=actor, user_id=user_id, reason=reason,
               context={"document_id": node.document_id})
        return node

    def update_text(self, node_id: str, new_text: str, reason: str,
                    changed_by: str = "user", change_type: str = "correction",
                    user_id: Optional[str] = None) -> Optional[GraphNode]:
        """Обновить текст узла с созданием новой версии."""
        node = self.get_by_id(node_id)
        if not node:
            return None

        old_text = node.text

        # Закрываем текущую версию
        current_version = (self.db.query(NodeVersion)
                           .filter(NodeVersion.node_id == node_id, NodeVersion.valid_to == None)
                           .first())
        if current_version:
            current_version.valid_to = datetime.now(timezone.utc)
            next_num = current_version.version_number + 1
        else:
            next_num = 1

        # Создаём новую версию
        new_version = NodeVersion(
            node_id=node_id,
            version_number=next_num,
            text=new_text,
            meta_info=node.meta_info,
            valid_from=datetime.now(timezone.utc),
            changed_by=changed_by,
            change_type=change_type,
            change_reason=reason,
        )
        self.db.add(new_version)
        self.db.flush()

        # Обновляем текст узла
        node.text = new_text

        _audit(self.db, AuditAction.NODE_UPDATED, "graph_node", node_id,
               actor=changed_by, user_id=user_id, reason=reason,
               changes={"text": {"old": old_text[:200], "new": new_text[:200]}})
        _audit(self.db, AuditAction.VERSION_CREATED, "node_version", new_version.id,
               actor=changed_by, user_id=user_id,
               context={"node_id": node_id, "version_number": next_num})
        return node

    def get_history(self, node_id: str) -> List[NodeVersion]:
        """Получить историю версий узла."""
        return (self.db.query(NodeVersion)
                .filter(NodeVersion.node_id == node_id)
                .order_by(NodeVersion.version_number)
                .all())


# ──────────────────────────────────────────────
# GraphEdgeRepository
# ──────────────────────────────────────────────

class GraphEdgeRepository:
    """Операции с рёбрами графа."""

    def __init__(self, db: Session):
        self.db = db

    def create(self, actor: str = "parser", **kwargs) -> GraphEdge:
        edge = GraphEdge(**kwargs)
        self.db.add(edge)
        self.db.flush()
        _audit(self.db, AuditAction.EDGE_CREATED, "graph_edge", edge.id,
               actor=actor,
               context={"source_id": edge.source_id, "target_id": edge.target_id,
                         "edge_type": edge.edge_type, "edge_class": edge.edge_class})
        return edge

    def get_by_id(self, edge_id: str) -> Optional[GraphEdge]:
        return self.db.query(GraphEdge).filter(GraphEdge.id == edge_id).first()

    def get_outgoing(self, node_id: str, edge_types: Optional[List[str]] = None,
                     edge_classes: Optional[List[str]] = None) -> List[GraphEdge]:
        """Исходящие рёбра из узла с фильтрацией."""
        q = self.db.query(GraphEdge).filter(GraphEdge.source_id == node_id)
        if edge_types:
            q = q.filter(GraphEdge.edge_type.in_(edge_types))
        if edge_classes:
            q = q.filter(GraphEdge.edge_class.in_(edge_classes))
        return q.all()

    def get_incoming(self, node_id: str, edge_types: Optional[List[str]] = None,
                     edge_classes: Optional[List[str]] = None) -> List[GraphEdge]:
        """Входящие рёбра в узел с фильтрацией."""
        q = self.db.query(GraphEdge).filter(GraphEdge.target_id == node_id)
        if edge_types:
            q = q.filter(GraphEdge.edge_type.in_(edge_types))
        if edge_classes:
            q = q.filter(GraphEdge.edge_class.in_(edge_classes))
        return q.all()

    def get_edges_between(self, node_a: str, node_b: str) -> List[GraphEdge]:
        """Все рёбра между двумя узлами (в обоих направлениях)."""
        return (self.db.query(GraphEdge)
                .filter(or_(
                    and_(GraphEdge.source_id == node_a, GraphEdge.target_id == node_b),
                    and_(GraphEdge.source_id == node_b, GraphEdge.target_id == node_a),
                ))
                .all())

    def expand(self, node_ids: List[str], max_depth: int = 2,
               allowed_classes: Optional[List[str]] = None,
               allowed_statuses: Optional[List[str]] = None) -> List[GraphEdge]:
        """
        Graph expansion: получить все рёбра на расстоянии до max_depth
        от заданных узлов. Фильтрация по edge_class и status.

        По умолчанию: structural + verified fact edges.
        """
        if not allowed_classes:
            allowed_classes = [EdgeClass.STRUCTURAL, EdgeClass.FACT]
        if not allowed_statuses:
            allowed_statuses = [EdgeStatus.VERIFIED, EdgeStatus.MACHINE_EXTRACTED]

        # Для MVP: итеративное расширение (без CTE для рёбер,
        # т.к. CTE для графа рёбер сложнее в SQLAlchemy)
        visited_nodes = set(node_ids)
        all_edges = []
        frontier = set(node_ids)

        for depth in range(max_depth):
            if not frontier:
                break

            edges = (self.db.query(GraphEdge)
                     .filter(
                         or_(
                             GraphEdge.source_id.in_(frontier),
                             GraphEdge.target_id.in_(frontier),
                         ),
                         GraphEdge.edge_class.in_(allowed_classes),
                         GraphEdge.status.in_(allowed_statuses),
                     )
                     .all())

            new_frontier = set()
            for edge in edges:
                if edge not in all_edges:
                    all_edges.append(edge)
                if edge.source_id not in visited_nodes:
                    new_frontier.add(edge.source_id)
                    visited_nodes.add(edge.source_id)
                if edge.target_id not in visited_nodes:
                    new_frontier.add(edge.target_id)
                    visited_nodes.add(edge.target_id)

            frontier = new_frontier

        return all_edges

    def update_status(self, edge_id: str, new_status: str, reason: str,
                      actor: str = "system", user_id: Optional[str] = None) -> Optional[GraphEdge]:
        """Изменить статус ребра с аудитом."""
        edge = self.get_by_id(edge_id)
        if not edge:
            return None
        old_status = edge.status
        edge.status = new_status
        _audit(self.db, AuditAction.EDGE_STATUS_CHANGED, "graph_edge", edge_id,
               actor=actor, user_id=user_id, reason=reason,
               changes={"status": {"old": old_status, "new": new_status}})
        return edge


# ──────────────────────────────────────────────
# CandidateEdgeRepository
# ──────────────────────────────────────────────

class CandidateEdgeRepository:
    """Операции с кандидатами на связи."""

    def __init__(self, db: Session):
        self.db = db

    def create(self, **kwargs) -> CandidateEdge:
        candidate = CandidateEdge(**kwargs)
        self.db.add(candidate)
        self.db.flush()
        _audit(self.db, AuditAction.CANDIDATE_CREATED, "candidate_edge", candidate.id,
               actor="system",
               context={"source_id": candidate.source_id, "target_id": candidate.target_id,
                         "proposed_type": candidate.proposed_type})
        return candidate

    def get_pending(self, limit: int = 50) -> List[CandidateEdge]:
        """Получить кандидаты, ожидающие ревью."""
        return (self.db.query(CandidateEdge)
                .filter(CandidateEdge.reviewed == False, CandidateEdge.requires_review == True)
                .order_by(CandidateEdge.confidence.desc())
                .limit(limit)
                .all())

    def get_by_node(self, node_id: str) -> List[CandidateEdge]:
        """Все кандидаты, связанные с узлом."""
        return (self.db.query(CandidateEdge)
                .filter(or_(
                    CandidateEdge.source_id == node_id,
                    CandidateEdge.target_id == node_id,
                ))
                .all())

    def review(self, candidate_id: str, result: str, reviewer_id: str,
               comment: Optional[str] = None) -> Tuple[Optional[CandidateEdge], Optional[GraphEdge]]:
        """
        Провести ревью кандидата.
        Если accepted — создаётся GraphEdge.
        Возвращает (candidate, created_edge_or_none).
        """
        candidate = self.db.query(CandidateEdge).filter(CandidateEdge.id == candidate_id).first()
        if not candidate:
            return None, None

        candidate.reviewed = True
        candidate.review_result = result
        candidate.reviewed_by = reviewer_id
        candidate.review_comment = comment
        candidate.reviewed_at = datetime.now(timezone.utc)

        created_edge = None
        if result == "accepted":
            # Создаём verified edge из кандидата
            created_edge = GraphEdge(
                source_id=candidate.source_id,
                target_id=candidate.target_id,
                edge_type=candidate.proposed_type,
                edge_class=candidate.proposed_class,
                status=EdgeStatus.VERIFIED,
                evidence=candidate.evidence,
                rationale=candidate.rationale,
                confidence=candidate.confidence,
                extracted_by=ExtractedBy.LLM,
            )
            self.db.add(created_edge)
            self.db.flush()
            candidate.accepted_edge_id = created_edge.id

            _audit(self.db, AuditAction.EDGE_CREATED, "graph_edge", created_edge.id,
                   actor="user", user_id=reviewer_id,
                   context={"from_candidate": candidate_id})

        _audit(self.db, AuditAction.CANDIDATE_REVIEWED, "candidate_edge", candidate_id,
               actor="user", user_id=reviewer_id,
               changes={"review_result": {"old": None, "new": result}},
               reason=comment)

        return candidate, created_edge


# ──────────────────────────────────────────────
# GraphEntityRepository
# ──────────────────────────────────────────────

class GraphEntityRepository:
    """Операции с нормализованными сущностями."""

    def __init__(self, db: Session):
        self.db = db

    def create(self, **kwargs) -> GraphEntity:
        entity = GraphEntity(**kwargs)
        self.db.add(entity)
        self.db.flush()
        return entity

    def get_by_node(self, node_id: str) -> List[GraphEntity]:
        return self.db.query(GraphEntity).filter(GraphEntity.node_id == node_id).all()

    def find_by_type(self, entity_type: str, value: Optional[str] = None,
                     limit: int = 50) -> List[GraphEntity]:
        q = self.db.query(GraphEntity).filter(GraphEntity.entity_type == entity_type)
        if value:
            q = q.filter(GraphEntity.entity_value.ilike(f"%{value}%"))
        return q.limit(limit).all()

    def find_norm_references(self, norm_code: Optional[str] = None,
                             article: Optional[str] = None) -> List[GraphEntity]:
        """Поиск ссылок на нормы НПА."""
        q = self.db.query(GraphEntity).filter(GraphEntity.entity_type == "norm_ref")
        if norm_code:
            q = q.filter(GraphEntity.norm_code.ilike(f"%{norm_code}%"))
        if article:
            q = q.filter(GraphEntity.norm_article == article)
        return q.all()


# ──────────────────────────────────────────────
# Convenience: единый фасад
# ──────────────────────────────────────────────

class GraphRepository:
    """
    Фасад для всех graph-RAG репозиториев.

    Использование:
        repo = GraphRepository(db)
        doc = repo.documents.create(layer="contract", title="...")
        node = repo.nodes.create(document_id=doc.id, ...)
        repo.edges.create(source_id=n1.id, target_id=n2.id, ...)
    """

    def __init__(self, db: Session):
        self.db = db
        self.documents = GraphDocumentRepository(db)
        self.nodes = GraphNodeRepository(db)
        self.edges = GraphEdgeRepository(db)
        self.candidates = CandidateEdgeRepository(db)
        self.entities = GraphEntityRepository(db)

    def commit(self):
        self.db.commit()

    def rollback(self):
        self.db.rollback()
