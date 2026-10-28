# -*- coding: utf-8 -*-
"""Проверка БЗ на временных файлах, без сети и настоящего Chroma-клиента."""
import importlib.util
import json
import os
import sqlite3
import subprocess
import sys
import types
from pathlib import Path

import pytest


class _ChromaError(Exception):
    """Ошибка API Chroma, которая не наследуется от ValueError."""


_SPEC = importlib.util.spec_from_file_location(
    "kb_verify", Path(__file__).parent.parent / "scripts/kb_verify.py")
verify = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(verify)


def _md(path, docid, extra=""):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"---\ntitle: Документ {docid}\n"
        f"source_url: https://www.consultant.ru/document/cons_doc_LAW_{docid}/\n"
        f"{extra}---\n\nТекст документа.\n", encoding="utf-8")


@pytest.fixture
def kb(tmp_path, monkeypatch):
    data = tmp_path / "данные"
    data.mkdir()
    (data / "kb_update_status.json").write_text('{"state": "ok"}', encoding="utf-8")
    db = tmp_path / "граф #1.db"
    with sqlite3.connect(db) as con:
        con.executescript("""
            CREATE TABLE graph_documents (
                id TEXT PRIMARY KEY, source_file TEXT,
                nodes_count INTEGER, edges_count INTEGER
            );
            CREATE TABLE graph_nodes (
                id TEXT PRIMARY KEY, document_id TEXT NOT NULL,
                number TEXT, is_archived INTEGER
            );
            CREATE TABLE graph_edges (
                id TEXT PRIMARY KEY, source_id TEXT NOT NULL, target_id TEXT NOT NULL
            );
            CREATE INDEX ix_graph_nodes_document_id ON graph_nodes(document_id);
            CREATE INDEX ix_graph_nodes_number ON graph_nodes(number);
            CREATE INDEX ix_graph_edges_source_id ON graph_edges(source_id);
            CREATE INDEX ix_graph_edges_target_id ON graph_edges(target_id);
        """)
        con.execute("PRAGMA journal_mode = WAL")
        # Настоящий список, включая все части ГК/НК, без импорта загрузчика.
        codes = verify._kodeksy()
        for i, (_, docid) in enumerate(codes):
            con.execute("INSERT INTO graph_documents VALUES (?, ?, 1, 0)",
                        (docid, f"https://example.test/cons_doc_LAW_{docid}/"))
            con.execute("INSERT INTO graph_nodes VALUES (?, ?, '1', 0)",
                        (f"узел-{i}", docid))

    chroma_dir = tmp_path / "chroma"
    chroma_dir.mkdir()
    vectors = {name: {docid for _, docid in codes} if name.startswith("laws") else set()
               for name in ("laws", "laws_u2", "case_law", "case_law_u2")}
    calls = []

    class Collection:
        def __init__(self, name):
            self.name = name

        def get(self, *, where, limit, include):
            assert limit == 1 and include == []
            assert isinstance(where["doc_id"], str)
            calls.append((self.name, where["doc_id"]))
            return {"ids": ["чанк"] if where["doc_id"] in vectors[self.name] else []}

    class Client:
        def __init__(self, *, path, settings):
            assert Path(path) == chroma_dir
            assert settings == {"anonymized_telemetry": False}

        def get_collection(self, name, embedding_function):
            assert embedding_function is None
            if name not in vectors:
                raise _ChromaError(f"нет коллекции {name}")
            return Collection(name)

    chroma = types.ModuleType("chromadb")
    chroma.PersistentClient = Client
    cfg = types.ModuleType("chromadb.config")
    cfg.Settings = lambda **kw: kw
    errors = types.ModuleType("chromadb.errors")
    errors.ChromaError = _ChromaError
    monkeypatch.setitem(sys.modules, "chromadb", chroma)
    monkeypatch.setitem(sys.modules, "chromadb.config", cfg)
    monkeypatch.setitem(sys.modules, "chromadb.errors", errors)
    return types.SimpleNamespace(data=data, db=db, chroma=chroma_dir,
                                 vectors=vectors, calls=calls)


def _run(kb, capsys, *flags):
    code = verify.main(["--data", str(kb.data), "--db", str(kb.db),
                        "--chroma", str(kb.chroma), "--json", *flags])
    report = json.loads(capsys.readouterr().out)
    assert len(report["checks"]) == 7
    return code, {row["id"]: row for row in report["checks"]}


