# -*- coding: utf-8 -*-
"""
Graph-RAG SQLAlchemy Models

Графовая модель документов: узлы, рёбра, версии, кандидаты, аудит.
Основная модель представления анализируемых договоров и НПА.
"""
from datetime import datetime, timezone
from sqlalchemy import (
    Boolean, Column, String, Text, Integer, Float,
    DateTime, ForeignKey, CheckConstraint, Index, JSON
)
from sqlalchemy.orm import relationship

from src.models.database import Base, generate_uuid


# ──────────────────────────────────────────────
# GraphDocument — документ-источник
# ──────────────────────────────────────────────

class GraphDocument(Base):
    """
    Документ, загруженный в граф.
    Корневая сущность: один документ → одно дерево GraphNode.
    Связан с Contract (если это договор) или LegalDocument (если НПА).
    """
    __tablename__ = "graph_documents"

    id = Column(String(36), primary_key=True, default=generate_uuid)

    # Связь с существующими моделями
    contract_id = Column(String(36), ForeignKey("contracts.id", ondelete="SET NULL"), index=True)
    legal_document_id = Column(String(36), ForeignKey("legal_documents.id", ondelete="SET NULL"), index=True)

    # Метаданные документа
    layer = Column(String(20), nullable=False, index=True)        # contract | npa
    title = Column(Text, nullable=False)
    document_date = Column(DateTime)                                # Дата документа (подписания / принятия)
    edition_date = Column(DateTime)                                 # Дата редакции (для НПА)
    document_type = Column(String(50))                              # Тип: supply, service, federal_law...
    source_file = Column(Text)                                      # Путь к исходному файлу
    source_format = Column(String(20))                              # docx, pdf, html

    # Статус парсинга
    parse_status = Column(String(20), nullable=False, default="fully_parsed", index=True)
    parse_errors = Column(JSON)                                     # Ошибки парсинга если partial

    # Статус документа
    status = Column(String(20), nullable=False, default="active", index=True)

    # Статистика
    nodes_count = Column(Integer, default=0)
    edges_count = Column(Integer, default=0)

    # Timestamps
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    contract = relationship("Contract", foreign_keys=[contract_id])
    legal_document = relationship("LegalDocument", foreign_keys=[legal_document_id])
    nodes = relationship("GraphNode", back_populates="document", cascade="all, delete-orphan")

    __table_args__ = (
        CheckConstraint(
            "layer IN ('contract', 'npa', 'court', 'internal')",
            name="check_graph_doc_layer"
        ),
        CheckConstraint(
            "parse_status IN ('fully_parsed', 'partial_parse', 'needs_review', 'failed')",
            name="check_graph_doc_parse_status"
        ),
        CheckConstraint(
            "status IN ('active', 'archived', 'superseded')",
            name="check_graph_doc_status"
        ),
    )

    def __repr__(self):
        return f"<GraphDocument(id={self.id}, layer={self.layer}, title={self.title[:50] if self.title else ''})>"


# ──────────────────────────────────────────────
# GraphNode — узел графа (пункт, статья, таблица...)
# ──────────────────────────────────────────────

