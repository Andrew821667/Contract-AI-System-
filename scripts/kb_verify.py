#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Проверка БЗ после kb_update.sh без изменений исходных файлов и сторов.

SQLite графа читается с mode=ro, без длинной транзакции на весь прогон.
Chroma открывает рабочий каталог; используются только get_collection
и get(where=..., limit=1, include=[]).
"""
from __future__ import annotations

import argparse
import ast
import contextlib
import glob
import importlib.util
import io
import json
import re
import sqlite3
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
LAW_ID = re.compile(r"cons_doc_LAW_(\d+)")
CHECK_IDS = ("status", "dedup", "pending", "kodeksy", "archive", "integrity", "index")


def _dedup():
    spec = importlib.util.spec_from_file_location(
        "kb_dedup_editions", ROOT / "scripts/kb_dedup_editions.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _kodeksy():
    """Читаем список без импорта загрузчика: его импорт создаёт каталог и лог."""
    path = ROOT / "tools/consultant/modules/kodeksy.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
                isinstance(t, ast.Name) and t.id == "KODEKSY" for t in node.targets):
            return [(name, LAW_ID.search(url).group(1))
                    for name, url in ast.literal_eval(node.value)]
    raise ValueError("не найден список KODEKSY")


def _connect(path):
    con = sqlite3.connect(Path(path).resolve().as_uri() + "?mode=ro",
                          uri=True, timeout=2)
    con.execute("PRAGMA query_only = ON")
    return con


def _docid(path):
    """LAW id из source_url во frontmatter; None, если его нет."""
    with Path(path).open(encoding="utf-8") as fh:
        if fh.readline().strip() != "---":
            return None
        for line in fh:
            if line.strip() == "---":
                break
            if line.startswith("source_url:") and (m := LAW_ID.search(line)):
                return m.group(1)
    return None


def _result(key, name, ok, details, **extra):
    return {"id": key, "name": name, "status": "OK" if ok else "FAIL",
            "details": details, **extra}


def _status(data):
    path = data / "kb_update_status.json"
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(f"ожидался объект JSON: {path}")
    state = raw.get("state")
    msg = f"state={state}; {raw.get('message', '')}"
    if state == "warning" and raw.get("warnings"):
        msg += f"; предупреждения: {raw['warnings']}"
    return _result("status", "Статус прогона", state in ("ok", "warning"), msg)


def _duplicates(dedup, sources):
    # plan печатает группы дублей; отчёт должен содержать ровно строки проверок.
    with contextlib.redirect_stdout(io.StringIO()):
        losers, _ = dedup.plan(sources=sources)
    files = [it["f"] for it in losers[:10]]
    return _result("dedup", "Дедуп редакций", not losers,
                   f"лишних файлов: {len(losers)}"
                   + ("; первые 10: " + "; ".join(files) if files else ""),
                   files=files, count=len(losers))


def _pending(data):
    path = data / "refs/pending_docids.txt"
    ids = path.read_text(encoding="utf-8").split() if path.exists() else []
    return _result("pending", "Очередь обновления", not ids,
                   f"ожидают обновления: {len(ids)}"
                   + ("; " + ", ".join(ids) if ids else ""))


def _graph_ids(db):
    with contextlib.closing(_connect(db)) as con:
        rows = con.execute("SELECT source_file FROM graph_documents").fetchall()
    return {m.group(1) for (src,) in rows
            for m in re.finditer(r"cons_doc_LAW_(\d+)/", src or "")}


def _integrity(db):
    with contextlib.closing(_connect(db)) as con:
        orphans = con.execute("""
            SELECT COUNT(*) FROM graph_edges e
            LEFT JOIN graph_nodes s ON s.id = e.source_id
            LEFT JOIN graph_nodes t ON t.id = e.target_id
            WHERE s.id IS NULL OR t.id IS NULL
        """).fetchone()[0]
        # Семантика scripts/graph_recount_stats.py: узлы только неархивные,
        # рёбра — все исходящие, в том числе от архивных и между документами.
        # Там SQL внутри main() с SessionLocal и записью во временные таблицы;
        # импортируемой функции чтения нет. Здесь те же агрегации через CTE.
        diff = con.execute("""
            WITH nodes AS (
                SELECT document_id AS doc_id, COUNT(*) AS cnt
                FROM graph_nodes
                WHERE is_archived = 0 AND document_id IS NOT NULL
                GROUP BY document_id
            ), edges AS (
                SELECT n.document_id AS doc_id, COUNT(*) AS cnt
                FROM graph_nodes n JOIN graph_edges e ON e.source_id = n.id
                WHERE n.document_id IS NOT NULL
                GROUP BY n.document_id
            )
            SELECT COUNT(*) FROM graph_documents d
            LEFT JOIN nodes n ON n.doc_id = d.id
            LEFT JOIN edges e ON e.doc_id = d.id
            WHERE d.nodes_count IS NOT COALESCE(n.cnt, 0)
               OR d.edges_count IS NOT COALESCE(e.cnt, 0)
        """).fetchone()[0]
    return _result("integrity", "Целостность графа", orphans == diff == 0,
                   f"осиротевших рёбер: {orphans}; документов с расхождением "
                   f"счётчиков: {diff}", orphan_edges=orphans, counter_mismatches=diff)


def _index(db):
    with contextlib.closing(_connect(db)) as con:
        exists = any(row[1] == "ix_graph_nodes_number"
                     for row in con.execute("PRAGMA index_list(graph_nodes)"))
        plan = [row[3] for row in con.execute(
            "EXPLAIN QUERY PLAN SELECT id FROM graph_nodes WHERE number = '1'")]
    used = any(re.search(r"USING (?:COVERING )?INDEX ix_graph_nodes_number\b", s)
               for s in plan)
    return _result("index", "Индекс номеров узлов", exists and used,
                   f"ix_graph_nodes_number: {'есть' if exists else 'нет'}; "
                   + "; ".join(plan), query_plan=plan)


class _Vectors:
    """Чтение метаданных из рабочего каталога Chroma через get_collection и get."""

    def __init__(self, path, no_chroma):
        self.client = None
        self.cols = {}
        self.reason = ""
        self.error = ""
        self.errors = (OSError, sqlite3.Error, ValueError, RuntimeError)
        if no_chroma:
            self.reason = "задан --no-chroma"
            return
        try:
            import chromadb
            from chromadb.config import Settings
        except ImportError as exc:
            self.reason = f"chromadb недоступен: {exc}"
            return
        try:
            from chromadb.errors import ChromaError
        except ImportError:
            # Старый клиент или тестовая подмена без отдельного модуля ошибок.
            ChromaError = RuntimeError
        self.errors += (ChromaError,)
        try:
            self.client = chromadb.PersistentClient(
                path=str(path), settings=Settings(anonymized_telemetry=False))
        except self.errors as exc:
            self.error = f"не удалось прочитать Chroma: {exc}"

    def has(self, name, docid):
        if self.error:
            raise ValueError(self.error)
        if name not in self.cols:
            # get_or_create недопустим: отсутствие коллекции — ошибка проверки.
            self.cols[name] = self.client.get_collection(name, embedding_function=None)
        got = self.cols[name].get(where={"doc_id": docid}, limit=1, include=[])
        return bool(got["ids"])


def _stores(key, name, missing, graph_ok, vectors):
    """Общий статус сохраняет FAIL графа даже при пропуске векторов."""
    parts = {"graph": "OK" if graph_ok else "FAIL",
             "chroma": "SKIP" if vectors.reason else "OK"}
    if vectors.reason:
        missing.append(f"векторы SKIP: {vectors.reason}")
    row = _result(key, name, graph_ok,
                  "; ".join(missing) or "граф и векторы в порядке", parts=parts)
    if graph_ok and vectors.reason:
        row["status"] = "SKIP"
    return row


def _codes(graph_ids, graph_error, vectors):
    missing = []
    graph_ok = not graph_error
    if graph_error:
        missing.append(graph_error)
    row = _stores("kodeksy", "Кодексы", missing, graph_ok, vectors)
    for name, docid in _kodeksy():
        if graph_ids is not None and docid not in graph_ids:
            missing.append(f"{name} (LAW {docid}): нет в графе")
            row["parts"]["graph"] = "FAIL"
        if not vectors.reason:
            for coll in ("laws", "laws_u2"):
                try:
                    if vectors.has(coll, docid):
                        continue
                    msg = "нет векторов"
                except vectors.errors as exc:
                    msg = str(exc)
                missing.append(f"{name} (LAW {docid}), {coll}: {msg}")
                row["parts"]["chroma"] = "FAIL"
    return _finish_stores(row, missing)


def _finish_stores(row, issues):
    if "FAIL" in row["parts"].values():
        row["status"] = "FAIL"
    row["details"] = "; ".join(issues) or "граф и векторы в порядке"
    row["issues"] = issues
    return row


def _archive(data, sources, graph_ids, graph_error, vectors):
    # Живым считается любой файл SOURCES, даже если у него нет date/number
    # для дедупа или он сам пока входит в losers.
    live = {docid for pat, _, _ in sources for f in glob.glob(str(pat))
            if (docid := _docid(f)) is not None}
    ids = set()
    for path in sorted((data / "archive-editions").rglob("*.md")):
        docid = _docid(path)
        if docid is not None and docid not in live:
            rel = path.relative_to(data / "archive-editions")
            colls = (("case_law", "case_law_u2") if rel.parts[0] == "court-practice"
                     else ("laws", "laws_u2"))
            ids.update((docid, coll) for coll in colls)
    issues = [graph_error] if graph_error else []
    row = _stores("archive", "Архив редакций", issues, not graph_error, vectors)
    for docid in sorted({did for did, _ in ids}):
        if graph_ids is not None and docid in graph_ids:
            issues.append(f"LAW {docid}: остался в графе")
            row["parts"]["graph"] = "FAIL"
    if not vectors.reason:
        for docid, coll in sorted(ids):
            try:
                if not vectors.has(coll, docid):
                    continue
                msg = "остался в векторах"
            except vectors.errors as exc:
                msg = str(exc)
            issues.append(f"LAW {docid}, {coll}: {msg}")
            row["parts"]["chroma"] = "FAIL"
    return _finish_stores(row, issues)


def main(argv=None):
    dedup = _dedup()
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--data", type=Path, default=dedup.BASE, help="каталог выгрузки К+")
    ap.add_argument("--db", type=Path, default=dedup.DB, help="SQLite графа")
    ap.add_argument("--chroma", type=Path, default=dedup.CHROMA, help="каталог Chroma")
    ap.add_argument("--json", action="store_true", help="машиночитаемый отчёт")
    ap.add_argument("--no-chroma", action="store_true", help="пропустить векторы")
    ap.add_argument("--skip", default="", metavar="ID[,ID...]",
                    help="пропустить проверки: " + ", ".join(CHECK_IDS))
    args = ap.parse_args(argv)
    skip = set(args.skip.split(",")) if args.skip else set()
    if unknown := skip - set(CHECK_IDS):
        ap.error("неизвестные ID проверок: " + ", ".join(sorted(unknown)))
    data, db, chroma = (p.expanduser() for p in (args.data, args.db, args.chroma))
    sources = [(data / pat.relative_to(dedup.BASE), colls, arch)
               for pat, colls, arch in dedup.SOURCES]
    rows = []

    def run(key, name, fn, *params):
        if key in skip:
            rows.append({"id": key, "name": name, "status": "SKIP",
                         "details": "пропущена по --skip"})
            return
        try:
            rows.append(fn(*params))
        except (OSError, ValueError, sqlite3.Error) as exc:
            rows.append(_result(key, name, False, str(exc)))

    run("status", "Статус прогона", _status, data)
    run("dedup", "Дедуп редакций", _duplicates, dedup, sources)
    run("pending", "Очередь обновления", _pending, data)
    graph_ids, graph_error = None, ""
    vectors = None
    if {"kodeksy", "archive"} - skip:
        try:
            graph_ids = _graph_ids(db)
        except (OSError, sqlite3.Error) as exc:
            graph_error = f"граф недоступен: {exc}"
        vectors = _Vectors(chroma, args.no_chroma)
    run("kodeksy", "Кодексы", _codes, graph_ids, graph_error, vectors)
    run("archive", "Архив редакций", _archive, data, sources,
        graph_ids, graph_error, vectors)
    run("integrity", "Целостность графа", _integrity, db)
    run("index", "Индекс номеров узлов", _index, db)
    ok = all(row["status"] != "FAIL" for row in rows)
    if args.json:
        print(json.dumps({"ok": ok, "checks": rows}, ensure_ascii=False))
    else:
        for row in rows:
            details = " ".join(row["details"].splitlines())
            print(f"{row['status']} {row['name']}: {details}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
