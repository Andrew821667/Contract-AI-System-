# -*- coding: utf-8 -*-
"""Дедуп редакций НПА: одна актуальная редакция на закон во всех сторах.

Корень проблемы: в К+ у КАЖДОЙ РЕДАКЦИИ свой doc_id. Добор (federal_laws --all)
видит в каталоге актуальную редакцию с новым doc_id/заголовком и качает её как
НОВЫЙ файл, а edition_check ходит по СТАРОМУ doc_id (К+ отдаёт тот же снапшот →
«изменений нет») и смену не флагает. Итог: в md-корпусе, графе, chroma и FTS
сосуществуют несколько редакций одного закона, и ретривер может отдать
устаревшую (аудит 2026-07-11: 65 законов с дублями, 69 лишних файлов).

Что делает:
  1) группирует md по идентичности акта: кодексы и ФЗ/ФКЗ — date + number из
     frontmatter, подзаконка и судебная практика — вид, орган, дата и номер
     из заголовка;
  2) в группе >1 файла оставляет свежайшую редакцию («ред. от», затем «с изм.
     от»; tie-break: больший doc_id = более поздний снапшот К+), остальные
     ПЕРЕНОСИТ в archive-editions/;
  3) их doc_id вычищает из графа (SQL-каскад: edges → entities → nodes → doc,
     повторяет consultant_importer._purge_by_source) и из chroma (laws +
     laws_u2 или case_law + case_law_u2, delete по метадате doc_id);
  4) новая редакция под прежним doc_id (так К+ обновляет кодексы и, похоже,
     постановления) — doc_id в refs/pending_docids.txt: граф и векторы по нему
     обновит kb_update.sh;
  5) пишет манифест refs/purged_docids_<дата>.txt.

FTS НЕ трогает — пересборка kb_fts_build.py идёт отдельным шагом пайплайна
(kb_update.sh 4b) уже после дедупа. Файлы не удаляются, только архивируются.

Запуск: .venv/bin/python scripts/kb_dedup_editions.py [--dry-run]
"""
import argparse
import collections
import datetime
import glob
import os
import re
import shutil
import sqlite3
from pathlib import Path

BASE = Path("/Users/legalai/consultant-data")
KS = Path("/Users/legalai/projects/Contract-AI-System-")
# (шаблон, коллекции chroma, архив). Кодексы и ФЗ/ФКЗ — идентичность из
# frontmatter (date, number), архив плоский: federal_laws не перекачивает
# редакцию, файл которой лежит в archive-editions/. Подзаконка и практика
# frontmatter date/number не пишут — идентичность из заголовка; без этого
# дедуп их не видел (24.10.2026: у 10 постановлений по 2–7 редакций разом,
# ПП N 353 — семь, с 15.04 по 23.09.2026). Архив — по подпапкам: в разных
# папках практики одинаковые имена файлов.
SOURCES = [
    (BASE / "kodeksy/converted-md/*.md", ("laws", "laws_u2"), None),
    (BASE / "federal-laws/fkz/converted-md/*.md", ("laws", "laws_u2"), None),
    (BASE / "federal-laws/fz/converted-md/*.md", ("laws", "laws_u2"), None),
    (BASE / "decrees/converted-md/*.md", ("laws", "laws_u2"), "decrees"),
    (BASE / "court-practice/*/converted-md/*.md", ("case_law", "case_law_u2"), "court-practice"),
]
ARCHIVE = BASE / "archive-editions"
DB = KS / "contract_ai.db"
CHROMA = KS / "data/chromadb"
# Изменённые здесь документы с тем же doc_id (новая редакция под прежним
# номером К+): граф и векторы по ним обновит kb_update.sh (шаги 3b, 4).
PENDING = BASE / "refs" / "pending_docids.txt"

_DATE = r"(\d{2})\.(\d{2})\.(\d{4})"
# «… от 20.04.2006 N 8 …» и «… N 90, Пленума ВАС РФ N 14 от 09.12.1999»
_REQ_DN = re.compile(r"от\s+(\d{2}\.\d{2}\.\d{4})\s+N\s*([^\s,()\"]+)")
_REQ_ND = re.compile(r"N\s*([^\s,()\"]+)[^()]*?от\s+(\d{2}\.\d{2}\.\d{4})")
_ED = re.compile(r"ред\.\s*от\s*" + _DATE)
_IZM = re.compile(r"с\s+изм\.\s*от\s*" + _DATE)