def test_clean_returns_zero(kb, capsys):
    """Архивный doc_id жив в SOURCES без реквизитов дедупа — удалять его нельзя."""
    _md(kb.data / "archive-editions/старый.md", "5142")
    _md(kb.data / "kodeksy/converted-md/живой.md", "5142")
    with sqlite3.connect(kb.db) as con:
        # Архивный узел не входит в nodes_count, его исходящее ребро входит.
        con.execute("INSERT INTO graph_nodes VALUES ('архивный', '5142', '2', 1)")
        con.execute("INSERT INTO graph_edges VALUES ('связь', 'архивный', 'узел-1')")
        con.execute("UPDATE graph_documents SET edges_count=1 WHERE id='5142'")
    before = {p: p.read_bytes() for p in kb.data.rglob("*") if p.is_file()}
    before[kb.db] = kb.db.read_bytes()
    code, rows = _run(kb, capsys)
    assert code == 0
    assert all(row["status"] == "OK" for row in rows.values())
    assert all(p.read_bytes() == raw for p, raw in before.items())
    assert len(kb.calls) == 2 * len(verify._kodeksy())


@pytest.mark.parametrize("text", [
    "---\ntitle: Документ без ссылки\n---\n\nТекст.\n",
    "---\nsource_url: https://example.test/document/\n---\n\nТекст.\n",
    "# Без frontmatter\nsource_url: https://example.test/cons_doc_LAW_999999/\n",
])
def test_archive_skips_files_without_law_id(kb, capsys, text):
    """Живой и архивный файлы без LAW id не мешают проверке архива."""
    for rel in ("kodeksy/converted-md/без-id.md", "archive-editions/без-id.md"):
        path = kb.data / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    code, rows = _run(kb, capsys)
    assert code == 0
    assert rows["archive"]["status"] == "OK"
    assert len(kb.calls) == 2 * len(verify._kodeksy())


@pytest.mark.parametrize("source,target", [("призрак", "узел-0"),
                                           ("узел-0", "призрак")])
def test_orphan_edge_fails(kb, capsys, source, target):
    with sqlite3.connect(kb.db) as con:
        con.execute("INSERT INTO graph_edges VALUES ('плохая-связь', ?, ?)",
                    (source, target))
    code, rows = _run(kb, capsys)
    assert code == 1
    assert rows["integrity"]["status"] == "FAIL"
    assert rows["integrity"]["orphan_edges"] == 1


@pytest.mark.parametrize("folder,coll", [("decrees", "laws"),
                                         ("", "laws_u2"),
                                         ("court-practice/plenum_vs", "case_law"),
                                         ("court-practice/vs_all", "case_law_u2")])
def test_archived_vector_fails(kb, capsys, folder, coll):
    _md(kb.data / "archive-editions" / folder / "старый.md", "999999")
    kb.vectors[coll].add("999999")
    code, rows = _run(kb, capsys)
    assert code == 1
    assert rows["archive"]["status"] == "FAIL"
    assert f"LAW 999999, {coll}: остался в векторах" in rows["archive"]["details"]


def test_missing_index_fails(kb, capsys):
    with sqlite3.connect(kb.db) as con:
        con.execute("DROP INDEX ix_graph_nodes_number")
    code, rows = _run(kb, capsys)
    assert code == 1
    assert rows["index"]["status"] == "FAIL"


def test_no_chromadb_skips_vectors(kb, capsys, monkeypatch):
    monkeypatch.setitem(sys.modules, "chromadb", None)
    code, rows = _run(kb, capsys)
    assert code == 0
    assert rows["kodeksy"]["status"] == rows["archive"]["status"] == "SKIP"
    assert rows["kodeksy"]["parts"] == {"graph": "OK", "chroma": "SKIP"}
    assert rows["integrity"]["status"] == "OK"
    # Пропущенные векторы не скрывают ошибку графа.
    with sqlite3.connect(kb.db) as con:
        con.execute("DELETE FROM graph_documents WHERE id='5142'")
    code, rows = _run(kb, capsys)
    assert code == 1
    assert rows["kodeksy"]["status"] == "FAIL"


