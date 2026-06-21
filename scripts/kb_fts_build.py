# -*- coding: utf-8 -*-
"""Строит лексический FTS5-индекс (BM25) по тем же чанкам, что в ChromaDB
laws_u2/case_law_u2 — для гибридного поиска (плотный USER2 + лексический BM25).

Плотный эмбеддер промахивается на enforcement-формулировках («взыскание
задолженности по займу»), где нужная статья ГК сформулирована академически;
лексический канал ловит её по буквальному совпадению ключевых слов.

Идемпотентно: пересоздаёт таблицу chunks_fts заново. Источник чанков — сами
u2-коллекции (id/doc_id/title/category/text), чтобы id совпадали с плотным каналом.

  kb_fts_build.py                      # полный пересбор
"""
import os, sys, time, sqlite3
os.environ.setdefault("HF_HUB_OFFLINE", "1"); os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

CHROMA = "/Users/legalai/projects/Contract-AI-System-/data/chromadb"
FTS_DB = "/Users/legalai/projects/Contract-AI-System-/data/chromadb/lexical_fts.db"
PAGE = 10000


def build():
    import chromadb
    from chromadb.config import Settings
    cl = chromadb.PersistentClient(path=CHROMA, settings=Settings(anonymized_telemetry=False))

    con = sqlite3.connect(FTS_DB)
    con.execute("DROP TABLE IF EXISTS chunks_fts")
    # unicode61 + remove_diacritics: нормализация регистра/диакритики. Русской
    # морфологии в FTS5 нет — компенсируем префиксными запросами на стороне поиска.
    con.execute(
        "CREATE VIRTUAL TABLE chunks_fts USING fts5("
        "chunk_id UNINDEXED, doc_id UNINDEXED, title, category UNINDEXED, coll UNINDEXED, "
        "text, tokenize='unicode61 remove_diacritics 2')"
    )
    total = 0
    for coll_name in ("laws_u2", "case_law_u2"):
        try:
            coll = cl.get_or_create_collection(coll_name)
        except Exception as e:
            print(f"нет коллекции {coll_name}: {e}"); continue
        n = coll.count()
        short = "laws" if coll_name == "laws_u2" else "case_law"
        print(f"=== {coll_name}: {n} чанков ===", flush=True)
        off = 0; t0 = time.time()
        while off < n:
            b = coll.get(limit=PAGE, offset=off, include=["documents", "metadatas"])
            ids = b["ids"]; docs = b["documents"]; metas = b["metadatas"]
            rows = []
            for cid, doc, m in zip(ids, docs, metas):
                m = m or {}
                rows.append((cid, str(m.get("doc_id", "")), m.get("title", ""),
                             m.get("category", ""), short, doc or ""))
            con.executemany(
                "INSERT INTO chunks_fts(chunk_id,doc_id,title,category,coll,text) "
                "VALUES (?,?,?,?,?,?)", rows)
            con.commit()
            off += PAGE; total += len(rows)
            print(f"  {min(off,n)}/{n}  ({time.time()-t0:.0f}s)", flush=True)
    con.execute("INSERT INTO chunks_fts(chunks_fts) VALUES('optimize')")
    con.commit(); con.close()
    print(f"ГОТОВО: {total} чанков в FTS → {FTS_DB}", flush=True)


if __name__ == "__main__":
    build()