def _head(path: str, n: int = 1500) -> str:
    with open(path, encoding="utf-8") as fh:
        return fh.read(n)


def _ymd(m):
    return (m.group(3), m.group(2), m.group(1)) if m else ("0", "0", "0")


def _meta(path: str, by_title: bool = False):
    """(ключ идентичности, ключ редакции, docid); None если идентичности нет.

    Ключ редакции — (дата «ред. от», дата «с изм. от»): у ПП N 353 две
    выгрузки под одним doc_id различаются только «с изм. от 08.07.2026».
    """
    h = _head(path)
    did = re.search(r"cons_doc_LAW_(\d+)", h)
    if not did:
        return None
    title = re.search(r"^title:\s*(.*)$", h, re.M)
    title = title.group(1) if title else ""
    izm = _ymd(_IZM.search(title))
    if not by_title:
        date = re.search(r"^date:\s*(\S+)", h, re.M)
        num = re.search(r"^number:\s*(\S+)", h, re.M)
        ed = re.search(r"^edition_date:\s*(\S*)", h, re.M)
        if not (date and num and date.group(1) and num.group(1)):
            return None
        edm = re.match(_DATE, (ed.group(1) if ed else "") or "")
        return (date.group(1), num.group(1)), (_ymd(edm), izm), did.group(1)
    head = re.sub(r"\s*\(ред\..*$", "", title)  # реквизиты — до «(ред. от …)»
    m = _REQ_DN.search(head)
    if m:
        date, num = m.group(1), m.group(2)
    else:
        m = _REQ_ND.search(head)
        if not m:
            return None  # обзоры и т.п. без номера — не группируем
        date, num = m.group(2), m.group(1)
    # вид и орган — всё до реквизитов: «постановление пленума верховного суда рф»
    kind = " ".join(head[:m.start()].lower().split())
    return (kind, date, num.rstrip(".").lower()), (_ymd(_ED.search(title)), izm), did.group(1)


def _purge_graph(con: sqlite3.Connection, docid: str) -> int:
    """Каскадное удаление документов графа с source_file по этому doc_id.

    Без фильтра по слою: практика лежит и в слое court (повторяет
    consultant_importer._purge_by_source — с версиями нод и кандидатами рёбер).
    """
    rows = con.execute(
        "SELECT id FROM graph_documents WHERE source_file LIKE ?",
        (f"%cons_doc_LAW_{docid}/%",)).fetchall()
    for (gid,) in rows:
        own = "(SELECT id FROM graph_nodes WHERE document_id=?)"
        for table, col in (("graph_edges", "source_id"), ("graph_edges", "target_id"),
                           ("candidate_edges", "source_id"), ("candidate_edges", "target_id"),
                           ("node_versions", "node_id"), ("graph_entities", "node_id")):
            con.execute(f"DELETE FROM {table} WHERE {col} IN {own}", (gid,))
        con.execute("DELETE FROM graph_nodes WHERE document_id=?", (gid,))
        con.execute("DELETE FROM graph_documents WHERE id=?", (gid,))
    return len(rows)


def _archive_path(it: dict) -> Path:
    f = Path(it["f"])
    if it["arch"] is None:
        return ARCHIVE / f.name
    if it["arch"] == "court-practice":  # court-practice/<slug>/converted-md/x.md
        return ARCHIVE / it["arch"] / f.parent.parent.name / f.name
    return ARCHIVE / it["arch"] / f.name


