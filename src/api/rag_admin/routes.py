# -*- coding: utf-8 -*-
"""
RAG Admin API — управление базой знаний ChromaDB.

Endpoints:
  GET    /api/v1/rag/stats                     — статистика по коллекциям
  GET    /api/v1/rag/documents?collection=...  — список документов
  POST   /api/v1/rag/documents                 — загрузить файл
  DELETE /api/v1/rag/documents/{doc_id}        — удалить документ

Синглтоны ChromaDB/эмбеддинги — из src.services.admin_rag_retriever (общие с агентом).
"""
import collections
import hashlib
import io
import re
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from loguru import logger
from pydantic import BaseModel

from src.api.dependencies import get_current_user
from src.models.auth_models import User
from src.services.admin_rag_retriever import (
    COLLECTION_LABELS,
    COLLECTIONS,
    get_collection as _get_collection_shared,
)

router = APIRouter(prefix="/rag", tags=["RAG Admin"])

# Stats cache (60s TTL) — stats query scans all collections, cache per request
_stats_cache: Optional[tuple] = None  # (StatsResponse, expires_at: float)
_STATS_TTL = 60.0

# Upload rate limiter: 10 uploads per user per minute (token bucket per user_id)
_upload_rl_lock = threading.Lock()
_upload_rl_buckets: dict[str, collections.deque] = {}
_UPLOAD_RL_MAX = 10     # max uploads
_UPLOAD_RL_WINDOW = 60  # seconds


def _check_upload_rate_limit(user_id: str) -> None:
    now = time.time()
    with _upload_rl_lock:
        bucket = _upload_rl_buckets.setdefault(user_id, collections.deque())
        # Drop timestamps outside the window
        while bucket and bucket[0] <= now - _UPLOAD_RL_WINDOW:
            bucket.popleft()
        if len(bucket) >= _UPLOAD_RL_MAX:
            raise HTTPException(
                status_code=429,
                detail=f"Слишком много загрузок. Лимит: {_UPLOAD_RL_MAX} файлов в минуту.",
            )
        bucket.append(now)


# ── Route-level helper (raises HTTPException вместо None) ────────────────────

def _get_collection(name: str):
    if name not in COLLECTIONS:
        raise HTTPException(status_code=400, detail=f"Неизвестная коллекция: {name}")
    coll = _get_collection_shared(name)
    if coll is None:
        raise HTTPException(status_code=503, detail="ChromaDB недоступна")
    return coll


# ── Text extraction ──────────────────────────────────────────────────────────

def _extract_text(content: bytes, filename: str) -> str:
    ext = Path(filename).suffix.lower()
    if ext == ".txt":
        return content.decode("utf-8", errors="ignore")
    if ext == ".pdf":
        import pdfplumber
        text_parts = []
        with pdfplumber.open(io.BytesIO(content)) as pdf:
            for page in pdf.pages:
                t = page.extract_text()
                if t:
                    text_parts.append(t)
        return "\n".join(text_parts)
    if ext in (".docx", ".doc"):
        import docx
        doc = docx.Document(io.BytesIO(content))
        return "\n".join(p.text for p in doc.paragraphs if p.text.strip())
    raise HTTPException(
        status_code=400,
        detail=f"Неподдерживаемый формат: {ext}. Используйте .txt, .pdf, .docx",
    )


def _chunk_text(text: str, chunk_size: int = 800, overlap: int = 150) -> List[str]:
    sentences = re.split(r"(?<=[.!?])\s+", text)
    chunks, current, current_len = [], [], 0
    for sentence in sentences:
        slen = len(sentence)
        if current_len + slen > chunk_size and current:
            chunks.append(" ".join(current))
            overlap_text = " ".join(current)[-overlap:]
            current = [overlap_text, sentence]
            current_len = len(overlap_text) + slen
        else:
            current.append(sentence)
            current_len += slen
    if current:
        chunks.append(" ".join(current))
    return [c for c in chunks if len(c.strip()) >= 50]


# ── Schemas ──────────────────────────────────────────────────────────────────

class CollectionStat(BaseModel):
    name: str
    label: str
    chunk_count: int
    doc_count: int


class RAGDocument(BaseModel):
    doc_id: str
    title: str
    collection: str
    doc_type: Optional[str] = None
    chunks: int
    uploaded_by: Optional[str] = None
    created_at: Optional[str] = None


class StatsResponse(BaseModel):
    collections: List[CollectionStat]


class DocumentsResponse(BaseModel):
    documents: List[RAGDocument]
    total: int


# ── Endpoints ────────────────────────────────────────────────────────────────

class UploadResponse(BaseModel):
    ok: bool
    doc_id: str
    title: str
    collection: str
    chunks: int


class DeleteResponse(BaseModel):
    ok: bool
    deleted_chunks: int


