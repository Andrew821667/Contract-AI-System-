"""
modules/kodeksy.py — загрузка всех Кодексов РФ

Использование:
    python3 modules/kodeksy.py
    python3 modules/kodeksy.py --force
    python3 modules/kodeksy.py --check
    python3 modules/kodeksy.py --refresh   # еженедельно: перекачать и сравнить
    python3 modules/kodeksy.py --notify
"""
import os, re, sys, time, logging, argparse, requests
from pathlib import Path
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).parent.parent))
from modules.base import fetch, extract_markdown, fetch_full_text, save_document, safe_fn
from config import BASE_DIR

# Манифест изменённых документов (номера LAW через перевод строки):
# kb_update.sh обновляет по нему граф и векторы точечно (--only-docids).
CHANGED_MANIFEST = BASE_DIR / "refs" / "changed_docids.txt"
RAW_DIR = BASE_DIR / "kodeksy" / "raw-html"
MD_DIR  = BASE_DIR / "kodeksy" / "converted-md"
LOG_PATH = BASE_DIR / "kodeksy.log"
BASE_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.FileHandler(str(LOG_PATH), encoding="utf-8"), logging.StreamHandler()]
)
log = logging.getLogger(__name__)

KODEKSY = [
    ("Гражданский кодекс РФ часть 1",         "https://www.consultant.ru/document/cons_doc_LAW_5142/"),
    ("Гражданский кодекс РФ часть 2",         "https://www.consultant.ru/document/cons_doc_LAW_9027/"),
    ("Гражданский кодекс РФ часть 3",         "https://www.consultant.ru/document/cons_doc_LAW_34154/"),
    ("Гражданский кодекс РФ часть 4",         "https://www.consultant.ru/document/cons_doc_LAW_64629/"),
    ("Налоговый кодекс РФ часть 1",           "https://www.consultant.ru/document/cons_doc_LAW_19671/"),
    ("Налоговый кодекс РФ часть 2",           "https://www.consultant.ru/document/cons_doc_LAW_28165/"),
    ("Трудовой кодекс РФ",                    "https://www.consultant.ru/document/cons_doc_LAW_34683/"),
    ("Уголовный кодекс РФ",                   "https://www.consultant.ru/document/cons_doc_LAW_10699/"),
    ("Уголовно-процессуальный кодекс РФ",     "https://www.consultant.ru/document/cons_doc_LAW_34481/"),
    ("Уголовно-исполнительный кодекс РФ",     "https://www.consultant.ru/document/cons_doc_LAW_12940/"),
    ("КоАП РФ",                               "https://www.consultant.ru/document/cons_doc_LAW_34661/"),
    ("Арбитражный процессуальный кодекс РФ",  "https://www.consultant.ru/document/cons_doc_LAW_37800/"),
    ("Гражданский процессуальный кодекс РФ",  "https://www.consultant.ru/document/cons_doc_LAW_39570/"),
    ("Земельный кодекс РФ",                   "https://www.consultant.ru/document/cons_doc_LAW_33773/"),
    ("Лесной кодекс РФ",                      "https://www.consultant.ru/document/cons_doc_LAW_64299/"),
    ("Водный кодекс РФ",                      "https://www.consultant.ru/document/cons_doc_LAW_60683/"),
    ("Жилищный кодекс РФ",                    "https://www.consultant.ru/document/cons_doc_LAW_51057/"),
    ("Градостроительный кодекс РФ",           "https://www.consultant.ru/document/cons_doc_LAW_51040/"),
    ("Семейный кодекс РФ",                    "https://www.consultant.ru/document/cons_doc_LAW_8982/"),
    ("Бюджетный кодекс РФ",                   "https://www.consultant.ru/document/cons_doc_LAW_19702/"),
    ("Воздушный кодекс РФ",                   "https://www.consultant.ru/document/cons_doc_LAW_13744/"),
    ("Кодекс торгового мореплавания РФ",      "https://www.consultant.ru/document/cons_doc_LAW_22916/"),
    ("Таможенный кодекс ЕАЭС",                "https://www.consultant.ru/document/cons_doc_LAW_215315/"),
    # Добор ФЗ видит кодексы в каталоге и пропускает («Не классифицирован»),
    # так что без этого списка двух кодексов в базе не было вовсе (до 10.2026).
    ("Кодекс административного судопроизводства РФ", "https://www.consultant.ru/document/cons_doc_LAW_176147/"),
    ("Кодекс внутреннего водного транспорта РФ",     "https://www.consultant.ru/document/cons_doc_LAW_30650/"),
]