class GraphNode(Base):
    """
    Узел графа документа.

    Каждый структурный элемент документа (раздел, пункт, подпункт, таблица,
    определение, приложение) представлен как GraphNode. Дерево документа
    строится через parent_id (adjacency list).
    """
    __tablename__ = "graph_nodes"

    id = Column(String(36), primary_key=True, default=generate_uuid)

    # Принадлежность
    document_id = Column(String(36), ForeignKey("graph_documents.id", ondelete="CASCADE"),
                         nullable=False, index=True)
    layer = Column(String(20), nullable=False, index=True)

    # Тип узла
    node_type = Column(String(30), nullable=False, index=True)

    # Идентификация
    title = Column(Text)                                            # Заголовок (если есть)
    number = Column(String(50))                                     # Номер пункта/статьи: "1.1", "ст. 330"
    text = Column(Text, nullable=False)                             # Текст узла

    # Дерево (adjacency list)
    parent_id = Column(String(36), ForeignKey("graph_nodes.id", ondelete="CASCADE"), index=True)
    level = Column(Integer, nullable=False, default=0)              # Уровень вложенности (0 = корень)
    position = Column(Integer, nullable=False, default=0)           # Порядок среди соседей

    # Метаданные
    meta_info = Column(JSON)                                        # Доп. данные: xpath, стиль, шрифт...

    # Статус
    is_archived = Column(Boolean, default=False, index=True)
    archived_at = Column(DateTime)
    archived_reason = Column(Text)

    # Timestamps
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    document = relationship("GraphDocument", back_populates="nodes")
    parent = relationship("GraphNode", remote_side=[id], backref="children")
    versions = relationship("NodeVersion", back_populates="node", cascade="all, delete-orphan",
                            order_by="NodeVersion.version_number")

    # Рёбра (исходящие и входящие)
    outgoing_edges = relationship("GraphEdge", foreign_keys="GraphEdge.source_id",
                                  back_populates="source_node", cascade="all, delete-orphan",
                                  lazy="select")
    incoming_edges = relationship("GraphEdge", foreign_keys="GraphEdge.target_id",
                                  back_populates="target_node", cascade="all, delete-orphan",
                                  lazy="select")

    __table_args__ = (
        CheckConstraint(
            "layer IN ('contract', 'npa', 'court', 'internal')",
            name="check_graph_node_layer"
        ),
        CheckConstraint(
            "node_type IN ('document', 'section', 'clause', 'subclause', 'paragraph', "
            "'table', 'table_row', 'list_item', 'appendix', 'term', 'header', "
            "'preamble', 'signature_block', 'article', 'part', 'chapter', 'title', 'note')",
            name="check_graph_node_type"
        ),
        Index("ix_graph_nodes_parent_position", "parent_id", "position"),
        Index("ix_graph_nodes_doc_level", "document_id", "level"),
    )

    def __repr__(self):
        label = self.number or self.title or self.text[:30]
        return f"<GraphNode(id={self.id}, type={self.node_type}, '{label}')>"


# ──────────────────────────────────────────────
# NodeVersion — версия содержимого узла
# ──────────────────────────────────────────────

class NodeVersion(Base):
    """
    Версия узла: хранит историю изменений текста.
    valid_to = NULL означает текущую (действующую) версию.
    """
    __tablename__ = "node_versions"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    node_id = Column(String(36), ForeignKey("graph_nodes.id", ondelete="CASCADE"),
                     nullable=False, index=True)

    version_number = Column(Integer, nullable=False)
    text = Column(Text, nullable=False)
    meta_info = Column(JSON)

    # Temporal validity
    valid_from = Column(DateTime)
    valid_to = Column(DateTime)                                     # NULL = текущая версия

    # Change tracking
    change_reason = Column(Text)
    changed_by = Column(String(20), nullable=False)                 # user | agent | system
    change_type = Column(String(20), nullable=False)                # new | correction | new_edition | archive

    # Timestamps
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)

    # Relationships
    node = relationship("GraphNode", back_populates="versions")

    __table_args__ = (
        CheckConstraint(
            "changed_by IN ('user', 'agent', 'system')",
            name="check_version_changed_by"
        ),
        CheckConstraint(
            "change_type IN ('new', 'correction', 'new_edition', 'archive')",
            name="check_version_change_type"
        ),
        Index("ix_node_versions_node_version", "node_id", "version_number", unique=True),
        Index("ix_node_versions_valid_to", "node_id", "valid_to"),
    )

    def __repr__(self):
        return f"<NodeVersion(node_id={self.node_id}, v={self.version_number})>"


# ──────────────────────────────────────────────
# GraphEdge — связь между узлами (verified)
# ──────────────────────────────────────────────

