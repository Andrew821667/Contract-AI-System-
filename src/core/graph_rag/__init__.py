# -*- coding: utf-8 -*-
"""
Graph-RAG Module

Графовая модель документов для Contract AI System.
Основная модель представления анализируемых договоров и НПА.

Использование:
    from src.core.graph_rag import GraphRepository
    from src.core.graph_rag.models import GraphNode, GraphEdge
    from src.core.graph_rag.enums import LayerType, NodeType, EdgeType
"""

from .models import (
    GraphDocument,
    GraphNode,
    NodeVersion,
    GraphEdge,
    CandidateEdge,
    GraphEntity,
    RAGAuditLog,
)

from .enums import (
    LayerType,
    NodeType,
    EdgeType,
    EdgeClass,
    EdgeStatus,
    ExtractedBy,
    ChangeType,
    ChangedBy,
    ParseStatus,
    ReviewResult,
    DocumentStatus,
    AuditAction,
)

from .repository import (
    GraphRepository,
    GraphDocumentRepository,
    GraphNodeRepository,
    GraphEdgeRepository,
    CandidateEdgeRepository,
    GraphEntityRepository,
)

from .pipeline import GraphRAGPipeline, IngestionResult
from .audit import GraphAuditService

__all__ = [
    # Models
    "GraphDocument",
    "GraphNode",
    "NodeVersion",
    "GraphEdge",
    "CandidateEdge",
    "GraphEntity",
    "RAGAuditLog",
    # Enums
    "LayerType",
    "NodeType",
    "EdgeType",
    "EdgeClass",
    "EdgeStatus",
    "ExtractedBy",
    "ChangeType",
    "ChangedBy",
    "ParseStatus",
    "ReviewResult",
    "DocumentStatus",
    "AuditAction",
    # Repositories
    "GraphRepository",
    "GraphDocumentRepository",
    "GraphNodeRepository",
    "GraphEdgeRepository",
    "CandidateEdgeRepository",
    "GraphEntityRepository",
    # Pipeline
    "GraphRAGPipeline",
    "IngestionResult",
    # Audit
    "GraphAuditService",
]