def download_one(name: str, url: str, force: bool = False) -> dict:
    slug = safe_fn(name)
    md_path = MD_DIR / f"{slug}.md"
    if md_path.exists() and not force:
        chars = len(md_path.read_text(encoding='utf-8'))
        log.info(f"  Пропуск: {name} ({chars:,} симв)")
        return {"name": name, "status": "skipped", "chars": chars}
    log.info(f"  Скачиваем: {name}")
    resp = fetch(url)
    if not resp:
        return {"name": name, "status": "error", "error": "Не удалось загрузить"}
    md = fetch_full_text(url, resp.text)
    if 'доступен по расписанию' in md:
        log.warning(f"  Заблокирован: {name}")
        return {"name": name, "status": "blocked"}
    (RAW_DIR / f"{slug}.html").parent.mkdir(parents=True, exist_ok=True)
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    (RAW_DIR / f"{slug}.html").write_text(resp.text, encoding='utf-8')
    result = save_document(name, url, md, RAW_DIR, MD_DIR, "kodeks")
    log.info(f"  OK: {result['lines']} строк, {result['chars']:,} симв")
    return result


def run(force: bool = False, check: bool = False) -> list:
    log.info("=" * 60)
    log.info(f"Кодексы РФ ({'force' if force else 'только новые'})")
    log.info("=" * 60)
    if check:
        results = []
        for name, _ in KODEKSY:
            p = MD_DIR / f"{safe_fn(name)}.md"
            if p.exists():
                results.append({"name": name, "status": "ok", "chars": len(p.read_text(encoding='utf-8'))})
            else:
                results.append({"name": name, "status": "missing"})
        return results
    results = []
    for name, url in KODEKSY:
        r = download_one(name, url, force=force)
        results.append(r)
        if r["status"] not in ("skipped",):
            time.sleep(2)
    ok = [r for r in results if r["status"] == "ok"]
    skip = [r for r in results if r["status"] == "skipped"]
    err = [r for r in results if r["status"] in ("error", "blocked")]
    log.info(f"Готово: {len(ok)} скачано, {len(skip)} пропущено, {len(err)} ошибок")
    return results


# Новая редакция кодекса в К+ приходит под тем же номером документа, поэтому
# «добор» её не видит, а сверка по дате в облачном интерфейсе ослепла после
# смены вёрстки К+ (с июля 2026 — «изменено 0» каждую неделю, кодексы застряли
# в редакциях на 30.05.2026). Здесь — без опоры на вёрстку: кодекс
# перекачивается тем же способом, что и при загрузке, и текст сравнивается с
# сохранённым. Повторная загрузка неизменного кодекса даёт байт в байт тот же
# текст (проверено на Водном кодексе), так что разница = новая редакция.
# Дата редакции для журнала; бывает и «(ред. от 26.06.2026, с изм. от …)».
EDITION_RE = re.compile(r"N\s*[\dА-Яа-я\-]+\s*\(ред\.\s*от\s*(\d{2}\.\d{2}\.\d{4})[,)]")
# Новый текст заметно короче прежнего — скорее обрыв или заглушка К+, чем
# новая редакция: не заменяем, пишем в журнал.
MIN_LENGTH_RATIO = 0.7


def _body(md_text: str) -> str:
    """Текст документа без frontmatter и заголовка «# название» — его и сравниваем."""
    if md_text.startswith("---") and "\n---\n" in md_text:
        md_text = md_text.split("\n---\n", 1)[1]
    lines = md_text.lstrip("\n").split("\n")
    if lines and lines[0].startswith("# "):
        lines = lines[1:]
    return "\n".join(lines).strip()


def _edition(text: str):
    m = EDITION_RE.search(text or "")
    return m.group(1) if m else None