class GraphEdge(Base):
    """
    Связь между узлами графа.

    Structural и fact edges хранятся здесь.
    Analytical/risk edges попадают сюда ТОЛЬКО после верификации
    (из CandidateEdge).
    """
    __tablename__ = "graph_edges"

    id = Column(String(36), primary_key=True, default=generate_uuid)

    source_id = Column(String(36), ForeignKey("graph_nodes.id", ondelete="CASCADE"),
                       nullable=False, index=True)
    target_id = Column(String(36), ForeignKey("graph_nodes.id", ondelete="CASCADE"),
                       nullable=False, index=True)

    # Классификация
    edge_type = Column(String(50), nullable=False, index=True)      # Конкретный тип: parent_child, references...
    edge_class = Column(String(20), nullable=False, index=True)     # structural | fact | analytical | risk_signal

    # Подтверждённость
    status = Column(String(25), nullable=False, default="verified", index=True)

    # Обоснование
    evidence = Column(Text)                                          # Текст-обоснование из документа
    rationale = Column(Text)                                         # Почему связь создана

    # Метрики
    confidence = Column(Float, default=1.0)                          # 0.0–1.0

    # Происхождение
    extracted_by = Column(String(20), nullable=False)                # parser | rule | llm | manual

    # Temporal validity
    valid_from = Column(DateTime)
    valid_to = Column(DateTime)

    # Timestamps
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    source_node = relationship("GraphNode", foreign_keys=[source_id], back_populates="outgoing_edges",
                               lazy="select")
    target_node = relationship("GraphNode", foreign_keys=[target_id], back_populates="incoming_edges",
                               lazy="select")

    __table_args__ = (
        CheckConstraint(
            "edge_class IN ('structural', 'fact', 'analytical', 'risk_signal')",
            name="check_edge_class"
        ),
        CheckConstraint(
            "status IN ('verified', 'machine_extracted', 'hypothesis', 'deprecated')",
            name="check_edge_status"
        ),
        CheckConstraint(
            "extracted_by IN ('parser', 'rule', 'llm', 'manual')",
            name="check_edge_extracted_by"
        ),
        CheckConstraint(
            "confidence >= 0.0 AND confidence <= 1.0",
            name="check_edge_confidence"
        ),
        Index("ix_graph_edges_source_type", "source_id", "edge_type"),
        Index("ix_graph_edges_target_type", "target_id", "edge_type"),
        Index("ix_graph_edges_valid_from_to", "valid_from", "valid_to"),
    )

    def __repr__(self):
        return f"<GraphEdge(src={self.source_id[:8]}, tgt={self.target_id[:8]}, type={self.edge_type})>"


# ──────────────────────────────────────────────
# CandidateEdge — кандидат на связь (отдельно!)
# ──────────────────────────────────────────────

class CandidateEdge(Base):
    """
    Кандидат на связь — предложен LLM или аналитикой.

    КРИТИЧЕСКИ ВАЖНО: хранится ОТДЕЛЬНО от verified edges.
    LLM не создаёт финальные рёбра напрямую — только кандидатов.
    После ревью юристом может быть принят → создаётся GraphEdge.
    """
    __tablename__ = "candidate_edges"

    id = Column(String(36), primary_key=True, default=generate_uuid)

    source_id = Column(String(36), ForeignKey("graph_nodes.id", ondelete="CASCADE"),
                       nullable=False, index=True)
    target_id = Column(String(36), ForeignKey("graph_nodes.id", ondelete="CASCADE"),
                       nullable=False, index=True)

    # Предложенная классификация
    proposed_type = Column(String(50), nullable=False)               # Предложенный edge_type
    proposed_class = Column(String(20), nullable=False)              # analytical | risk_signal

    # Обоснование
    rationale = Column(Text, nullable=False)
    evidence = Column(Text)
    confidence = Column(Float, default=0.5)

    # Review workflow
    requires_review = Column(Boolean, default=True)
    reviewed = Column(Boolean, default=False, index=True)
    review_result = Column(String(20))                               # accepted | rejected | modified
    reviewed_by = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"))
    review_comment = Column(Text)

    # Если принят — ссылка на созданный GraphEdge
    accepted_edge_id = Column(String(36), ForeignKey("graph_edges.id", ondelete="SET NULL"))

    # Timestamps
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    reviewed_at = Column(DateTime)

    # Relationships
    source_node = relationship("GraphNode", foreign_keys=[source_id])
    target_node = relationship("GraphNode", foreign_keys=[target_id])
    reviewer = relationship("User", foreign_keys=[reviewed_by])
    accepted_edge = relationship("GraphEdge", foreign_keys=[accepted_edge_id])

    __table_args__ = (
        CheckConstraint(
            "proposed_class IN ('analytical', 'risk_signal')",
            name="check_candidate_proposed_class"
        ),
        CheckConstraint(
            "review_result IN ('accepted', 'rejected', 'modified') OR review_result IS NULL",
            name="check_candidate_review_result"
        ),
        CheckConstraint(
            "confidence >= 0.0 AND confidence <= 1.0",
            name="check_candidate_confidence"
        ),
        Index("ix_candidate_edges_pending", "reviewed", "requires_review"),
    )

    def __repr__(self):
        status = self.review_result or ("pending" if not self.reviewed else "reviewed")
        return f"<CandidateEdge(id={self.id[:8]}, type={self.proposed_type}, status={status})>"


