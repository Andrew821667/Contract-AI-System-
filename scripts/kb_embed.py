# -*- coding: utf-8 -*-
"""Наполнение/обновление векторной БЗ (ChromaDB data/chromadb, laws/case_law)
из скачанных .md. Переиспользует штатные get_collection/embedding_fn КС
(модель paraphrase-multilingual-MiniLM-L12-v2). Эмбеддинг на MPS если доступен.

Режимы:
  chunktest  — QA чанков (очистка К+-мусора + метрики/образцы), без записи.
  embed      — наполнение. По умолчанию пропуск уже добавленных (resume).
               --refresh: удалить старые чанки документа и заэмбедить заново
                          (для обновления редакций / REPLACE).
               --only-docids id1,id2 : только указанные документы.

Чанкер идентичен src/api/rag_admin/routes.py (предложения→~800 симв, overlap
150, min 50) + жёсткий потолок 1200 симв (длинные таблицы дробятся).
"""
import os, sys, re, glob, argparse, time, statistics
# Эмбеддер грузим ОФЛАЙН из кеша (HF может быть недоступен → падение/фолбэк).
os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
sys.path.insert(0, "/Users/legalai/projects/Contract-AI-System-")

BASE = "/Users/legalai/consultant-data"
SRC = {
    "laws": [BASE+"/kodeksy/converted-md/*.md", BASE+"/federal-laws/fkz/converted-md/*.md",
             BASE+"/federal-laws/fz/converted-md/*.md", BASE+"/decrees/converted-md/*.md"],
    "case_law": [BASE+"/court-practice/*/converted-md/*.md"],
}
MIN_BODY = 500
HARD = 1200

JUNK_LINE = re.compile(
    r'(Ваша оценка|Документ похож|Документ не похож|Спасибо, ваш ответ|'
    r'Насколько этот документ|улучшит сервис|Связь с сервером временно|'
    r'Документ:\s*\d+/\d+|Доп\. информация к документу|Свернуть|Развернуть|'
    r'Получить спецпредложение|обратиться в региональный|'
    r'Тексты документов всегда доступны|некоммерческой версии|по расписанию|'
    r'Откройте документ в системе|Заказать документ|Поставьте запрос на контроль)',
    re.IGNORECASE)
MD_LINK = re.compile(r'\[([^\]]*)\]\([^)]*\)')
MD_HEAD = re.compile(r'^#{1,6}\s*')

def clean_body(body):
    out = []
    for ln in body.split("\n"):
        s = ln.strip()
        if not s or JUNK_LINE.search(s): continue
        s = MD_HEAD.sub('', s)
        s = MD_LINK.sub(r'\1', s)
        s = re.sub(r'\s{2,}', ' ', s).strip()
        if len(s) >= 2: out.append(s)
    return "\n".join(out)

def chunk_text(text, chunk_size=800, overlap=150):
    sentences = re.split(r"(?<=[.!?])\s+", text)
    chunks, current, clen = [], [], 0
    for s in sentences:
        slen = len(s)
        if clen + slen > chunk_size and current:
            chunks.append(" ".join(current))
            ov = " ".join(current)[-overlap:]
            current = [ov, s]; clen = len(ov) + slen
        else:
            current.append(s); clen += slen
    if current: chunks.append(" ".join(current))
    out = []
    for c in chunks:
        if len(c) <= HARD: out.append(c); continue
        words = c.split(" "); buf = []; blen = 0
        for w in words:
            if blen + len(w) + 1 > HARD and buf:
                out.append(" ".join(buf)); buf = [w]; blen = len(w)
            else:
                buf.append(w); blen += len(w) + 1
        if buf: out.append(" ".join(buf))
    return [c for c in out if len(c.strip()) >= 50]

def parse_md(path):
    raw = open(path, encoding="utf-8", errors="replace").read()
    fm = {}; body = raw
    m = re.match(r'^---\n(.*?)\n---\n?(.*)$', raw, re.DOTALL)
    if m:
        for line in m.group(1).split("\n"):
            km = re.match(r'^([a-zA-Z_]\w*):\s?(.*)$', line)
            if km: fm[km.group(1)] = km.group(2).strip()
        body = m.group(2)
    return fm, body

