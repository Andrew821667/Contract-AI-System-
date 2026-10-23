# -*- coding: utf-8 -*-
"""Сбор судебной практики высших судов из КонсультантПлюс через платный сеанс.

Энумерация — карточка поиска (cardDiv=LAW) с фильтром «Принявший орган»
(механизм как у ФЗ), scroll-harvest списка. Скачивание — фрейм document_inner
(как decrees). Результат → BASE_DIR/court-practice/<slug>/converted-md/*.md
с frontmatter category=court_practice, organ=<орган>.

Запуск:
    python modules/court_practice.py --organ "Пленум Верховного Суда РФ" --slug plenum_vs
    python modules/court_practice.py --organ "..." --slug ... --limit 5   # тест
"""
import sys, time, re, json, argparse, logging
from datetime import datetime
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
import html2text                                          # noqa: E402
from config import BASE_DIR                               # noqa: E402
from modules.federal_laws import ConsultantSession, kill_restriction, safe_fn  # noqa: E402

log = logging.getLogger("court")


def html_to_md(html):
    h = html2text.HTML2Text(); h.ignore_links = False; h.ignore_images = True; h.body_width = 0
    return re.sub(r"\n{4,}", "\n\n\n", h.handle(html)).strip()


def discover(p, rnd, organ):
    """Карточка → Принявший орган → <организация> → Применить → scroll-harvest."""
    p.goto(f"https://cloud.consultant.ru/cloud/cgi/online.cgi?req=card&cardDiv=LAW&rnd={rnd}",
           wait_until="domcontentloaded", timeout=30000)
    time.sleep(4); kill_restriction(p); time.sleep(3)
    p.locator("text=/Законодательство\\s*\\d/").first.click(timeout=20000)
    time.sleep(10); kill_restriction(p); time.sleep(4)
    p.locator("text=Уточнить по реквизитам").first.click(timeout=15000)
    time.sleep(5); kill_restriction(p); time.sleep(2)
    p.locator('text="Принявший орган"').first.click(timeout=15000)
    time.sleep(5); kill_restriction(p); time.sleep(2)
    p.locator(f'text="{organ}"').first.click(timeout=15000)
    time.sleep(2)
    p.locator('button:has-text("Применить")').first.click(timeout=15000)
    time.sleep(8); kill_restriction(p)
    try: p.wait_for_load_state("networkidle", timeout=20000)
    except Exception: pass
    time.sleep(4); kill_restriction(p)
    total_m = re.search(r'\[\d+\s*:\s*(\d+)\]', p.inner_text("body"))
    total = int(total_m.group(1)) if total_m else None
    log.info(f"Всего у органа «{organ}»: {total}")

    seen = {}
    def collect():
        links = p.eval_on_selector_all("a",
            "els=>els.filter(e=>e.href&&e.href.includes('req=doc')&&e.href.includes('base=LAW')&&(e.offsetWidth||e.offsetHeight))"
            ".map(e=>({t:(e.innerText||'').replace(/\\n/g,' ').trim(),href:e.href}))") or []
        for l in links:
            m = re.search(r'[?&]n=(\d+)', l["href"])
            if m and len(l["t"]) > 10:
                seen[m.group(1)] = {"doc_id": m.group(1), "title": l["t"], "url": l["href"]}
    collect(); last = 0; stale = 0
    for i in range(400):
        p.evaluate("""()=>{const l=document.querySelector('.x-page-search-results__list');
            if(l){l.scrollTop=l.scrollHeight;const r=l.querySelectorAll('.x-list__row');
            if(r.length)r[r.length-1].scrollIntoView({block:'end'});}}""")
        time.sleep(1.1); kill_restriction(p); collect()
        if len(seen) == last:
            stale += 1
            if stale >= 6: break
        else: stale = 0
        last = len(seen)
        if (i + 1) % 25 == 0:
            log.info(f"  …скролл {i+1}: собрано {len(seen)}/{total}")
    log.info(f"Собрано ссылок: {len(seen)} (total={total})")
    return list(seen.values()), total


def fetch_doc(p, href):
    p.goto(href, wait_until="domcontentloaded", timeout=30000)
    time.sleep(4); kill_restriction(p); time.sleep(3)
    for fr in p.frames:
        if "document_inner" in fr.url:
            for _ in range(2):
                try: return fr.content()
                except Exception: time.sleep(2)
    return None


def run(organ, slug, limit=0, title_filter=None):
    out_md = BASE_DIR / "court-practice" / slug / "converted-md"
    out_md.mkdir(parents=True, exist_ok=True)
    stat = {"found": 0, "saved": 0, "stub": 0, "short": 0, "err": 0}
    tf = re.compile(title_filter, re.I) if title_filter else None
    with ConsultantSession(headless=True) as sess:
        p, rnd = sess.page, sess.rnd
        items, total = discover(p, rnd, organ)
        if tf:
            items = [it for it in items if tf.search(it["title"])]
            log.info(f"После фильтра заголовка /{title_filter}/: {len(items)}")
        if limit: items = items[:limit]
        stat["found"] = len(items)
        for i, it in enumerate(items, 1):
            target = out_md / f"{safe_fn(it['title'])[:150]}.md"
            if target.exists():                      # резюмируемость: не качать повторно
                stat["saved"] += 1
                continue
            try:
                html = fetch_doc(p, it["url"])
            except Exception as e:  # noqa: BLE001 — перенесено из OpenClaw_consultant-tools как есть
                stat["err"] += 1; log.warning(f"  [{i}] fetch err: {repr(e)[:50]}"); continue
            if not html:
                stat["err"] += 1; continue
            md = html_to_md(html); low = md.lower()
            if "по расписанию" in low or "некоммерческой версии" in low:
                stat["stub"] += 1; log.info(f"  [{i}] заглушка {it['doc_id']}"); continue
            if len(md) < 400:
                stat["short"] += 1; continue
            public = f"https://www.consultant.ru/document/cons_doc_LAW_{it['doc_id']}/"
            fm = (f"---\ntitle: {it['title']}\nsource_url: {public}\n"
                  f"date_downloaded: {datetime.now().isoformat()}\n"
                  f"category: court_practice\norgan: {organ}\n---\n\n")
            # атомарная запись: tmp → rename (kill по окну не оставит обрезок)
            tmp = target.with_suffix(".md.part")
            tmp.write_text(fm + f"# {it['title']}\n\n" + md, encoding="utf-8")
            tmp.replace(target)
            stat["saved"] += 1
            if i % 20 == 0: log.info(f"  [{i}/{len(items)}] сохранено {stat['saved']}")
    log.info(f"ИТОГО {slug}: {json.dumps(stat, ensure_ascii=False)}")
    return stat


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    ap = argparse.ArgumentParser()
    ap.add_argument("--organ", required=True)
    ap.add_argument("--slug", required=True)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--title-filter", default=None,
                    help="regex по заголовку (напр. ^Постановление для КС)")
    a = ap.parse_args()
    run(a.organ, a.slug, a.limit, a.title_filter)
