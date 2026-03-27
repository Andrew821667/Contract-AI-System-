# -*- coding: utf-8 -*-
"""
API v2 — Graph-RAG

Endpoints для работы с графом документов:
- POST   /graph/ingest       — загрузить документ в граф
- POST   /graph/ask          — RAG-запрос (search + context + policy)
- POST   /graph/search       — поиск по графу
- GET    /graph/documents     — список документов в графе
- GET    /graph/documents/{id} — документ с деревом
- GET    /graph/nodes/{id}    — узел с контекстом
- GET    /graph/stats         — статистика графа
- GET    /graph/entities/{document_id} — сущности документа
- POST   /graph/candidates    — предложить связь (CandidateEdge)
- POST   /graph/candidates/{id}/review — ревью кандидата
- GET    /graph/audit/{entity_type}/{entity_id} — audit log
"""
import logging
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from src.api.dependencies import get_current_user
from src.models.database import get_db
from src.models.auth_models import User
from src.core.graph_rag.tools import GraphReadTools, GraphWriteTools, GraphAnalyzeTools
from src.core.graph_rag.audit import GraphAuditService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/graph", tags=["Graph-RAG"])


# ──────────────────────────────────────────────
# Pydantic schemas
# ──────────────────────────────────────────────

class GraphAskRequest(BaseModel):
    query: str = Field(..., min_length=1, description="Вопрос пользователя")
    document_ids: Optional[List[str]] = Field(None, description="Ограничить по документам")
    layers: Optional[List[str]] = Field(None, description="contract, npa")
    top_k: int = Field(5, ge=1, le=20)
    max_context_chars: int = Field(8000, ge=1000, le=30000)


class GraphSearchRequest(BaseModel):
    query: str = Field(..., min_length=1)
    document_ids: Optional[List[str]] = None
    layers: Optional[List[str]] = None
    top_k: int = Field(10, ge=1, le=50)


class GraphIngestTextRequest(BaseModel):
    text: str = Field(..., min_length=10)
    title: str = Field(..., min_length=1)
    layer: str = Field("contract", pattern="^(contract|npa)$")
    contract_id: Optional[str] = None
    legal_document_id: Optional[str] = None


class ProposeEdgeRequest(BaseModel):
    source_id: str
    target_id: str
    proposed_type: str
    proposed_class: str = Field(..., pattern="^(analytical|risk_signal)$")
    rationale: str = Field(..., min_length=10)
    evidence: Optional[str] = None
    confidence: float = Field(0.5, ge=0.0, le=1.0)


class ReviewCandidateRequest(BaseModel):
    result: str = Field(..., pattern="^(accepted|rejected|modified)$")
    comment: Optional[str] = None


# ──────────────────────────────────────────────
# Dependencies
# ──────────────────────────────────────────────

def get_read_tools(db: Session = Depends(get_db)) -> GraphReadTools:
    return GraphReadTools(db)


def get_write_tools(db: Session = Depends(get_db)) -> GraphWriteTools:
    return GraphWriteTools(db)


def get_analyze_tools(db: Session = Depends(get_db)) -> GraphAnalyzeTools:
    return GraphAnalyzeTools(db)


def get_audit_service(db: Session = Depends(get_db)) -> GraphAuditService:
    return GraphAuditService(db)


# ──────────────────────────────────────────────
# POST /graph/ask — RAG-запрос
# ──────────────────────────────────────────────

@router.post(
    "/ask",
    summary="RAG-запрос: поиск + контекст + answer policy",
)
async def graph_ask(
    body: GraphAskRequest,
    tools: GraphReadTools = Depends(get_read_tools),
    current_user: User = Depends(get_current_user),
):
    """
    Основной endpoint для вопросов по документам.
    Возвращает контекст, system prompt и метаданные для формирования ответа.
    """
    result = tools.ask(
        query=body.query,
        document_ids=body.document_ids,
        layers=body.layers,
        top_k=body.top_k,
        max_context_chars=body.max_context_chars,
    )
    return result


# ──────────────────────────────────────────────
# POST /graph/search
# ──────────────────────────────────────────────

@router.post(
    "/search",
    summary="Поиск по графу документов",
)
async def graph_search(
    body: GraphSearchRequest,
    tools: GraphReadTools = Depends(get_read_tools),
    current_user: User = Depends(get_current_user),
):
    return tools.search(
        query=body.query,
        document_ids=body.document_ids,
        layers=body.layers,
        top_k=body.top_k,
    )


# ──────────────────────────────────────────────
# POST /graph/ingest — загрузка текста
# ──────────────────────────────────────────────

@router.post(
    "/ingest",
    status_code=status.HTTP_201_CREATED,
    summary="Загрузить текст документа в граф",
)
async def graph_ingest_text(
    body: GraphIngestTextRequest,
    tools: GraphWriteTools = Depends(get_write_tools),
    current_user: User = Depends(get_current_user),
):
    result = tools.ingest_text(
        text=body.text,
        title=body.title,
        layer=body.layer,
        contract_id=body.contract_id,
        legal_document_id=body.legal_document_id,
    )
    return result


# ──────────────────────────────────────────────
# GET /graph/documents
# ──────────────────────────────────────────────

