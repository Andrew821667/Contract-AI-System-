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
            # РУССКИЙ реранкер (не английский ms-marco — тот для RU ранжировал плохо).
            # DiTy/cross-encoder-russian-msmarco — ruBERT, обучен на ru MS MARCO, лёгкий.
            # CPU: реранк идёт по ~20 кандидатам/запрос (не bulk), а MPS занят сервисом.
            _reranker = CrossEncoder("DiTy/cross-encoder-russian-msmarco", device="cpu", max_length=512)
            logger.info("AdminRAG: русский реранкер DiTy загружен (cpu)")
        except Exception as e:
            _reranker_failed = True
            logger.warning(f"AdminRAG: реранкер недоступен ({e}) — поиск без переранжирования")
    return _reranker


# ── USER2-эмбеддер запроса (deepvk/USER2-small, лёгкий, RU) ──────────────────
_u2_model = None
_u2_failed = False

def get_u2_model():
    """Lazy-init USER2-small для эмбеддинга ЗАПРОСА (офлайн, MPS). prompt search_query."""
    global _u2_model, _u2_failed
    if _u2_model is None and not _u2_failed:
        os.environ.setdefault("HF_HUB_OFFLINE", "1")
        os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
        try:
            from sentence_transformers import SentenceTransformer
            import torch
            dev = "mps" if torch.backends.mps.is_available() else "cpu"
            _u2_model = SentenceTransformer("deepvk/USER2-small", device=dev)
            logger.info(f"AdminRAG: USER2-small загружен (device={dev})")
        except Exception as e:
            _u2_failed = True
            logger.warning(f"AdminRAG: USER2-small недоступен ({e}) — fallback на 384-MiniLM-стор")
    return _u2_model

def _u2_collection(name: str):
    """USER2-коллекция (laws_u2/case_law_u2) без chroma-EF, если наполнена."""
    client = get_chroma_client()
    if client is None:
        return None
    try:
        coll = client.get_or_create_collection(name=name + "_u2")
        return coll if coll.count() > 0 else None
    except Exception:
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
        # 1) Кандидаты: берём заведомо больше (fetch_k) для последующего смешанного
        # ранжирования. Предпочитаем USER2-стор (laws_u2/case_law_u2) если наполнен.
        fetch_k = max(n_results * 8, int(os.environ.get("RAG_FETCH_K", "24")))
        cands = []  # dict: doc/label/title/category/dist
        u2 = get_u2_model()
        u2_active = u2 is not None and _u2_collection(collections[0]) is not None
        qemb = None
        if u2_active:
            qemb = u2.encode([query], prompt_name="search_query", convert_to_numpy=True)[0].tolist()
        for coll_name in collections:
            if u2_active:
                coll = _u2_collection(coll_name)
                if coll is None:
                    continue
                results = coll.query(query_embeddings=[qemb],
                                     n_results=min(fetch_k, coll.count()),
                                     include=["documents", "metadatas", "distances"])
            else:
                coll = get_collection(coll_name)
                if coll is None or coll.count() == 0:
                    continue
                results = coll.query(query_texts=[query],
                                     n_results=min(fetch_k, coll.count()),
                                     include=["documents", "metadatas", "distances"])
            if not results["documents"] or not results["documents"][0]:
                continue
            label = COLLECTION_LABELS.get(coll_name, coll_name)
            dists = (results.get("distances") or [[None]*len(results["documents"][0])])[0]
            for doc, meta, dist in zip(results["documents"][0], results["metadatas"][0], dists):
                cands.append({"doc": doc, "label": label,
                              "title": (meta or {}).get("title", ""),
                              "category": (meta or {}).get("category", ""),
                              "dist": dist})

        if not cands:
            return ""

        # 2) СМЕШАННОЕ ранжирование: вектор (USER2) + реранк (DiTy) + приоритет кодексам.
        # Чистый реранк DiTy топил лаконичные статьи кодексов под многословную практику;
        # blend сохраняет сильные векторные попадания, реранк уточняет, бонус кодексам
        # возвращает профильную норму наверх. Веса подобраны по тесту 20 вопросов.
        def _minmax(vals):
            lo, hi = min(vals), max(vals)
            return [0.5]*len(vals) if hi <= lo else [(v - lo) / (hi - lo) for v in vals]
        # вектор: меньше distance → лучше; инвертируем
        vsc = _minmax([-(c["dist"] if c["dist"] is not None else 0.0) for c in cands])
        reranker = get_reranker()
        if reranker is not None and len(cands) > 1:
            try:
                rsc = _minmax(list(reranker.predict([(query, c["doc"]) for c in cands])))
            except Exception as e:
                logger.warning(f"AdminRAG: реранкинг не выполнен ({e})"); rsc = vsc
        else:
            rsc = vsc
        # Веса (через env для подбора): вектор USER2 — надёжный сигнал для RU-права,
        # реранк DiTy уточняет, но не должен доминировать (топит кодексы).
        VEC_W = float(os.environ.get("RAG_VEC_W", "0.65"))
        RR_W = float(os.environ.get("RAG_RERANK_W", "0.35"))
        KOD_B = float(os.environ.get("RAG_KODEKS_BONUS", "0.20"))
        CODE_BONUS = {"kodeks": KOD_B, "federal_constitutional_law": KOD_B * 0.4}
        for i, c in enumerate(cands):
            c["score"] = VEC_W * vsc[i] + RR_W * rsc[i] + CODE_BONUS.get(c["category"], 0.0)
        order = sorted(range(len(cands)), key=lambda i: -cands[i]["score"])

        # 3) ДИВЕРСИФИКАЦИЯ: качественный юр-ответ = И НОРМА (кодекс/закон), И ПРАКТИКА.
        # Гарантируем в выдаче лучший кодекс и лучшую судебную практику (если есть
        # среди кандидатов), остальные слоты — по score. Иначе сильная практика
        # вытесняла профильный кодекс из топа (и наоборот).
        picked = []
        def grab(pred):
            for i in order:
                if i not in picked and pred(cands[i]):
                    picked.append(i); return
        if n_results >= 2:
            grab(lambda c: c["category"] == "kodeks")
            grab(lambda c: c["label"] == "Судебная практика")
        for i in order:
            if len(picked) >= n_results:
                break
            if i not in picked:
                picked.append(i)
        picked = sorted(picked[:n_results], key=lambda i: -cands[i]["score"])

        # 4) В контекст
        parts = []
        for i in picked:
            c = cands[i]; t = c["title"]
            header = f"[{c['label']}] — {t}" if t else f"[{c['label']}]"
            parts.append(f"{header}\n{c['doc'][:600]}")

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
