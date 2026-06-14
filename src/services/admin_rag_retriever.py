# -*- coding: utf-8 -*-
"""
Admin RAG Retriever — singleton-доступ к admin-базе знаний ChromaDB.

Используется:
- ContractAnalyzerAgent: обогащение RAG-контекста законами и судебной практикой
- rag_admin/routes.py: управление коллекциями (stats, list, upload, delete)

Коллекции: laws, case_law, templates, knowledge
ChromaDB: data/chromadb (отдельная от data/chroma_enhanced)
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import List, Optional

from loguru import logger

_CHROMA_DIR = "data/chromadb"
COLLECTIONS = ["laws", "case_law", "templates", "knowledge"]
COLLECTION_LABELS = {
    "laws": "Законы и НПА",
    "case_law": "Судебная практика",
    "templates": "Шаблоны",
    "knowledge": "База знаний",
}

# ── Синглтоны ──────────────────────────────────────────────────────────────

_chroma_client = None
_embedding_fn = None


def get_chroma_client():
    """Lazy-init клиента ChromaDB (общий синглтон)."""
    global _chroma_client
    if _chroma_client is None:
        try:
            import chromadb
            from chromadb.config import Settings
            Path(_CHROMA_DIR).mkdir(parents=True, exist_ok=True)
            _chroma_client = chromadb.PersistentClient(
                path=_CHROMA_DIR,
                settings=Settings(anonymized_telemetry=False),
            )
        except Exception as e:
            logger.error(f"AdminRAG: не удалось инициализировать ChromaDB: {e}")
    return _chroma_client


def get_embedding_fn():
    """Lazy-init функции эмбеддингов (multilingual-MiniLM).

    КРИТИЧНО: грузим модель ОФЛАЙН из локального кеша. Без офлайн-режима при
    недоступности huggingface.co (нет интернета) SentenceTransformer падает на
    HEAD-запросе и происходит fallback на DefaultEmbeddingFunction — ДРУГУЮ
    модель. Размерность совпадает (384), Chroma не падает, но вектор-пространство
    иное → семантический поиск МОЛЧА деградирует (запрос и документы в разных
    пространствах). Поэтому HF_HUB_OFFLINE=1 + НИКАКОГО fallback на DefaultEF.
    """
    global _embedding_fn
    if _embedding_fn is None:
        os.environ.setdefault("HF_HUB_OFFLINE", "1")
        os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
        try:
            from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction
            _embedding_fn = SentenceTransformerEmbeddingFunction(
                model_name="paraphrase-multilingual-MiniLM-L12-v2"
            )
        except Exception as e:
            # НЕ делаем fallback на DefaultEF — несовместим со стором. Падаем громко.
            logger.error(f"AdminRAG: не удалось загрузить multilingual-MiniLM из кеша: {e}. "
                         f"Семантический поиск НЕДОСТУПЕН (fallback на DefaultEF запрещён — "
                         f"он несовместим с вектор-стором).")
            _embedding_fn = None
    return _embedding_fn


def get_collection(name: str):
    """Получить или создать коллекцию."""
    client = get_chroma_client()
    if client is None:
        return None
    ef = get_embedding_fn()
    kwargs = {"name": name, "metadata": {"description": COLLECTION_LABELS.get(name, name)}}
    if ef is not None:
        kwargs["embedding_function"] = ef
    try:
        return client.get_or_create_collection(**kwargs)
    except Exception as e:
        logger.error(f"AdminRAG: не удалось получить коллекцию '{name}': {e}")
        return None


# ── Re-ranker (cross-encoder) ───────────────────────────────────────────────
_reranker = None
_reranker_failed = False

def get_reranker():
    """Lazy-init cross-encoder для переранжирования (офлайн из кеша, MPS если есть)."""
    global _reranker, _reranker_failed
    if _reranker is None and not _reranker_failed:
        os.environ.setdefault("HF_HUB_OFFLINE", "1")
        os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
        try:
            from sentence_transformers import CrossEncoder
            import torch
            dev = "mps" if torch.backends.mps.is_available() else "cpu"
            _reranker = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2", device=dev)
            logger.info(f"AdminRAG: реранкер загружен (device={dev})")
        except Exception as e:
            _reranker_failed = True
            logger.warning(f"AdminRAG: реранкер недоступен ({e}) — поиск без переранжирования")
    return _reranker


# ── Retrieval ──────────────────────────────────────────────────────────────

def get_legal_context(
    query: str,
    collections: Optional[List[str]] = None,
    n_results: int = 4,
    max_chars: int = 3000,
) -> str:
    """
    Поиск релевантных фрагментов из базы знаний (laws + case_law).

    Возвращает строку-контекст для вставки в промпт LLM.
    При любой ошибке возвращает пустую строку (не ломает анализ).
    """
    if collections is None:
        collections = ["laws", "case_law"]

    try:
        # 1) Кандидаты: берём заведомо больше (fetch_k), чтобы реранкер выбрал лучшее
        fetch_k = max(n_results * 5, 15)
        cands = []  # (doc, label, title)
        for coll_name in collections:
            coll = get_collection(coll_name)
            if coll is None:
                continue
            count = coll.count()
            if count == 0:
                continue
            results = coll.query(
                query_texts=[query],
                n_results=min(fetch_k, count),
                include=["documents", "metadatas"],
            )
            if not results["documents"] or not results["documents"][0]:
                continue
            label = COLLECTION_LABELS.get(coll_name, coll_name)
            for doc, meta in zip(results["documents"][0], results["metadatas"][0]):
                title = (meta or {}).get("title", "")
                cands.append((doc, label, title))

        if not cands:
            return ""

        # 2) Переранжирование cross-encoder'ом (если доступен)
        reranker = get_reranker()
        if reranker is not None and len(cands) > 1:
            try:
                scores = reranker.predict([(query, c[0]) for c in cands])
                cands = [c for _, c in sorted(zip(scores, cands), key=lambda x: -x[0])]
            except Exception as e:
                logger.warning(f"AdminRAG: реранкинг не выполнен ({e})")

        # 3) Топ-N в контекст
        parts = []
        for doc, label, title in cands[:n_results]:
            header = f"[{label}]{f' — {title}' if title else ''}"
            parts.append(f"{header}\n{doc[:600]}")

        context = "\n\n".join(parts)
        if len(context) > max_chars:
            context = context[:max_chars] + "..."
        return context

    except Exception as e:
        logger.warning(f"AdminRAG.get_legal_context error (non-fatal): {e}")
        return ""


def has_legal_docs() -> bool:
    """Проверить, есть ли хоть что-то в laws или case_law."""
    try:
        for name in ("laws", "case_law"):
            coll = get_collection(name)
            if coll and coll.count() > 0:
                return True
    except Exception:
        pass
    return False
