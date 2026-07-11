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


# ── Лексический канал (BM25/FTS5) для гибридного поиска ─────────────────────
_fts_conn = None
_fts_failed = False
_FTS_PATH = "data/chromadb/lexical_fts.db"
import re as _re

_FTS_STOP = set(
    "для при под над без про что как где или его это эта эти при течение порядок "
    "связанных вопросам некоторых применения рассмотрения".split()
)

def _fts_query_terms(query: str) -> str:
    """Строим FTS5 MATCH из значимых слов запроса (префиксы — грубая компенсация
    русской морфологии, которой нет в FTS5): "неустой"* OR "займ"* ..."""
    ws = [w for w in _re.findall(r"[а-яёa-z]+", query.lower())
          if len(w) >= 5 and w not in _FTS_STOP]
    seen, terms = set(), []
    for w in ws:
        stem = w[: max(5, len(w) - 2)]
        if stem in seen:
            continue
        seen.add(stem)
        terms.append(f'"{stem}"*')
    return " OR ".join(terms)

def _get_fts():
    global _fts_conn, _fts_failed
    if _fts_conn is None and not _fts_failed:
        try:
            import sqlite3
            if not Path(_FTS_PATH).exists():
                _fts_failed = True
                return None
            # read-only, общий для потоков uvicorn (sqlite + FTS5 — потокобезопасно на чтение)
            _fts_conn = sqlite3.connect(f"file:{_FTS_PATH}?mode=ro", uri=True,
                                        check_same_thread=False)
        except Exception as e:
            _fts_failed = True
            logger.warning(f"AdminRAG: FTS-индекс недоступен ({e}) — гибрид выключен")
    return _fts_conn

def _fts_search(query: str, k: int):
    """Топ-k чанков по BM25. Возвращает [(chunk_id, text, title, category, coll)]."""
    conn = _get_fts()
    if conn is None:
        return []
    fq = _fts_query_terms(query)
    if not fq:
        return []
    try:
        rows = conn.execute(
            "SELECT chunk_id, text, title, category, coll FROM chunks_fts "
            "WHERE chunks_fts MATCH ? ORDER BY bm25(chunks_fts) LIMIT ?",
            (fq, k)).fetchall()
        return rows
    except Exception as e:
        logger.warning(f"AdminRAG: FTS-поиск не выполнен ({e})")
        return []


# ── Retrieval ──────────────────────────────────────────────────────────────

# -- Graph-hop (semantic edges, project graph-build) --
_SEM_EDGES = None
def _semantic_edges():
    global _SEM_EDGES
    if _SEM_EDGES is None:
        try:
            import json as _json
            _SEM_EDGES = _json.load(open("data/semantic_edges.json", encoding="utf-8"))
        except Exception:
            _SEM_EDGES = {}
    return _SEM_EDGES

_PILOT_COLL = None
def _pilot_collection():
    global _PILOT_COLL
    if _PILOT_COLL is None:
        try:
            _PILOT_COLL = get_chroma_client().get_collection("laws_pilot")
        except Exception:
            _PILOT_COLL = False
    return _PILOT_COLL or None

def _clean_norm(t):
    import re as _r
    t = _r.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", t)
    t = _r.sub(r"\(в ред\.[^)]*\)|\(см\. текст[^)]*\)|Позиции высших судов[^\n]*|Путеводител[^\n]*|Перспективы и риски[^\n]*|Вопросы судебной практики[^\n]*|КонсультантПлюс|Подготовлена редакция[^\n]*|>>>", "", t)
    return _r.sub(r"[ \t]+", " ", t).strip()


_ART_TEXTS = None
def _article_texts():
    global _ART_TEXTS
    if _ART_TEXTS is None:
        try:
            import json as _json
            _ART_TEXTS = _json.load(open("data/article_texts.json", encoding="utf-8"))
        except Exception:
            _ART_TEXTS = {}
    return _ART_TEXTS

def _norm_text(did, art):
    """Чистый текст статьи: сперва article_texts (из .md), затем pilot (fallback)."""
    t = _article_texts().get(did, {}).get(art)
    if t:
        return t
    pilot = _pilot_collection()
    if pilot is None:
        return ""
    try:
        g = pilot.get(where={"$and": [{"doc_id": did}, {"article": art}]},
                      include=["documents"])
        if g["documents"]:
            return _clean_norm(" ".join(g["documents"]))
    except Exception:
        pass
    return ""

