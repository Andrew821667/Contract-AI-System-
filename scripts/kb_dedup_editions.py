# -*- coding: utf-8 -*-
"""Дедуп редакций НПА: одна актуальная редакция на закон во всех сторах.

Корень проблемы: в К+ у КАЖДОЙ РЕДАКЦИИ свой doc_id. Добор (federal_laws --all)
видит в каталоге актуальную редакцию с новым doc_id/заголовком и качает её как
НОВЫЙ файл, а edition_check ходит по СТАРОМУ doc_id (К+ отдаёт тот же снапшот →
«изменений нет») и смену не флагает. Итог: в md-корпусе, графе, chroma и FTS
сосуществуют несколько редакций одного закона, и ретривер может отдать
устаревшую (аудит 2026-07-11: 65 законов с дублями, 69 лишних файлов).

Что делает:
  1) группирует md по идентичности закона (date + number из frontmatter);
  2) в группе >1 файла оставляет свежайшую редакцию (tie-break: больший doc_id
     = более поздний снапшот К+), остальные ПЕРЕНОСИТ в archive-editions/;
  3) их doc_id вычищает из графа (SQL-каскад: edges → entities → nodes → doc,
     повторяет consultant_importer._purge_by_source) и из chroma
     (laws + laws_u2, delete по метадате doc_id);
  4) пишет манифест refs/purged_docids_<дата>.txt.

FTS НЕ трогает — пересборка kb_fts_build.py идёт отдельным шагом пайплайна
(kb_update.sh 4b) уже после дедупа. Файлы не удаляются, только архивируются.

Запуск: .venv/bin/python scripts/kb_dedup_editions.py [--dry-run]
"""
import argparse
import collections
import datetime
import glob
import re
import shutil
import sqlite3
from pathlib import Path

BASE = Path("/Users/legalai/consultant-data")
KS = Path("/Users/legalai/projects/Contract-AI-System-")
MD_PATTERNS = [
    BASE / "kodeksy/converted-md/*.md",
    BASE / "federal-laws/fkz/converted-md/*.md",
    BASE / "federal-laws/fz/converted-md/*.md",
    BASE / "decrees/converted-md/*.md",
]
ARCHIVE = BASE / "archive-editions"
DB = KS / "contract_ai.db"
CHROMA = KS / "data/chromadb"


def _head(path: str, n: int = 900) -> str:
    with open(path, encoding="utf-8") as fh:
        return fh.read(n)


def _meta(path: str):
    """(date, number, edition_key, docid) из frontmatter; None если нет идентичности."""
    h = _head(path)
    date = re.search(r"^date:\s*(\S+)", h, re.M)
    num = re.search(r"^number:\s*(\S+)", h, re.M)
    ed = re.search(r"^edition_date:\s*(\S*)", h, re.M)
    did = re.search(r"cons_doc_LAW_(\d+)", h)
    if not (date and num and date.group(1) and num.group(1) and did):
        return None
    edm = re.match(r"(\d{2})\.(\d{2})\.(\d{4})", (ed.group(1) if ed else "") or "")
    edkey = (edm.group(3), edm.group(2), edm.group(1)) if edm else ("0", "0", "0")
    return date.group(1), num.group(1), edkey, did.group(1)


def _purge_graph(con: sqlite3.Connection, docid: str) -> int:
    """Каскадное удаление документов графа с source_file по этому doc_id."""
    rows = con.execute(
        "SELECT id FROM graph_documents WHERE layer='npa' AND source_file LIKE ?",
        (f"%cons_doc_LAW_{docid}/%",)).fetchall()
    for (gid,) in rows:
        con.execute("DELETE FROM graph_edges WHERE source_id IN "
                    "(SELECT id FROM graph_nodes WHERE document_id=?)", (gid,))
        con.execute("DELETE FROM graph_edges WHERE target_id IN "
                    "(SELECT id FROM graph_nodes WHERE document_id=?)", (gid,))
        con.execute("DELETE FROM graph_entities WHERE node_id IN "
                    "(SELECT id FROM graph_nodes WHERE document_id=?)", (gid,))
        con.execute("DELETE FROM graph_nodes WHERE document_id=?", (gid,))
        con.execute("DELETE FROM graph_documents WHERE id=?", (gid,))
    return len(rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true",
                    help="только показать, что будет сделано")
    a = ap.parse_args()

    groups = collections.defaultdict(list)
    for pat in MD_PATTERNS:
        for f in glob.glob(str(pat)):
            m = _meta(f)
            if m:
                groups[(m[0], m[1])].append({"f": f, "ed": m[2], "docid": m[3]})

    losers = []  # файлы старых редакций на архивацию
    for key, items in sorted(groups.items()):
        if len(items) < 2:
            continue
        items.sort(key=lambda x: (x["ed"], int(x["docid"])), reverse=True)
        keep, rest = items[0], items[1:]
        kept_docid = keep["docid"]
        print(f"[{key[0]} N {key[1]}] оставляю ред.{'.'.join(reversed(keep['ed']))} "
              f"(id {kept_docid}); в архив: {len(rest)}", flush=True)
        for it in rest:
            # тот же doc_id у обоих файлов (полный дубль) — файл в архив,
            # но из сторов doc_id НЕ чистим: он же у оставшегося файла.
            losers.append({**it, "purge": it["docid"] != kept_docid})

    print(f"\nгрупп с дублями: обработано, лишних файлов: {len(losers)}, "
          f"к вычистке из сторов: {sum(1 for x in losers if x['purge'])}")
    if a.dry_run or not losers:
        print("dry-run/нечего делать — стор не тронут")
        return

    ARCHIVE.mkdir(exist_ok=True)
    con = sqlite3.connect(str(DB), timeout=60)
    import chromadb
    from chromadb.config import Settings
    cl = chromadb.PersistentClient(path=str(CHROMA),
                                   settings=Settings(anonymized_telemetry=False))
    colls = [cl.get_or_create_collection(n) for n in ("laws", "laws_u2")]

    purged_ids, g_docs, c_chunks = [], 0, 0
    for it in losers:
        shutil.move(it["f"], ARCHIVE / Path(it["f"]).name)
        if not it["purge"]:
            continue
        g_docs += _purge_graph(con, it["docid"])
        for col in colls:
            got = col.get(where={"doc_id": it["docid"]}, include=[])
            if got["ids"]:
                col.delete(ids=got["ids"])
                c_chunks += len(got["ids"])
        purged_ids.append(it["docid"])
    con.commit()
    con.close()

    stamp = datetime.date.today().isoformat()
    manifest = BASE / "refs" / f"purged_docids_{stamp}.txt"
    manifest.write_text("\n".join(purged_ids), encoding="utf-8")
    print(f"ГОТОВО: файлов в архив {len(losers)}, графовых доков удалено {g_docs}, "
          f"chroma-чанков удалено {c_chunks}. Манифест: {manifest}")
    print("Дальше по пайплайну: kb_fts_build (FTS) и рестарт бэкенда (in-memory HNSW).")


if __name__ == "__main__":
    main()