def docid_of(fm, path):
    mm = re.search(r'cons_doc_LAW_(\d+)', fm.get("source_url","") or "")
    return mm.group(1) if mm else re.sub(r'\W+','_', path.split("/")[-1])[:40]

def collect_files(cname, limit=0, sample=0):
    files = []
    for pat in SRC[cname]: files += sorted(glob.glob(pat))
    if sample and len(files) > sample:
        files = files[::max(1,len(files)//sample)][:sample]
    if limit: files = files[:limit]
    return files

def chunktest(cname, sample):
    files = collect_files(cname, sample=sample)
    print(f"=== QA ЧАНКОВ {cname}: выборка {len(files)} ===")
    sizes=[]; per=[]; junk=0; total=0; short=0; ex=[]
    J = re.compile(r'Ваша оценка|Связь с сервером|Документ:\s*\d+/\d+|Доп\. информация|req=query|online\.cgi', re.I)
    for f in files:
        fm, body = parse_md(f)
        if len(body) < MIN_BODY: continue
        ch = chunk_text(clean_body(body)); per.append(len(ch))
        for c in ch:
            total+=1; sizes.append(len(c))
            if J.search(c): junk+=1
            if len(c)<100: short+=1
        if ch and len(ex)<3: ex.append((fm.get("title","")[:55], ch[len(ch)//2][:300]))
    if not sizes: print("нет чанков"); return
    print(f"чанков {total} | на док медиана {statistics.median(per):.0f} max {max(per)}")
    print(f"размер медиана {statistics.median(sizes):.0f} max {max(sizes)} | мусор {100*junk/total:.1f}% | коротких {100*short/total:.1f}%")
    for t,c in ex: print(f"  [{t}] {c[:160]}")

def run_embed(targets, limit, refresh, only_docids, model_kind="minilm", batch=0):
    """batch>0 — дискретный режим: обработать не более `batch` НОВЫХ документов
    за вызов и выйти (для батч-драйвера с рестартом процесса). Возвращает число
    добавленных — драйвер крутит вызовы, пока не станет 0."""
    from sentence_transformers import SentenceTransformer
    import torch
    dev = "mps" if torch.backends.mps.is_available() else "cpu"
    # e5 — топовый для русского (1024-dim), требует префиксы query:/passage:.
    # Льём в отдельные коллекции laws_e5/case_law_e5 (БЕЗ chroma-EF, эмбеддинги
    # передаём сами), чтобы боевой 384-стор laws/case_law не трогать до переключения.
    prompt_doc = None  # для моделей с prompt_name (USER2)
    if model_kind == "user2":
        # deepvk/USER2-small — лёгкая (34M), сильная для RU, 384-dim, ctx 8192.
        # Префиксы через prompt_name (search_document/search_query). Отдельные
        # коллекции laws_u2/case_law_u2 (без chroma-EF, эмбеддинги передаём сами).
        model = SentenceTransformer("deepvk/USER2-small", device=dev)
        prefix = ""; suffix = "_u2"; prompt_doc = "search_document"
        import chromadb
        from chromadb.config import Settings
        client = chromadb.PersistentClient(path="/Users/legalai/projects/Contract-AI-System-/data/chromadb",
                                           settings=Settings(anonymized_telemetry=False))
        get_coll = lambda nm: client.get_or_create_collection(name=nm + suffix)
    elif model_kind == "e5":
        model = SentenceTransformer("intfloat/multilingual-e5-large", device=dev)
        prefix = "passage: "
        suffix = "_e5"
        import chromadb
        from chromadb.config import Settings
        client = chromadb.PersistentClient(path="/Users/legalai/projects/Contract-AI-System-/data/chromadb",
                                           settings=Settings(anonymized_telemetry=False))
        get_coll = lambda nm: client.get_or_create_collection(name=nm + suffix)  # без EF
    else:
        from src.services.admin_rag_retriever import get_collection
        model = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2", device=dev)
        prefix = ""
        get_coll = get_collection
    print(f"устройство: {dev}, модель: {model_kind}", flush=True)
    def embed(texts):
        if prompt_doc:
            # batch_size МАЛЫЙ: USER2=RuModernBERT (ctx 8192), при больших батчах
            # MPS OOM (живой сервис уже держит ~10 ГиБ). 32 — безопасно, модель лёгкая.
            return model.encode(texts, prompt_name=prompt_doc, batch_size=32,
                                convert_to_numpy=True, show_progress_bar=False).tolist()
        # batch_size крупнее → лучше утилизация MPS-GPU (e5-large на M4)
        return model.encode([prefix + t for t in texts], batch_size=192 if model_kind=="e5" else 128,
                            convert_to_numpy=True, show_progress_bar=False).tolist()
    total_added = 0
    for cname in targets:
        coll = get_coll(cname)
        if coll is None: print("нет коллекции", cname); continue
        files = collect_files(cname, limit=limit)
        print(f"=== EMBED {cname}: файлов {len(files)}, в коллекции {coll.count()} ===", flush=True)
        added=skipped=refreshed=0; t0=time.time()
        for i, f in enumerate(files, 1):
            if batch and total_added >= batch:
                print(f"  батч-лимит {batch} достигнут — стоп", flush=True); break
            fm, body = parse_md(f)
            if len(body) < MIN_BODY: continue
            did = docid_of(fm, f)
            if only_docids and did not in only_docids: continue
            exists = False
            try: exists = bool(coll.get(ids=[f"{did}:0"])["ids"])
            except Exception: pass
            if exists and not refresh: skipped+=1; continue
            if exists and refresh:
                coll.delete(where={"doc_id": did}); refreshed+=1
            ch = chunk_text(clean_body(body))
            if not ch: continue
            title=fm.get("title","")[:300]; cat=fm.get("category",""); url=fm.get("source_url","")
            ids=[f"{did}:{j}" for j in range(len(ch))]
            metas=[{"doc_id":did,"title":title,"category":cat,"source_url":url,"chunk":j} for j in range(len(ch))]
            for b in range(0,len(ch),256):
                sub=ch[b:b+256]
                coll.add(documents=sub, ids=ids[b:b+256], metadatas=metas[b:b+256], embeddings=embed(sub))
            added+=1; total_added+=1
            if i % 50 == 0:
                print(f"  [{i}/{len(files)}] +{added} skip{skipped} refr{refreshed} чанков~{coll.count()} {time.time()-t0:.0f}s", flush=True)
        print(f"ИТОГО {cname}: добавлено {added}, обновлено {refreshed}, пропущено {skipped}, чанков {coll.count()}", flush=True)
        if batch and total_added >= batch:
            break
    print(f"ADDED_TOTAL={total_added}", flush=True)
    return total_added

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["chunktest","embed"], default="chunktest")
    ap.add_argument("--collection", choices=["laws","case_law","all"], default="all")
    ap.add_argument("--sample", type=int, default=40)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--refresh", action="store_true", help="удалить старые чанки документа и заэмбедить заново")
    ap.add_argument("--only-docids", default="", help="через запятую: эмбедить только эти doc_id")
    ap.add_argument("--model", choices=["minilm","e5","user2"], default="minilm",
                    help="user2 = deepvk/USER2-small (384-dim, лёгкая, RU, коллекции *_u2)")
    ap.add_argument("--batch", type=int, default=0,
                    help="дискретно: обработать не более N новых док за вызов и выйти")
    a = ap.parse_args()
    targets = ["laws","case_law"] if a.collection=="all" else [a.collection]
    only = set(x.strip() for x in a.only_docids.split(",") if x.strip())
    if a.mode == "chunktest":
        for c in targets: chunktest(c, a.sample)
    else:
        run_embed(targets, a.limit, a.refresh, only, model_kind=a.model, batch=a.batch)
