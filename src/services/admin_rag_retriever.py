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
        parts: List[str] = []
        for coll_name in collections:
            coll = get_collection(coll_name)
            if coll is None:
                continue

            count = coll.count()
            if count == 0:
                continue

            results = coll.query(
                query_texts=[query],
                n_results=min(n_results, count),
                include=["documents", "metadatas"],
            )

            if not results["documents"] or not results["documents"][0]:
                continue

            label = COLLECTION_LABELS.get(coll_name, coll_name)
            for doc, meta in zip(results["documents"][0], results["metadatas"][0]):
                title = meta.get("title", "") if meta else ""
                header = f"[{label}]{f' — {title}' if title else ''}"
                parts.append(f"{header}\n{doc[:600]}")

        if not parts:
            return ""

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