def _graph_hop_text(query, qemb, base_ctx=""):
    edges = _semantic_edges()
    if not edges or qemb is None:
        return ""
    rr = get_reranker()
    if rr is None:
        return ""
    try:
        import re as _re
        # 1а) ЯКОРЬ-A: основной поиск laws_u2 -> реранк -> номер статьи из текста чанка.
        main = get_chroma_client().get_collection("laws_u2")
        mr = main.query(query_embeddings=[qemb], n_results=12,
                        include=["documents", "metadatas"])
        if not mr["documents"] or not mr["documents"][0]:
            return ""
        docs = mr["documents"][0]; metas = mr["metadatas"][0]
        msc = list(rr.predict([(query, d[:500]) for d in docs]))
        morder = sorted(range(len(docs)), key=lambda i: -msc[i])
        minsc = float(os.environ.get("RAG_HOP_MINSCORE", "0.2"))
        _ART = _re.compile(r"(?:Стать[яи]|ст\.?)\s*(\d+(?:\.\d+)?)")
        prim = []; prim_keys = set()
        # слабый чанк-топ гейтит только regex-якорь; LLM-якорь работает всегда
        for i in (morder[:4] if msc[morder[0]] >= minsc else []):
            did = (metas[i] or {}).get("doc_id")
            if not did or did not in edges:
                continue
            for a in _ART.findall(docs[i][:600]):
                if a in edges.get(did, {}) and (did, a) not in prim_keys:
                    prim_keys.add((did, a)); prim.append((did, a))
                    break
            if len(prim) >= 2:
                break
        # 1б) ЯКОРЬ-B (generate-then-verify): LLM называет статью+кодекс; берём ТОЛЬКО
        # если статья есть в графе. Такие якоря имеют приоритет и мягкий порог.
        llm_keys = set()
        try:
            from src.services.llm_gateway import LLMGateway as _GW
            _CDX = {"ГК": ["5142", "9027", "34154", "64629"], "УК": ["10699"],
                    "ТК": ["34683"], "СК": ["8982"], "КОАП": ["34661"],
                    "НК": ["19671"], "ЖК": ["51057"], "ГПК": ["39570"],
                    "УПК": ["34481"], "АПК": ["37800"], "ЗК": ["33773"],
                    "БК": ["19702"]}
            _o = _GW(provider="deepseek", model="deepseek-chat").call(
                prompt=(f"Вопрос: {query}\nНазови 1-2 статьи российских кодексов, напрямую "
                        "регулирующие вопрос. Формат СТРОГО: ст.НОМЕР КОДЕКС (кодекс одним "
                        "словом: ГК, УК, ТК, СК, КоАП, НК, ЖК, ГПК, УПК, АПК, ЗК, БК), "
                        "через запятую. Ничего больше."),
                system_prompt="Ты юрист-справочник. Отвечай только в заданном формате.",
                response_format="text", temperature=0.0, max_tokens=40)
            for _num, _cdx in _re.findall(r"ст\.?\s*(\d+(?:\.\d+)?)\s*([А-Яа-яЁё]+)",
                                          _o if isinstance(_o, str) else str(_o)):
                for _did in _CDX.get(_cdx.upper().replace("РФ", "").strip(), []):
                    if _num in edges.get(_did, {}):
                        llm_keys.add((_did, _num))
                        if (_did, _num) not in prim_keys:
                            prim_keys.add((_did, _num)); prim.append((_did, _num))
                        break
        except Exception:
            pass
        if not prim:
            return ""
        # 2) КАНДИДАТЫ: якоря (если их номера НЕТ в базовом контексте) + связанные по рёбрам.
        ctx_nums = set(_ART.findall(base_ctx or ""))
        rel_keys = [(did, a) for did, a in prim if a not in ctx_nums]
        for did, a in prim:
            for r in edges.get(did, {}).get(a, []):
                if (did, r) not in prim_keys and (did, r) not in rel_keys:
                    rel_keys.append((did, r))
        items = []
        for did, r in rel_keys[:16]:
            t = _norm_text(did, r)
            if t:
                items.append((did, r, t))
        if not items:
            return ""
        # 3) ОТБОР: LLM-якоря первыми (мягкий порог — они верифицированы графом),
        # затем остальные по реранку с обычным порогом. Всего top-3.
        rs = list(rr.predict([(query, t[2][:500]) for t in items]))
        _absmin = float(os.environ.get("RAG_HOP_REL_MIN", "0.1"))
        _amin = float(os.environ.get("RAG_HOP_ANCHOR_MIN", "0.0"))
        order = sorted(range(len(items)), key=lambda i: -rs[i])
        pick = [i for i in order if (items[i][0], items[i][1]) in llm_keys and rs[i] >= _amin][:2]
        for i in order:
            if len(pick) >= 3:
                break
            if i not in pick and rs[i] >= _absmin:
                pick.append(i)
        if not pick:
            return ""
        out = [f"[Связанная норма] ст.{items[i][1]}\n{items[i][2][:700]}" for i in pick]
        return "\n\n".join(out)
    except Exception as _e:
        logger.warning(f"AdminRAG: graph-hop failed ({_e})")
        return ""