# ──────────────────────────────────────────────
# GraphEntity — нормализованная сущность
# ──────────────────────────────────────────────

class GraphEntity(Base):
    """
    Нормализованная сущность, извлечённая из узла.

    NormReference (ст. 330 ГК РФ), MonetaryValue (1 000 000 руб.),
    DateReference (до 31.12.2026), ClauseType (неустойка), ContractType (поставка).
    """
    __tablename__ = "graph_entities"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    node_id = Column(String(36), ForeignKey("graph_nodes.id", ondelete="CASCADE"),
                     nullable=False, index=True)

    # Классификация
    entity_type = Column(String(30), nullable=False, index=True)     # norm_ref, monetary, date_ref, clause_type, contract_type
    entity_value = Column(Text, nullable=False)                      # Нормализованное значение
    raw_text = Column(Text, nullable=False)                          # Оригинальный текст из документа

    # Для NormReference
    norm_code = Column(String(100))                                  # "ГК РФ", "ФЗ-44"
    norm_article = Column(String(50))                                # "330", "14.1"
    norm_part = Column(String(50))                                   # Часть/пункт статьи

    # Для MonetaryValue
    amount = Column(Float)
    currency = Column(String(10))                                    # RUB, USD, EUR

    # Для DateReference
    date_value = Column(DateTime)
    date_type = Column(String(20))                                   # deadline, start, end, signing

    # Происхождение
    extracted_by = Column(String(20), nullable=False, default="parser")
    confidence = Column(Float, default=1.0)

    # Timestamps
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    # Relationships
    node = relationship("GraphNode")

    __table_args__ = (
        CheckConstraint(
            "entity_type IN ('norm_ref', 'monetary', 'date_ref', 'clause_type', "
            "'contract_type', 'document_edition')",
            name="check_entity_type"
        ),
        CheckConstraint(
            "extracted_by IN ('parser', 'rule', 'llm', 'manual')",
            name="check_entity_extracted_by"
        ),
        Index("ix_graph_entities_type_value", "entity_type", "entity_value"),
    )

    def __repr__(self):
        return f"<GraphEntity(type={self.entity_type}, value={self.entity_value[:30]})>"


# ──────────────────────────────────────────────
# RAGAuditLog — аудит всех изменений графа
# ──────────────────────────────────────────────

class RAGAuditLog(Base):
    """
    Аудит изменений графа.
    Каждое создание/изменение/архивирование узлов, рёбер, версий логируется.
    Физическое удаление запрещено в MVP.
    """
    __tablename__ = "rag_audit_log"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # Что изменилось
    action = Column(String(30), nullable=False, index=True)          # node_created, edge_updated, ...
    entity_type = Column(String(30), nullable=False)                 # graph_node, graph_edge, node_version, ...
    entity_id = Column(String(36), nullable=False, index=True)       # ID изменённой сущности

    # Кто изменил
    actor = Column(String(20), nullable=False)                       # user | agent | system | parser
    user_id = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"))

    # Детали
    changes = Column(JSON)                                           # {field: {old: ..., new: ...}}
    reason = Column(Text)
    context = Column(JSON)                                           # Доп. контекст (document_id, session_id, ...)

    # Timestamps
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)

    # Relationships
    user = relationship("User", foreign_keys=[user_id])

    __table_args__ = (
        Index("ix_rag_audit_entity", "entity_type", "entity_id"),
        Index("ix_rag_audit_action_time", "action", "created_at"),
    )

    def __repr__(self):
        return f"<RAGAuditLog(action={self.action}, entity={self.entity_type}:{self.entity_id[:8]})>"


# ──────────────────────────────────────────────
# Exports
# ──────────────────────────────────────────────

__all__ = [
    "GraphDocument",
    "GraphNode",
    "NodeVersion",
    "GraphEdge",
    "CandidateEdge",
    "GraphEntity",
    "RAGAuditLog",
]