def plan(sources=None):
    """Что сделать: (losers — файлы старых редакций на архивацию с флагом
    purge «вычистить doc_id из сторов», refresh — doc_id новой редакции
    под прежним номером, по которым надо обновить граф и векторы)."""
    groups = collections.defaultdict(list)
    for pat, colls, arch in (sources or SOURCES):
        for f in glob.glob(str(pat)):
            m = _meta(f, by_title=arch is not None)
            if m:  # у подзаконки и практики — своё пространство ключей
                groups[(arch or "npa",) + m[0]].append(
                    {"f": f, "ed": m[1], "docid": m[2], "colls": colls, "arch": arch})

    losers = []
    refresh = set()
    for key, items in sorted(groups.items()):
        if len(items) < 2:
            continue
        items.sort(key=lambda x: (x["ed"], int(x["docid"]), os.path.getmtime(x["f"])),
                   reverse=True)
        keep = items[0]
        # Та же редакция того же документа в ДРУГОЙ папке практики (Пленум ВС
        # есть и в plenum_vs, и в vs_all) — не дубль: убери её в архив, и
        # добор перекачает файл через неделю — и так по кругу.
        rest = [it for it in items[1:]
                if not (it["docid"] == keep["docid"] and it["ed"] == keep["ed"]
                        and Path(it["f"]).parent != Path(keep["f"]).parent)]
        if not rest:
            continue
        print(f"[{' | '.join(key[1:])}] оставляю ред.{'.'.join(reversed(keep['ed'][0]))} "
              f"(id {keep['docid']}); в архив: {len(rest)}", flush=True)
        for it in rest:
            same = it["docid"] == keep["docid"]
            # тот же doc_id — из сторов не чистим (он же у оставшегося файла),
            # но если оставшийся новее — в сторах может лежать старый текст
            losers.append({**it, "purge": not same})
            if same and it["ed"] < keep["ed"]:
                refresh.add(keep["docid"])

    # doc_id, который остаётся у какого-то файла, из сторов не чистим: иначе
    # эмбед и ингест вернут его через неделю, и так по кругу
    loser_files = {it["f"] for it in losers}
    remaining = {it["docid"] for items in groups.values() for it in items
                 if it["f"] not in loser_files}
    for it in losers:
        if it["purge"] and it["docid"] in remaining:
            it["purge"] = False
    return losers, refresh


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true",
                    help="только показать, что будет сделано")
    a = ap.parse_args()

    losers, refresh = plan()
    print(f"\nлишних файлов: {len(losers)}, к вычистке из сторов: "
          f"{sum(1 for x in losers if x['purge'])}, к обновлению (тот же doc_id): {len(refresh)}")
    if a.dry_run or not losers:
        print("dry-run/нечего делать — стор не тронут")
        return

    # Порядок важен на случай сбоя посреди (database is locked и т.п.):
    # сначала задание на обновление, затем чистка сторов, и только потом
    # файлы — в архив. Пока файл на месте, следующий прогон увидит дубль и
    # повторит; перенеси его первым — устаревший текст остался бы в сторах
    # навсегда.
    if refresh:
        old = set(PENDING.read_text(encoding="utf-8").split()) if PENDING.exists() else set()
        PENDING.write_text("\n".join(sorted(old | refresh)) + "\n", encoding="utf-8")

    con = sqlite3.connect(str(DB), timeout=60)
    import chromadb
    from chromadb.config import Settings
    cl = chromadb.PersistentClient(path=str(CHROMA),
                                   settings=Settings(anonymized_telemetry=False))
    colls = {}

    purged_ids, g_docs, c_chunks = [], 0, 0
    for it in losers:
        if not it["purge"]:
            continue
        g_docs += _purge_graph(con, it["docid"])
        con.commit()
        for name in it["colls"]:
            col = colls.setdefault(name, cl.get_or_create_collection(name))
            got = col.get(where={"doc_id": it["docid"]}, include=[])
            if got["ids"]:
                col.delete(ids=got["ids"])
                c_chunks += len(got["ids"])
        purged_ids.append(it["docid"])
    con.close()
    for it in losers:
        dst = _archive_path(it)
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(it["f"], dst)

    stamp = datetime.date.today().isoformat()
    manifest = BASE / "refs" / f"purged_docids_{stamp}.txt"
    manifest.write_text("\n".join(purged_ids), encoding="utf-8")
    print(f"ГОТОВО: файлов в архив {len(losers)}, графовых доков удалено {g_docs}, "
          f"chroma-чанков удалено {c_chunks}, к обновлению {len(refresh)} "
          f"({PENDING.name}). Манифест: {manifest}")
    print("Дальше по пайплайну: kb_fts_build (FTS) и рестарт бэкенда (in-memory HNSW).")


if __name__ == "__main__":
    main()