@router.get("/stats", response_model=StatsResponse)
async def get_stats(current_user: User = Depends(get_current_user)):
    """Статистика по всем коллекциям ChromaDB."""
    global _stats_cache
    if _stats_cache is not None and _stats_cache[1] > time.time():
        return _stats_cache[0]

    result = []
    for name in COLLECTIONS:
        try:
            coll = _get_collection(name)
            all_items = coll.get(include=["metadatas"])
            doc_ids = {m.get("doc_id") for m in all_items["metadatas"] if m.get("doc_id")}
            result.append(CollectionStat(
                name=name,
                label=COLLECTION_LABELS.get(name, name),
                chunk_count=len(all_items["ids"]),
                doc_count=len(doc_ids),
            ))
        except HTTPException:
            result.append(CollectionStat(
                name=name, label=COLLECTION_LABELS.get(name, name), chunk_count=0, doc_count=0,
            ))
        except Exception as e:
            logger.warning(f"Не удалось получить статистику для {name}: {e}")
            result.append(CollectionStat(
                name=name, label=COLLECTION_LABELS.get(name, name), chunk_count=0, doc_count=0,
            ))
    response = StatsResponse(collections=result)
    _stats_cache = (response, time.time() + _STATS_TTL)
    return response


@router.get("/documents", response_model=DocumentsResponse)
async def list_documents(
    collection: str = Query("knowledge", description="Коллекция ChromaDB"),
    limit: int = Query(50, ge=1, le=200, description="Максимум документов"),
    offset: int = Query(0, ge=0, description="Смещение (для пагинации)"),
    current_user: User = Depends(get_current_user),
):
    """Список документов в коллекции (сгруппированных по doc_id)."""
    coll = _get_collection(collection)
    all_items = coll.get(include=["metadatas"])

    is_admin = current_user.role in ("admin", "senior_lawyer")
    docs: Dict[str, Dict[str, Any]] = {}
    for meta in all_items["metadatas"]:
        doc_id = meta.get("doc_id")
        if not doc_id:
            continue
        # IDOR fix: non-admin users see only their own documents
        if not is_admin and meta.get("uploaded_by") != str(current_user.id):
            continue
        if doc_id not in docs:
            docs[doc_id] = {
                "doc_id": doc_id,
                "title": meta.get("title", doc_id),
                "collection": collection,
                "doc_type": meta.get("doc_type"),
                "uploaded_by": meta.get("uploaded_by"),
                "created_at": meta.get("created_at"),
                "chunks": 0,
            }
        docs[doc_id]["chunks"] += 1

    all_documents = [RAGDocument(**d) for d in docs.values()]
    all_documents.sort(key=lambda d: d.created_at or "", reverse=True)
    paginated = all_documents[offset : offset + limit]
    return DocumentsResponse(documents=paginated, total=len(all_documents))


@router.post("/documents", status_code=status.HTTP_201_CREATED, response_model=UploadResponse)
async def upload_document(
    file: UploadFile = File(...),
    collection: str = Query("knowledge"),
    doc_type: Optional[str] = Query(None, description="Тип документа"),
    current_user: User = Depends(get_current_user),
):
    """
    Загрузить документ в ChromaDB.
    Поддерживаемые форматы: .txt, .pdf, .docx
    """
    _check_upload_rate_limit(str(current_user.id))

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Файл пустой")

    text = _extract_text(content, file.filename or "document.txt")
    if not text.strip():
        raise HTTPException(status_code=400, detail="Не удалось извлечь текст из файла")

    doc_id = hashlib.md5(f"{file.filename}_{current_user.id}".encode()).hexdigest()
    chunks = _chunk_text(text)

    if not chunks:
        raise HTTPException(status_code=400, detail="Документ слишком короткий для индексации")

    now = datetime.now(timezone.utc).isoformat()
    title = Path(file.filename or "document").stem
    coll = _get_collection(collection)

    existing = coll.get(where={"doc_id": doc_id})
    if existing["ids"]:
        coll.delete(ids=existing["ids"])

    ids = [f"{doc_id}_chunk_{i}" for i in range(len(chunks))]
    metadatas = [
        {
            "doc_id": doc_id,
            "title": title,
            "doc_type": doc_type or "document",
            "chunk_id": i,
            "total_chunks": len(chunks),
            "uploaded_by": str(current_user.id),
            "created_at": now,
            "filename": file.filename or "",
        }
        for i in range(len(chunks))
    ]

    coll.add(ids=ids, documents=chunks, metadatas=metadatas)
    logger.info(
        f"RAG: загружен '{title}' ({len(chunks)} чанков) → '{collection}' пользователем {current_user.id}"
    )
    global _stats_cache
    _stats_cache = None  # invalidate stats cache after upload

    return UploadResponse(ok=True, doc_id=doc_id, title=title, collection=collection, chunks=len(chunks))


@router.delete("/documents/{doc_id}", response_model=DeleteResponse)
async def delete_document(
    doc_id: str,
    collection: str = Query("knowledge"),
    current_user: User = Depends(get_current_user),
):
    """Удалить документ из ChromaDB по doc_id."""
    coll = _get_collection(collection)
    existing = coll.get(where={"doc_id": doc_id}, include=["metadatas"])

    if not existing["ids"]:
        raise HTTPException(status_code=404, detail="Документ не найден в коллекции")

    # Verify ownership — only the uploader or an admin can delete (IDOR prevention)
    if current_user.role != "admin":
        meta = existing["metadatas"][0] if existing["metadatas"] else {}
        if meta.get("uploaded_by") != str(current_user.id):
            raise HTTPException(status_code=403, detail="Нет доступа к этому документу")

    coll.delete(ids=existing["ids"])
    logger.info(f"RAG: удалён документ {doc_id} из коллекции '{collection}' пользователем {current_user.id}")
    global _stats_cache
    _stats_cache = None  # invalidate stats cache after delete
    return DeleteResponse(ok=True, deleted_chunks=len(existing["ids"]))