def get_legal_context(
    query: str,
    collections: Optional[List[str]] = None,
    n_results: int = 4,
    max_chars: int = 3000,
    aux_query: Optional[str] = None,
) -> str:
    """
    Поиск релевантных фрагментов из базы знаний (laws + case_law).

    Возвращает строку-контекст для вставки в промпт LLM.
    При любой ошибке возвращает пустую строку (не ломает анализ).
    """
    if collections is None:
        collections = ["laws", "case_law"]

    try:
        # 0) Авто-рерайт за флагом RAG_REWRITE: deepseek-chat переводит разговорный
        # запрос в канон-форму → pool-union расширяет пул кандидатов.
        # aux_query=None (default) → активируется; явный aux_query → без изменений.
        _do_rewrite = False
        if aux_query is None:
            try:
                from config.settings import settings as _cfg
                _do_rewrite = _cfg.rag_rewrite
            except Exception:
                _do_rewrite = bool(os.environ.get("RAG_REWRITE", "").strip())
        # Два варианта рерайта ОДНИМ вызовом: (1) доктрина/термины кодексов —
        # исторический вариант; (2) титул профильного ФЗ + термины его заголовка.
        # Замер 2026-07-11: вариант «титул ФЗ» ВМЕСТО доктрины чинит ФЗ-темы
        # (held-out 77→87%), но роняет кодексные (парные 93→91%) — поэтому оба
        # варианта идут в pool-union КАК ДВА aux-запроса (пул только растёт,
        # эмбеддинг локальный/дешёвый, LLM-вызов один).
        _aux_list = [aux_query] if aux_query else []
        if aux_query is None and _do_rewrite:
            try:
                from src.services.llm_gateway import LLMGateway as _GW
                _SYS = (
                    "Ты — помощник юридического поиска по российскому праву. "
                    "Перепиши бытовой вопрос пользователя в поисковые запросы на "
                    "языке закона. Верни РОВНО ДВЕ строки без нумерации и кавычек:\n"
                    "строка 1 — область права и ключевые правовые термины/институты "
                    "(как в названиях статей кодексов);\n"
                    "строка 2 — если тема регулируется профильным федеральным "
                    "законом: его официальное краткое название (как в заголовке "
                    "закона) плюс ключевые термины заголовка; если профильного ФЗ "
                    "нет — та же тема другими словами.\n"
                    "НЕ отвечай на вопрос."
                )
                _FEWSHOT = (
                    "Примеры (для других тем):\n"
                    "Вопрос: сколько времени есть на возврат денег за авиабилет\n"
                    "Запрос:\nвозврат провозной платы при отказе пассажира от воздушной перевозки\n"
                    "Воздушный кодекс, договор воздушной перевозки пассажира\n\n"
                    "Вопрос: мне постоянно звонят с рекламой хотя я не соглашался\n"
                    "Запрос:\nраспространение рекламы по сетям электросвязи, согласие абонента\n"
                    "федеральный закон о рекламе, требования к распространению рекламы\n\n"
                    f"Вопрос: {query}\nЗапрос:"
                )
                _rw = _GW(provider="deepseek", model="deepseek-chat").call(
                    prompt=_FEWSHOT, system_prompt=_SYS,
                    response_format="text", temperature=0.0, max_tokens=160,
                )
                _rw = (_rw if isinstance(_rw, str) else str(_rw)).strip().strip('"')
                for _line in _rw.splitlines():
                    _line = _line.strip().strip('"').lstrip("-•1234567890.) ").strip()
                    if _line and _line != query and _line not in _aux_list:
                        _aux_list.append(_line)
                    if len(_aux_list) >= 2:
                        break
                if _aux_list:
                    aux_query = _aux_list[0]  # для обратной совместимости логики ниже
                    logger.debug(f"AdminRAG rewrite: «{query[:50]}» → {_aux_list}")
            except Exception as _re:
                logger.warning(f"AdminRAG: query rewrite failed ({_re})")

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
            ids0 = (results.get("ids") or [[None]*len(results["documents"][0])])[0]
            for cid, doc, meta, dist in zip(ids0, results["documents"][0], results["metadatas"][0], dists):
                cands.append({"doc": doc, "label": label,
                              "title": (meta or {}).get("title", ""),
                              "category": (meta or {}).get("category", ""),
                              "dist": dist, "cid": cid})

        # 1a') POOL-UNION (query rewriting): отдельный плотный поиск по КАЖДОМУ
        # варианту рерайта, слияние пулов кандидатов (dedup по cid). Реранк
        # остаётся по ИСХОДНОМУ query. НЕ заменяет, а ДОБАВЛЯет — raw-попадание
        # не теряется.
        if _aux_list and u2_active and qemb is not None:
            _seen = {c.get("cid") for c in cands}
            try:
                for _aq in _aux_list:
                    aemb = u2.encode([_aq], prompt_name="search_query",
                                     convert_to_numpy=True)[0].tolist()
                    for coll_name in collections:
                        coll = _u2_collection(coll_name)
                        if coll is None:
                            continue
                        ares = coll.query(query_embeddings=[aemb],
                                          n_results=min(fetch_k, coll.count()),
                                          include=["documents", "metadatas", "distances"])
                        if not ares["documents"] or not ares["documents"][0]:
                            continue
                        label = COLLECTION_LABELS.get(coll_name, coll_name)
                        adists = (ares.get("distances") or [[None]*len(ares["documents"][0])])[0]
                        aids = (ares.get("ids") or [[None]*len(ares["documents"][0])])[0]
                        for cid, doc, meta, dist in zip(aids, ares["documents"][0],
                                                        ares["metadatas"][0], adists):
                            if cid in _seen:
                                continue
                            _seen.add(cid)
                            cands.append({"doc": doc, "label": label,
                                          "title": (meta or {}).get("title", ""),
                                          "category": (meta or {}).get("category", ""),
                                          "dist": dist, "cid": cid, "is_aux": True})
            except Exception as _e:
                logger.warning(f"AdminRAG: pool-union aux retrieval failed ({_e})")

        # 1b) ГИБРИД (аддитивный): лексический канал (BM25/FTS5) только ДОБАВЛЯет в пул
        # кандидатов, которых плотный USER2 не нашёл. Плотный канал промахивается на
        # enforcement-формулировках, где профильная статья ГК сформулирована
        # академически («уменьшить неустойку» vs запрос «снижение неустойки»; «по
        # договору займа» под ворохом практики) — лексика ловит ключевые слова и
        # подаёт нужный кодекс в пул. ВАЖНО: плотные кандидаты НЕ трогаем (раньше
        # перезапись dist=-RRF топила семантику и давала регресс на «директоре»).
        # Лексические добиратели входят с худшим вектор-скором, но с полным правом на
        # реранк DiTy + бонус кодексу + диверсификацию. Флаг RAG_HYBRID (по умолч. вкл).
        # ВАЖНО — инъекция ТОЛЬКО кодексов (kodeks/ФКЗ). Диагностика на A–E показала:
        # промахи неустойка/заём/расписка — это retrieval-промахи (нужная статья ГК
        # вообще не попадает в плотный пул, диверсификация бессильна), и достаёт её
        # лишь лексика. А весь шум прошлого «широкого» гибрида был от инъекции НЕ-
        # кодексов (129-ФЗ для контрафакта, обзоры) — они вытесняли верный код.
        # Ограничение инъекции кодексами убирает шум, оставляя спасение статьи кодекса.
        # Вместе с grab_pref (профильный код гарантированно получает слот) это даёт
        # чистый прирост без регресса.
        if os.environ.get("RAG_HYBRID", "1") == "1":
            lex = _fts_search(query, k=fetch_k)
            if lex:
                by_cid = {c["cid"] for c in cands}
                worst = max((c["dist"] for c in cands if c["dist"] is not None),
                            default=1.0)
                # Дедуп по документу: впрыскиваем НЕ БОЛЕЕ 1 чанка на код. Иначе
                # лексика на одно тангенциальное слово («супруг» → НК) тащит 4 чанка
                # одного кодекса и затапливает верный код (СК), который плотный нашёл.
                # С 1 чанком профильный код по score (grab_pref) переигрывает добор.
                lex_titles = set()
                for cid, text, title, cat, coll in lex:
                    if (cid in by_cid
                            or cat not in ("kodeks", "federal_constitutional_law")
                            or title in lex_titles):
                        continue
                    lbl = COLLECTION_LABELS.get("laws" if coll == "laws" else "case_law", coll)
                    cands.append({"doc": text, "label": lbl, "title": title,
                                  "category": cat, "dist": worst, "cid": cid})
                    by_cid.add(cid); lex_titles.add(title)

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
        # raw-кандидаты получают бонус, чтобы aux не вытеснял при случайном реранк-шуме.
        AUX_PEN = float(os.environ.get("RAG_AUX_PENALTY", "0.05"))
        for i, c in enumerate(cands):
            raw_bonus = 0.0 if c.get("is_aux") else AUX_PEN
            c["score"] = VEC_W * vsc[i] + RR_W * rsc[i] + CODE_BONUS.get(c["category"], 0.0) + raw_bonus
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
        def _is_proc(c):
            # Процессуальные кодексы (ГПК/АПК/УПК/КАС) — это «как судиться», а не
            # материальная норма, которой обычно отвечают на правовой вопрос.
            t = (c.get("title") or "").lower()
            return "процессуальн" in t or "административного судопроизводств" in t
        def grab_pref(pred_pref, pred_any):
            for i in order:
                if i not in picked and pred_pref(cands[i]):
                    picked.append(i); return
            for i in order:
                if i not in picked and pred_any(cands[i]):
                    picked.append(i); return
        if n_results >= 2:
            # Профильный (субстантивный) кодекс важнее процессуального. На enforcement-
            # запросах («взыскать долг», «снижение неустойки судом», «кто возмещает
            # ущерб») плотный ранжировал ГПК и обзоры ВС выше профильной статьи ГК, и
            # единственный слот кодекса доставался процессуальному. Берём субстантивный
            # кодекс, если он есть в пуле; иначе любой (вкл. процессуальный — тогда тема
            # действительно процессуальная). Процессуальные вопросы не страдают: их ГПК/
            # АПК и так попадает в выдачу по score через добор оставшихся слотов.
            grab_pref(lambda c: c["category"] == "kodeks" and not _is_proc(c),
                      lambda c: c["category"] == "kodeks")
            grab(lambda c: c["label"] == "Судебная практика")
        # Кап ≤2 слота на один документ. Некоторые объёмные документы (НК ч.2,
        # бюджетные ФЗ) ведут себя как embedding-хабы и затапливают выдачу одним
        # документом (на «разводе» плотный давал НК ч.2 ×4, вытесняя СК). Ограничение
        # на дубли одного title освобождает слоты для других профильных норм/практики
        # — generic-приём против hub-flood, без побочных эффектов для остальных тем.
        def _tkey(i):
            return cands[i].get("title") or cands[i]["label"]
        tcount = {}
        for i in picked:
            tcount[_tkey(i)] = tcount.get(_tkey(i), 0) + 1
        for i in order:
            if len(picked) >= n_results:
                break
            if i in picked:
                continue
            k = _tkey(i)
            if tcount.get(k, 0) >= 2:
                continue
            picked.append(i); tcount[k] = tcount.get(k, 0) + 1
        picked = sorted(picked[:n_results], key=lambda i: -cands[i]["score"])

        # 4) В контекст
        parts = []
        for i in picked:
            c = cands[i]; t = c["title"]
            header = f"[{c['label']}] — {t}" if t else f"[{c['label']}]"
            parts.append(f"{header}\n{c['doc'][:600]}")

        context = "\n\n".join(parts)
        # Обрезаем БАЗУ до бюджета ДО дописывания связанных норм: иначе при
        # прод-лимите (max_chars=2000) hop-нормы всегда отрезаются с конца.
        # Сами нормы капованы в _graph_hop_text (2 x 700 симв).
        if len(context) > max_chars:
            context = context[:max_chars] + "..."
        _hop = os.environ.get("RAG_GRAPH_HOP", "").strip() in ("1", "true", "True")
        if not _hop:
            try:
                from config.settings import settings as _gs
                _hop = bool(getattr(_gs, "rag_graph_hop", False))
            except Exception:
                _hop = False
        if _hop:
            _ex = _graph_hop_text(query, qemb, context)
            if _ex:
                context = context + "\n\n" + _ex
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