def test_no_chroma_flag_does_not_open_client(kb, capsys, monkeypatch):
    monkeypatch.setattr(sys.modules["chromadb"], "PersistentClient", None)
    code, rows = _run(kb, capsys, "--no-chroma")
    assert code == 0
    assert rows["archive"]["status"] == "SKIP"
    assert not kb.calls


def test_missing_collection_is_failure(kb, capsys):
    del kb.vectors["laws_u2"]
    code, rows = _run(kb, capsys)
    assert code == 1 and rows["kodeksy"]["status"] == "FAIL"
    assert "нет коллекции laws_u2" in rows["kodeksy"]["details"]


def test_warning_and_pending(kb, capsys):
    (kb.data / "kb_update_status.json").write_text(
        '{"state":"warning","message":"предупреждение: relink"}', encoding="utf-8")
    pending = kb.data / "refs/pending_docids.txt"
    pending.parent.mkdir()
    pending.write_text("  \n", encoding="utf-8")
    code, rows = _run(kb, capsys)
    assert code == 0
    assert "relink" in rows["status"]["details"]
    pending.write_text("5142\n", encoding="utf-8")
    code, rows = _run(kb, capsys)
    assert code == 1 and rows["pending"]["status"] == "FAIL"


@pytest.mark.parametrize("raw", [None, "{", '{"state":"running"}'])
def test_bad_status_fails(kb, capsys, raw):
    path = kb.data / "kb_update_status.json"
    if raw is None:
        path.unlink()
    else:
        path.write_text(raw, encoding="utf-8")
    code, rows = _run(kb, capsys)
    assert code == 1 and rows["status"]["status"] == "FAIL"


def test_skip_running_status(kb, capsys):
    (kb.data / "kb_update_status.json").write_text(
        '{"state":"running"}', encoding="utf-8")
    code, rows = _run(kb, capsys, "--skip", "status")
    assert code == 0
    assert rows["status"]["status"] == "SKIP"
    assert rows["status"]["details"] == "пропущена по --skip"
    code = verify.main(["--data", str(kb.data), "--db", str(kb.db),
                        "--no-chroma", "--skip", "status"])
    assert code == 0
    assert capsys.readouterr().out.splitlines()[0] == (
        "SKIP Статус прогона: пропущена по --skip")


def test_skip_multiple_checks(kb, capsys):
    pending = kb.data / "refs/pending_docids.txt"
    pending.parent.mkdir()
    pending.write_text("5142\n", encoding="utf-8")
    with sqlite3.connect(kb.db) as con:
        con.execute("DROP INDEX ix_graph_nodes_number")
    code, rows = _run(kb, capsys, "--skip", "pending,index")
    assert code == 0
    assert rows["pending"]["status"] == rows["index"]["status"] == "SKIP"


@pytest.mark.parametrize("ids", ["unknown", "status,unknown"])
def test_skip_unknown_id_is_argparse_error(capsys, ids):
    with pytest.raises(SystemExit) as exc:
        verify.main(["--skip", ids])
    assert exc.value.code == 2
    assert "неизвестные ID проверок: unknown" in capsys.readouterr().err


def test_skip_all_does_not_open_stores(kb, capsys, monkeypatch):
    def unexpected(*args, **kwargs):
        pytest.fail("пропущенные проверки не должны открывать хранилища")

    monkeypatch.setattr(verify, "_graph_ids", unexpected)
    monkeypatch.setattr(verify, "_Vectors", unexpected)
    code, rows = _run(kb, capsys, "--skip", ",".join(verify.CHECK_IDS))
    assert code == 0
    assert all(row["status"] == "SKIP" for row in rows.values())


