# -*- coding: utf-8 -*-
"""Дедуп редакций (scripts/kb_dedup_editions.py): подзаконка и практика.

До 10.2026 дедуп видел только кодексы и ФЗ/ФКЗ (date/number во frontmatter):
у постановлений Правительства копились все редакции разом, у Пленума ВС —
прежняя рядом с новой.
"""
import importlib.util
import os
from pathlib import Path

_SPEC = importlib.util.spec_from_file_location(
    "kb_dedup_editions", Path(__file__).parent.parent / "scripts" / "kb_dedup_editions.py")
dedup = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(dedup)


def _md(path: Path, docid: str, title: str, mtime: int = 0, extra: str = "") -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"---\ntitle: {title}\nsource_url: https://www.consultant.ru/document/"
                    f"cons_doc_LAW_{docid}/\n{extra}---\n\n# {title}\n\nтекст\n", encoding="utf-8")
    if mtime:
        os.utime(path, (mtime, mtime))
    return str(path)


def _sources(tmp_path):
    return [
        (tmp_path / "federal-laws/fz/converted-md/*.md", ("laws", "laws_u2"), None),
        (tmp_path / "decrees/converted-md/*.md", ("laws", "laws_u2"), "decrees"),
        (tmp_path / "court-practice/*/converted-md/*.md", ("case_law", "case_law_u2"), "court-practice"),
    ]


def test_decree_editions_keep_latest(tmp_path):
    d = tmp_path / "decrees/converted-md"
    old = _md(d / "a.md", "532112", 'Постановление Правительства РФ от 12.03.2022 N 353 '
              '(ред. от 15.04.2026) "Об особенностях"')
    old_izm = _md(d / "b.md", "532112", 'Постановление Правительства РФ от 12.03.2022 N 353 '
                  '(ред. от 15.04.2026, с изм. от 08.07.2026) "Об особенностях"')
    new = _md(d / "c.md", "545244", 'Постановление Правительства РФ от 12.03.2022 N 353 '
              '(ред. от 23.09.2026) "Об особенностях"')
    _md(d / "other.md", "1", 'Распоряжение Правительства РФ от 12.03.2022 N 353-р "Иное"')

    losers, refresh = dedup.plan(_sources(tmp_path))
    assert {x["f"] for x in losers} == {old, old_izm}
    assert all(x["purge"] for x in losers)  # у 532112 не осталось файла
    assert new not in {x["f"] for x in losers}
    assert refresh == set()


def test_same_docid_new_edition_is_refreshed(tmp_path):
    """Новая редакция под прежним doc_id: старый файл — в архив, из сторов не
    чистим, а doc_id — на обновление графа и векторов."""
    d = tmp_path / "decrees/converted-md"
    old = _md(d / "a.md", "532112", "Постановление Правительства РФ от 12.03.2022 N 353 "
              "(ред. от 15.04.2026)")
    _md(d / "b.md", "532112", "Постановление Правительства РФ от 12.03.2022 N 353 "
        "(ред. от 15.04.2026, с изм. от 08.07.2026)")

    losers, refresh = dedup.plan(_sources(tmp_path))
    assert [(x["f"], x["purge"]) for x in losers] == [(old, False)]
    assert refresh == {"532112"}


def test_plenum_old_edition_in_both_folders(tmp_path):
    """Пленум ВС лежит и в plenum_vs, и в vs_all: старую редакцию убираем из
    обеих папок, а копию актуальной во второй папке не трогаем."""
    c = tmp_path / "court-practice"
    t_old = ("Постановление Пленума Верховного Суда РФ от 27.12.2002 N 29 "
             '(ред. от 15.12.2022) "О судебной практике по делам о краже"')
    t_new = ("Постановление Пленума Верховного Суда РФ от 27.12.2002 N 29 "
             '(ред. от 16.06.2026) "О судебной практике по делам о краже"')
    old1 = _md(c / "plenum_vs/converted-md/old.md", "434674", t_old)
    old2 = _md(c / "vs_all/converted-md/old.md", "434674", t_old)
    _md(c / "plenum_vs/converted-md/new.md", "537127", t_new)
    _md(c / "vs_all/converted-md/new.md", "537127", t_new)
    # одно и то же постановление без редакций в двух папках — не дубль
    t_plain = "Постановление Пленума Верховного Суда РФ N 90, Пленума ВАС РФ N 14 от 09.12.1999"
    _md(c / "plenum_vs/converted-md/p.md", "25814", t_plain)
    _md(c / "vs_all/converted-md/p.md", "25814", t_plain)

    losers, refresh = dedup.plan(_sources(tmp_path))
    assert {x["f"] for x in losers} == {old1, old2}
    assert all(x["purge"] for x in losers)
    assert refresh == set()
    assert {dedup._archive_path(x) for x in losers} == {
        dedup.ARCHIVE / "court-practice/plenum_vs/old.md",
        dedup.ARCHIVE / "court-practice/vs_all/old.md"}


def test_docid_kept_elsewhere_is_not_purged(tmp_path):
    """doc_id старой редакции остался у файла в другой группе (заголовок в
    другой папке иначе разобрался) — из сторов не чистим, иначе эмбед и
    ингест вернут его через неделю."""
    c = tmp_path / "court-practice"
    _md(c / "plenum_vs/converted-md/old.md", "434674", "Постановление Пленума Верховного Суда РФ "
        "от 27.12.2002 N 29 (ред. от 15.12.2022)")
    _md(c / "plenum_vs/converted-md/new.md", "537127", "Постановление Пленума Верховного Суда РФ "
        "от 27.12.2002 N 29 (ред. от 16.06.2026)")
    _md(c / "vs_all/converted-md/odd.md", "434674", "Постановление Пленума ВС РФ "
        "от 27.12.2002 N 29 (ред. от 15.12.2022)")

    losers, _ = dedup.plan(_sources(tmp_path))
    assert [x["purge"] for x in losers] == [False]


def test_fz_identity_still_from_frontmatter(tmp_path):
    fz = tmp_path / "federal-laws/fz/converted-md"
    old = _md(fz / "a.md", "100", "Федеральный закон от 05.04.2013 N 44-ФЗ (ред. от 01.01.2025)",
              extra="date: 05.04.2013\nnumber: 44-ФЗ\nedition_date: 01.01.2025\n")
    _md(fz / "b.md", "200", "Федеральный закон от 05.04.2013 N 44-ФЗ (ред. от 01.06.2026)",
        extra="date: 05.04.2013\nnumber: 44-ФЗ\nedition_date: 01.06.2026\n")
    # без date/number во frontmatter ФЗ не группируется (как раньше)
    _md(fz / "c.md", "300", "Федеральный закон от 05.04.2013 N 44-ФЗ (ред. от 01.07.2026)")

    losers, _ = dedup.plan(_sources(tmp_path))
    assert [x["f"] for x in losers] == [old]
    assert dedup._archive_path(losers[0]) == dedup.ARCHIVE / "a.md"