def refresh_one(name: str, url: str, dry_run: bool = False) -> dict:
    slug = safe_fn(name)
    md_path = MD_DIR / f"{slug}.md"
    doc_id = re.search(r"cons_doc_LAW_(\d+)", url).group(1)
    resp = fetch(url)
    if not resp:
        return {"name": name, "doc_id": doc_id, "status": "error", "error": "не удалось загрузить"}
    md = fetch_full_text(url, resp.text).strip()
    if "доступен по расписанию" in md:
        return {"name": name, "doc_id": doc_id, "status": "blocked"}
    old = _body(md_path.read_text(encoding="utf-8")) if md_path.exists() else ""
    if md == old:
        return {"name": name, "doc_id": doc_id, "status": "same", "edition": _edition(md)}
    if old and len(md) < len(old) * MIN_LENGTH_RATIO:
        return {"name": name, "doc_id": doc_id, "status": "suspicious",
                "error": f"новый текст {len(md):,} симв против {len(old):,} — не заменяю"}
    if not dry_run:
        RAW_DIR.mkdir(parents=True, exist_ok=True)
        (RAW_DIR / f"{slug}.html").write_text(resp.text, encoding="utf-8")
        save_document(name, url, md, RAW_DIR, MD_DIR, "kodeks")
    return {"name": name, "doc_id": doc_id, "status": "changed",
            "old_edition": _edition(old), "edition": _edition(md)}


def refresh(dry_run: bool = False) -> int:
    """Перекачать все кодексы, заменить изменившиеся, записать манифест.

    dry_run — только сравнить и показать, ничего не записывая: отдельный
    настоящий прогон «съел» бы изменения — следующий kb_update.sh увидел бы
    кодексы уже совпадающими и не обновил бы им граф и векторы.

    Код возврата: 0 — прошло; 2 — больше половины кодексов не скачалось
    (К+ недоступен или сессия протухла) — kb_update.sh пометит прогон.
    """
    log.info("=" * 60)
    log.info("Кодексы РФ: проверка новых редакций (перекачка и сравнение)")
    log.info("=" * 60)
    results = []
    for name, url in KODEKSY:
        try:
            r = refresh_one(name, url, dry_run=dry_run)
        except Exception as e:  # noqa: BLE001 — один кодекс не роняет остальные; ошибка уходит в журнал ниже
            r = {"name": name, "status": "error", "error": repr(e)[:120]}
        results.append(r)
        if r["status"] == "changed":
            log.info(f"  ИЗМЕНЁН: {name} — ред. {r.get('old_edition') or '?'} → {r.get('edition') or '?'}")
        elif r["status"] == "same":
            log.info(f"  без изменений: {name} (ред. {r.get('edition') or '?'})")
        else:
            log.warning(f"  {r['status'].upper()}: {name} — {r.get('error', '')}")
        time.sleep(2)
    changed = [r["doc_id"] for r in results if r["status"] == "changed"]
    if not dry_run:
        CHANGED_MANIFEST.parent.mkdir(parents=True, exist_ok=True)
        CHANGED_MANIFEST.write_text("\n".join(changed), encoding="utf-8")
    failed = [r for r in results if r["status"] in ("error", "blocked", "suspicious")]
    log.info(f"Кодексы: изменено {len(changed)}, без изменений "
             f"{sum(1 for r in results if r['status'] == 'same')}, ошибок {len(failed)}. "
             f"Манифест: {CHANGED_MANIFEST}")
    return 2 if len(failed) > len(KODEKSY) // 2 else 0


def send_telegram(results: list):
    load_dotenv(Path.home() / ".config" / "consultant" / ".env")
    token   = os.getenv("TELEGRAM_BOT_TOKEN", "")
    chat_id = os.getenv("TELEGRAM_CHAT_ID", "321681061")
    if not token: return
    ok  = [r for r in results if r["status"] == "ok"]
    err = [r for r in results if r["status"] in ("error", "blocked")]
    lines = [f"📚 *Кодексы РФ обновлены*\n✅ Скачано: *{len(ok)}*"]
    for r in ok:
        lines.append(f"  • {r['name']} ({r.get('chars',0):,} симв)")
    if err:
        lines.append(f"❌ Ошибок: *{len(err)}*")
    requests.post(
        f"https://api.telegram.org/bot{token}/sendMessage",
        json={"chat_id": chat_id, "text": "\n".join(lines), "parse_mode": "Markdown"},
        timeout=10
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--force",  action="store_true")
    parser.add_argument("--check",  action="store_true")
    parser.add_argument("--refresh", action="store_true",
                        help="перекачать все кодексы, заменить изменившиеся, записать манифест")
    parser.add_argument("--dry-run", action="store_true",
                        help="с --refresh: только сравнить, ничего не записывать")
    parser.add_argument("--notify", action="store_true")
    args = parser.parse_args()
    if args.refresh:
        sys.exit(refresh(dry_run=args.dry_run))
    results = run(force=args.force, check=args.check)
    if args.notify:
        send_telegram(results)
