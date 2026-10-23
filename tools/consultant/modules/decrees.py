# -*- coding: utf-8 -*-
"""Скачивание подзаконных актов (постановления/распоряжения Правительства,
указы Президента) из КонсультантПлюс через ПЛАТНЫЙ сеанс (cloud.consultant.ru).

Резолв — быстрый поиск по запросу «{вид} {дата} {номер}» с выбором результата
по совпадению названия (быстрый поиск type-blind). Текст берётся из фрейма
document_inner (полный текст, не заглушка «некоммерческой версии»).

Источник списка — refs/subordinate_acts_ALL.json (готовит экстрактор реквизитов
по корпусу НПА). Результат → BASE_DIR/decrees/converted-md/*.md с frontmatter
(category: government_decree|government_order|presidential_decree).

Запуск:
    python modules/decrees.py                 # все акты из списка
    python modules/decrees.py --limit-per-type 2   # тест
"""
import sys, time, re, json, argparse, logging
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
import html2text                                            # noqa: E402
from config import BASE_DIR                                 # noqa: E402
from modules.federal_laws import (                          # noqa: E402
    ConsultantSession, kill_restriction, safe_fn,
)

log = logging.getLogger('decrees')

REFS = BASE_DIR / 'refs' / 'subordinate_acts_ALL.json'
OUT_MD = BASE_DIR / 'decrees' / 'converted-md'
UNRESOLVED = BASE_DIR / 'refs' / 'decrees_unresolved.txt'

# Ключ JSON-списка → (префикс запроса, regex вида в названии, category)
TYPES = {
    'Постановление Правительства': (
        'Постановление Правительства РФ', r'постановлени\w*\s+Правительства',
        'government_decree'),
    'Распоряжение Правительства': (
        'Распоряжение Правительства РФ', r'распоряжени\w*\s+Правительства',
        'government_order'),
    'Указ Президента': (
        'Указ Президента РФ', r'указ\w*\s+Президента', 'presidential_decree'),
}
STUB_MARKERS = ('по расписанию', 'некоммерческой версии',
                'коммерческой версии консультантплюс')
MIN_CHARS = 400


def html_to_md(html: str) -> str:
    h = html2text.HTML2Text()
    h.ignore_links = False
    h.ignore_images = True
    h.body_width = 0
    return re.sub(r'\n{4,}', '\n\n\n', h.handle(html)).strip()


def quick_search(p, rnd, query):
    p.goto(f'https://cloud.consultant.ru/cloud/cgi/online.cgi?req=home&rnd={rnd}',
           wait_until='domcontentloaded', timeout=30000)
    time.sleep(2.5); kill_restriction(p); time.sleep(1.5)
    box = p.locator("input[class*='search'], input.x-input__field").first
    box.click(); box.fill(query); time.sleep(0.8); p.keyboard.press('Enter')
    time.sleep(6); kill_restriction(p); time.sleep(2.5)
    return p.eval_on_selector_all(
        'a', "els=>els.filter(e=>e.href&&e.href.includes('req=doc'))"
             ".slice(0,10).map(e=>({t:(e.innerText||'').trim(),href:e.href}))") or []


def pick(results, title_rx, date, number):
    """Выбрать результат по виду + точному совпадению «от ДАТА N НОМЕР»."""
    want = re.compile(title_rx, re.I)
    dn = re.compile(r'от\s+%s\s+N\s*%s\b' % (re.escape(date), re.escape(number)), re.I)
    for r in results:
        t = r['t'].replace('\n', ' ')
        if want.search(t) and dn.search(t):
            m = re.search(r'[?&]n=(\d+)', r['href'])
            return r['href'], (m.group(1) if m else None), t
    return None, None, None


def fetch_doc(p, href):
    """Открыть документ в платном сеансе, вернуть HTML из фрейма document_inner."""
    p.goto(href, wait_until='domcontentloaded', timeout=30000)
    time.sleep(4); kill_restriction(p); time.sleep(3)
    for fr in p.frames:
        if 'document_inner' in fr.url:
            for _ in range(2):
                try:
                    return fr.content()
                except Exception:  # noqa: BLE001 — перенесено из OpenClaw_consultant-tools как есть
                    time.sleep(2)
    return None


def save(doc_id, title, category, md):
    OUT_MD.mkdir(parents=True, exist_ok=True)
    slug = safe_fn(title)[:150]
    public = (f'https://www.consultant.ru/document/cons_doc_LAW_{doc_id}/'
              if doc_id else '')
    fm = ('---\n' f'title: {title}\n' f'source_url: {public}\n'
          f'date_downloaded: {datetime.now().isoformat()}\n'
          f'category: {category}\n---\n\n')
    (OUT_MD / f'{slug}.md').write_text(fm + f'# {title}\n\n' + md, encoding='utf-8')


def run(limit_per_type: int = 0):
    data = json.load(open(REFS, encoding='utf-8'))
    stat = {'resolved': 0, 'unresolved': 0, 'saved': 0, 'stub': 0,
            'short': 0, 'errors': 0}
    unresolved = []
    with ConsultantSession(headless=True) as sess:
        p, rnd = sess.page, sess.rnd
        for jtype, (prefix, rx, cat) in TYPES.items():
            items = data.get(jtype, [])
            if limit_per_type:
                items = items[:limit_per_type]
            log.info(f'=== {jtype}: {len(items)} ===')
            for it in items:
                d, n = it['date'], it['number']
                try:
                    res = quick_search(p, rnd, f'{prefix} {d} {n}')
                except Exception as e:  # noqa: BLE001 — перенесено из OpenClaw_consultant-tools как есть
                    stat['errors'] += 1
                    log.warning(f'  search err {d} N{n}: {repr(e)[:50]}')
                    continue
                href, doc_id, t = pick(res, rx, d, n)
                if not href:
                    stat['unresolved'] += 1
                    unresolved.append(f'{jtype} {d} N{n}')
                    log.info(f'  ✗ не найден {d} N{n} (рез {len(res)})')
                    continue
                stat['resolved'] += 1
                html = fetch_doc(p, href)
                if not html:
                    stat['errors'] += 1
                    log.info(f'  ! {d} N{n}: фрейм пуст')
                    continue
                md = html_to_md(html)
                low = md.lower()
                if any(s in low for s in STUB_MARKERS):
                    stat['stub'] += 1
                    log.info(f'  ! {d} N{n}: заглушка')
                    continue
                if len(md) < MIN_CHARS:
                    stat['short'] += 1
                    log.info(f'  ~ {d} N{n}: короткий {len(md)}')
                    continue
                save(doc_id, t, cat, md)
                stat['saved'] += 1
                log.info(f'  ✓ {d} N{n} id={doc_id} → {len(md):,} симв')
    log.info(f'ИТОГО: {json.dumps(stat, ensure_ascii=False)}')
    if unresolved:
        UNRESOLVED.parent.mkdir(parents=True, exist_ok=True)
        UNRESOLVED.write_text('\n'.join(unresolved), encoding='utf-8')
    return stat


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO,
                        format='%(asctime)s [%(levelname)s] %(message)s')
    ap = argparse.ArgumentParser()
    ap.add_argument('--limit-per-type', type=int, default=0,
                    help='Ограничить число актов на тип (тест)')
    args = ap.parse_args()
    run(limit_per_type=args.limit_per_type)