@router.get(
    "/documents",
    summary="Список документов в графе",
)
async def list_graph_documents(
    layer: Optional[str] = Query(None, pattern="^(contract|npa)$"),
    limit: int = Query(20, ge=1, le=100),
    tools: GraphReadTools = Depends(get_read_tools),
    current_user: User = Depends(get_current_user),
):
    return tools.list_documents(layer=layer, limit=limit)


# ──────────────────────────────────────────────
# GET /graph/documents/{document_id}
# ──────────────────────────────────────────────

@router.get(
    "/documents/{document_id}",
    summary="Документ с деревом узлов",
)
async def get_graph_document(
    document_id: str,
    max_depth: int = Query(2, ge=1, le=5),
    tools: GraphReadTools = Depends(get_read_tools),
    current_user: User = Depends(get_current_user),
):
    result = tools.get_document(document_id, max_depth=max_depth)
    if not result:
        raise HTTPException(status_code=404, detail="Document not found in graph")
    return result


# ──────────────────────────────────────────────
# GET /graph/nodes/{node_id}
# ──────────────────────────────────────────────

@router.get(
    "/nodes/{node_id}",
    summary="Узел графа с контекстом",
)
async def get_graph_node(
    node_id: str,
    include_context: bool = Query(True),
    tools: GraphReadTools = Depends(get_read_tools),
    current_user: User = Depends(get_current_user),
):
    result = tools.get_node(node_id, include_context=include_context)
    if not result:
        raise HTTPException(status_code=404, detail="Node not found")
    return result


# ──────────────────────────────────────────────
# GET /graph/stats
# ──────────────────────────────────────────────

@router.get(
    "/stats",
    summary="Статистика графа",
)
async def graph_stats(
    document_id: Optional[str] = Query(None),
    tools: GraphAnalyzeTools = Depends(get_analyze_tools),
    current_user: User = Depends(get_current_user),
):
    return tools.stats(document_id=document_id)


# ──────────────────────────────────────────────
# GET /graph/entities/{document_id}
# ──────────────────────────────────────────────

@router.get(
    "/entities/{document_id}",
    summary="Сущности документа (суммы, даты, нормы)",
)
async def graph_entity_summary(
    document_id: str,
    tools: GraphAnalyzeTools = Depends(get_analyze_tools),
    current_user: User = Depends(get_current_user),
):
    return tools.entity_summary(document_id=document_id)


# ──────────────────────────────────────────────
# GET /graph/references/{document_id}
# ──────────────────────────────────────────────

@router.get(
    "/references/{document_id}",
    summary="Ссылки на НПА в документе",
)
async def graph_norm_references(
    document_id: str,
    norm_code: Optional[str] = Query(None),
    tools: GraphAnalyzeTools = Depends(get_analyze_tools),
    current_user: User = Depends(get_current_user),
):
    return tools.find_norm_references(document_id=document_id, norm_code=norm_code)


# ──────────────────────────────────────────────
# POST /graph/candidates — предложить связь
# ──────────────────────────────────────────────

@router.post(
    "/candidates",
    status_code=status.HTTP_201_CREATED,
    summary="Предложить связь между узлами (CandidateEdge)",
)
async def propose_edge(
    body: ProposeEdgeRequest,
    tools: GraphWriteTools = Depends(get_write_tools),
    current_user: User = Depends(get_current_user),
):
    return tools.propose_edge(
        source_id=body.source_id,
        target_id=body.target_id,
        proposed_type=body.proposed_type,
        proposed_class=body.proposed_class,
        rationale=body.rationale,
        evidence=body.evidence,
        confidence=body.confidence,
    )


# ──────────────────────────────────────────────
# POST /graph/candidates/{id}/review
# ──────────────────────────────────────────────

@router.post(
    "/candidates/{candidate_id}/review",
    summary="Ревью кандидата на связь",
)
async def review_candidate(
    candidate_id: str,
    body: ReviewCandidateRequest,
    tools: GraphWriteTools = Depends(get_write_tools),
    current_user: User = Depends(get_current_user),
):
    result = tools.review_candidate(
        candidate_id=candidate_id,
        result=body.result,
        reviewer_id=current_user.id,
        comment=body.comment,
    )
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result


# ──────────────────────────────────────────────
# GET /graph/candidates/pending
# ──────────────────────────────────────────────

@router.get(
    "/candidates/pending",
    summary="Кандидаты на связи, ожидающие ревью",
)
async def pending_candidates(
    limit: int = Query(20, ge=1, le=100),
    tools: GraphAnalyzeTools = Depends(get_analyze_tools),
    current_user: User = Depends(get_current_user),
):
    return tools.pending_reviews(limit=limit)


# ──────────────────────────────────────────────
# GET /graph/audit/{entity_type}/{entity_id}
# ──────────────────────────────────────────────

@router.get(
    "/audit/{entity_type}/{entity_id}",
    summary="Audit log сущности графа",
)
async def graph_audit_log(
    entity_type: str,
    entity_id: str,
    limit: int = Query(50, ge=1, le=200),
    audit: GraphAuditService = Depends(get_audit_service),
    current_user: User = Depends(get_current_user),
):
    return audit.get_entity_history(entity_type, entity_id, limit=limit)
