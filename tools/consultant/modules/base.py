"""Базовый класс для всех модулей загрузки документов."""
import re, json, time, logging, requests, html2text
from pathlib import Path
from datetime import datetime
from typing import List
from concurrent.futures import ThreadPoolExecutor, as_completed
from bs4 import BeautifulSoup
from config import SESSION_PATH, HEADERS

log = logging.getLogger(__name__)

# Число параллельных потоков при выкачке статей документа из www.consultant.ru.
# 8 — компромисс между скоростью и нагрузкой/риском троттлинга со стороны К+.
ARTICLE_FETCH_WORKERS = 8

FOOTER_PATTERNS = [
    r'\n\s*\*\s*\[Гражданский кодекс \(ГК РФ\)\]',
    r'\[Производственный календарь на 20\d{2}',
    r'\[Минимальный размер оплаты труда',
]

def load_session() -> dict:
    if not SESSION_PATH.exists():
        return {}
    return {c['name']: c['value'] for c in json.loads(SESSION_PATH.read_text(encoding='utf-8'))}

def safe_fn(t: str) -> str:
    t = re.sub(r'[^\w\s-]', '', t.lower())
    return re.sub(r'[\s]+', '_', t.strip())[:80]

def fetch(url: str, retries: int = 3, delay: int = 5):
    cookies = load_session()
    for attempt in range(retries):
        try:
            r = requests.get(url, headers=HEADERS, cookies=cookies, timeout=30)
            r.raise_for_status()
            return r
        except requests.RequestException as e:
            log.warning(f"  Попытка {attempt+1}/{retries}: {e}")
            if attempt < retries - 1:
                time.sleep(delay)
    return None

def extract_markdown(html: str) -> str:
    soup = BeautifulSoup(html, 'html.parser')
    ct = soup.find('div', class_=lambda c: c and 'document-page' in c and 'content' in c)
    if not ct:
        ct = soup.find('body') or soup
    for tag in ct.find_all(['nav','script','style','noscript']): tag.decompose()
    for tag in ct.find_all(class_=lambda c: c and 'breadcrumb' in ' '.join(c if c else [])): tag.decompose()
    h = html2text.HTML2Text()
    h.ignore_links = False; h.ignore_images = True; h.body_width = 0
    md = h.handle(str(ct))
    for pat in FOOTER_PATTERNS:
        matches = list(re.finditer(pat, md))
        if matches:
            pos = matches[-1].start()
            if pos > len(md) * 0.8:
                md = md[:pos].strip(); break
    md = re.sub(r'\n(\s*\*\s*\[(?:Главная|Документы)\]\([^)]+\)\s*\n)+', '\n', md)
    return md.strip()

# Порог: если markdown главной страницы документа короче этого — считаем что
# это оглавление (TOC), а не полный текст, и собираем статьи отдельно.
SHORT_DOC_THRESHOLD = 8000

# Любая строка-пункт списка, целиком являющаяся ссылкой на документ
# consultant.ru: оглавление статей, футер с кодексами, хлебные крошки.
# Покрывает форматы: (/document/...), (//www.consultant.ru/...), (http://...).
_NAV_LINK_RE = re.compile(
    r'^\s*\*\s*\[[^\]]*\]\('
    r'(?:'
    r'(?:https?:)?//[^)]*consultant\.ru/[^)]*'   # абсолютные ссылки на КП
    r'|/?(?:document|law)/[^)]*'                  # относительные /document/, /law/
    r')'
    r'\)\s*$',
    re.IGNORECASE,
)
# Прочие навигационные строки
_NAV_MISC_RE = re.compile(
    r'^\s*\*\s*\[(?:Главная|Документы)\]', re.IGNORECASE
)


def strip_nav(md: str) -> str:
    """Убрать навигационные link-списки (оглавление статей, футер с кодексами,
    хлебные крошки), которые www.consultant.ru дублирует на каждой странице."""
    out = []
    for line in md.splitlines():
        if _NAV_LINK_RE.match(line) or _NAV_MISC_RE.match(line):
            continue
        if line.strip() in ('Открыть полный текст документа', 'КонсультантПлюс'):
            continue
        out.append(line)
    cleaned = re.sub(r'\n{3,}', '\n\n', '\n'.join(out))
    return cleaned.strip()