@pytest.mark.parametrize("rc,output,warning", [
    (0, "OK Кодексы: всё на месте", None),
    (1, "FAIL Дедуп редакций: лишние файлы\nFAIL Кодексы: нет векторов",
     "kb_verify: Дедуп редакций, Кодексы"),
    (2, "ошибка запуска без отчёта", "kb_verify"),
])
def test_update_verification_step(tmp_path, rc, output, warning):
    """Шаг 5c нефатален и разбирает только вывод текущего вызова, а не весь лог."""
    script = (Path(__file__).parent.parent / "scripts/kb_update.sh").read_text(
        encoding="utf-8")
    step = script.split("# 5c.", 1)[1].split("# 6.", 1)[0]
    step = "\n".join(step.splitlines()[1:])
    pyk = tmp_path / "python"
    pyk.write_text(
        '#!/bin/sh\n[ "$*" = "scripts/kb_verify.py --skip status" ] || exit 99\n'
        'printf "%s\\n" "$VERIFY_TEST_OUTPUT" >&2\nexit "$VERIFY_TEST_RC"\n',
        encoding="utf-8")
    pyk.chmod(0o755)
    log = tmp_path / "kb_update.log"
    log.write_text("FAIL Старый прогон: старая ошибка\n", encoding="utf-8")
    env = {**os.environ, "PYK": str(pyk), "LOG": str(log),
           "VERIFY_TEST_OUTPUT": output, "VERIFY_TEST_RC": str(rc)}
    result = subprocess.run(
        ["sh", "-c", 'status() { printf "%s\\n" "$*"; }\n'
         'warn() { printf "warn: %s\\n" "$1" >> "$LOG"; }\n'
         + step + '\nprintf "шаг завершён\\n"\n'],
        env=env, cwd=tmp_path, capture_output=True, text=True, check=True)
    assert result.stdout == "running проверка базы\nшаг завершён\n"
    expected = "FAIL Старый прогон: старая ошибка\n" + output + "\n"
    if warning:
        expected += f"warn: {warning}\n"
    assert log.read_text(encoding="utf-8") == expected


def test_duplicates_fail_without_extra_stdout(kb, capsys):
    for i in range(12):
        _md(kb.data / f"federal-laws/fz/converted-md/{i}.md", str(10000 + i),
            "date: 01.01.2020\nnumber: 1-ФЗ\nedition_date: 01.01.2025\n")
    code, rows = _run(kb, capsys)
    assert code == 1 and rows["dedup"]["status"] == "FAIL"
    assert rows["dedup"]["count"] == 11
    assert len(rows["dedup"]["files"]) == 10


def test_missing_code_part_and_vector(kb, capsys):
    with sqlite3.connect(kb.db) as con:
        con.execute("DELETE FROM graph_documents WHERE id='34154'")
    kb.vectors["laws_u2"].remove("28165")
    code, rows = _run(kb, capsys)
    assert code == 1
    assert "Гражданский кодекс РФ часть 3 (LAW 34154): нет в графе" in rows["kodeksy"]["details"]
    assert "Налоговый кодекс РФ часть 2 (LAW 28165), laws_u2" in rows["kodeksy"]["details"]


def test_archived_graph_fails_even_without_chroma(kb, capsys):
    _md(kb.data / "archive-editions/decrees/старый.md", "999999")
    with sqlite3.connect(kb.db) as con:
        con.execute("INSERT INTO graph_documents VALUES ('старый', ?, 0, 0)",
                    ("https://example.test/cons_doc_LAW_999999/",))
    code, rows = _run(kb, capsys, "--no-chroma")
    assert code == 1 and rows["archive"]["status"] == "FAIL"
    assert "LAW 999999: остался в графе" in rows["archive"]["details"]


def test_counter_mismatches_cannot_cancel(kb, capsys):
    with sqlite3.connect(kb.db) as con:
        con.execute("UPDATE graph_documents SET nodes_count=2 WHERE id='5142'")
        con.execute("UPDATE graph_documents SET nodes_count=0 WHERE id='9027'")
    code, rows = _run(kb, capsys)
    assert code == 1
    assert rows["integrity"]["counter_mismatches"] == 2


def test_read_only_connection_sees_wal(kb):
    # Незачекпоинченная запись видна mode=ro; immutable=1 потерял бы её.
    with sqlite3.connect(kb.db) as writer:
        writer.execute("INSERT INTO graph_documents VALUES ('wal', ?, 0, 0)",
                       ("https://example.test/cons_doc_LAW_123456/",))
        writer.commit()
        with verify._connect(kb.db) as reader:
            assert reader.execute("SELECT id FROM graph_documents WHERE id='wal'").fetchone()
            with pytest.raises(sqlite3.OperationalError):
                reader.execute("DELETE FROM graph_documents")
        reader.close()


def test_text_report_has_seven_lines(kb, capsys):
    code = verify.main(["--data", str(kb.data), "--db", str(kb.db), "--no-chroma"])
    lines = capsys.readouterr().out.splitlines()
    assert code == 0 and len(lines) == 7
    assert all(line.startswith(("OK ", "SKIP ")) and ": " in line for line in lines)