def fetch_full_text(public_url: str, toc_html: str) -> str:
    """Вернуть полный markdown документа с www.consultant.ru.

    На www.consultant.ru документ бывает в двух формах:
      1. Одна страница с полным текстом (напр. ГК ч.1, КоАП — 100K+ символов).
      2. Страница-оглавление (TOC) со ссылками на статьи (ФЗ/ФКЗ, а также
         крупные кодексы вроде УК/НК — их TOC сам по себе огромный!).

    КЛЮЧЕВОЕ: решение о concat принимается по ЧИСЛУ ссылок-на-статьи, а НЕ по
    длине текста. Длина обманчива: у КоАП/НК ч.2 преамбула («Список изменяющих
    документов» из сотен inline-ссылок) сама по себе >90K, но текста статей в
    ней нет. Если в TOC много article-ссылок (cons_doc_LAW_<BASE>/<HASH>) —
    это оглавление, надо собирать статьи concat'ом, сколь угодно длинным ни был
    бы сам TOC. Если article-ссылок мало — это уже цельный документ, отдаём
    очищенный strip_nav-текст.
    """
    toc_md = extract_markdown(toc_html)

    soup = BeautifulSoup(toc_html, 'html.parser')
    article_re = re.compile(r'^/document/cons_doc_LAW_(\d+)/[a-f0-9]{32,}/?$')
    base_ids: dict = {}
    for a in soup.find_all('a', href=True):
        m = article_re.match(a['href'])
        if not m:
            continue
        base_ids.setdefault(m.group(1), []).append(a['href'])

    # Нет article-ссылок → это цельный документ, отдаём очищенный текст
    if not base_ids:
        return strip_nav(toc_md)

    base_id = max(base_ids, key=lambda k: len(base_ids[k]))
    seen = set()
    article_paths = []
    for path in base_ids[base_id]:
        if path not in seen:
            seen.add(path)
            article_paths.append(path)
    # Мало ссылок-на-статьи → цельный документ (не оглавление)
    if len(article_paths) < 5:
        return strip_nav(toc_md)

    log.info(f"    TOC ({len(toc_md)} симв), base_law=LAW_{base_id}, "
             f"{len(article_paths)} статей → concat (параллельно)")

    # Статьи качаем ПАРАЛЛЕЛЬНО (пул потоков): один кодекс из сотен статей
    # собирается за десятки секунд, а не за минуты. Порядок сохраняем по индексу.
    def _fetch_article(path: str) -> str:
        r = fetch(f'https://www.consultant.ru{path}')
        if not r:
            return ''
        return strip_nav(extract_markdown(r.text))

    results: List[str] = [''] * len(article_paths)
    done = 0
    with ThreadPoolExecutor(max_workers=ARTICLE_FETCH_WORKERS) as ex:
        future_to_idx = {ex.submit(_fetch_article, p): i
                         for i, p in enumerate(article_paths)}
        for fut in as_completed(future_to_idx):
            idx = future_to_idx[fut]
            try:
                results[idx] = fut.result()
            except Exception as e:  # noqa: BLE001 — перенесено из OpenClaw_consultant-tools как есть
                log.warning(f"    статья {idx} ошибка: {e}")
            done += 1
            if done % 50 == 0:
                log.info(f"    …скачано {done}/{len(article_paths)} статей")

    parts = ['# Полный текст\n\n']
    for art in results:
        if art:
            parts.append(art)
            parts.append('\n\n')
    return ''.join(parts)


def save_document(name: str, url: str, md: str, raw_dir: Path, md_dir: Path, category: str) -> dict:
    slug = safe_fn(name)
    dd = datetime.now().isoformat()
    raw_dir.mkdir(parents=True, exist_ok=True)
    md_dir.mkdir(parents=True, exist_ok=True)
    full_md = f"---\ntitle: {name}\nsource_url: {url}\ndate_downloaded: {dd}\ncategory: {category}\n---\n\n# {name}\n\n{md}"
    (md_dir / f"{slug}.md").write_text(full_md, encoding='utf-8')
    return {"name": name, "status": "ok", "lines": len(md.splitlines()), "chars": len(md), "slug": slug}
