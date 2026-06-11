# -*- coding: utf-8 -*-
"""Быстрая прямая линковка (без медленной Фазы 2 --relink) поверх SQLite:
  decree→law : текст «Постановлением Правительства РФ от ДАТА N» → акт-цель
  court→law  : облачные ссылки судебных актов online.cgi?base=LAW&n=NNN → закон
Идемпотентно (дедуп по существующим references). Запуск после заливок.
"""
import sqlite3, re, uuid, sys
from datetime import datetime
DB = sys.argv[1] if len(sys.argv) > 1 else "/Users/legalai/projects/Contract-AI-System-/contract_ai.db"

SUBORD_RE = re.compile(
    r'(постановлени|распоряжени|указ)\w*\s+(Правительств|Президент)\w*\s+'
    r'(?:Российской\s+Федерации|РФ)\s+от\s+(\d{2}\.\d{2}\.\d{4})\s+N\s*([0-9][\w\-/.]*)', re.I)
SUBORD_TITLE_RE = SUBORD_RE
CLOUD_LINK = re.compile(r'online\.cgi\?[^)\s"\']+'); NID = re.compile(r'[?&]n=(\d+)')

def kind(stem, organ):
    s, o = stem.lower(), organ.lower()
    if s.startswith('постановлени') and o.startswith('правительств'): return 'government_decree'
    if s.startswith('распоряжени') and o.startswith('правительств'): return 'government_order'
    if s.startswith('указ') and o.startswith('президент'): return 'presidential_decree'
    return None

def main():
    c = sqlite3.connect(DB, timeout=60)
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")
    docid2gdoc, root_of = {}, {}
    for did, sf in c.execute("select id, source_file from graph_documents where layer='npa' and status='active'"):
        m = re.search(r'cons_doc_LAW_(\d+)', sf or '')
        if m: docid2gdoc[m.group(1)] = did
    for nid, did in c.execute("select id, document_id from graph_nodes where node_type='document'"):
        root_of[did] = nid
    existing = {r[0] for r in c.execute("select source_id||'|'||target_id from graph_edges where edge_type='references'")}
    rows = []; seen = set()
    def add(src, tgt, ev, rat):
        if not tgt or src == tgt: return
        k = f"{src}|{tgt}"
        if k in existing or k in seen: return
        seen.add(k)
        rows.append((str(uuid.uuid4()), src, tgt, 'references', 'fact', 'machine_extracted',
                     ev[:160], rat, 0.9, 'rule', now, now))
    # карта подзаконки по реквизитам
    subord = {}
    for did, title, dt in c.execute("select id,title,document_type from graph_documents where document_type in ('government_decree','government_order','presidential_decree') and status='active'"):
        tm = SUBORD_TITLE_RE.search(title or '')
        if tm:
            kk = kind(tm.group(1), tm.group(2))
            if kk: subord.setdefault((kk, tm.group(3), tm.group(4).rstrip('.').lower()), did)
    # (А) законы/НПА → подзаконка по реквизитам
    cand = c.execute("select id, document_id, text from graph_nodes where text like '%равительства РФ от %' or text like '%равительства Российской Федерации от %' or text like '%резидента РФ от %' or text like '%резидента Российской Федерации от %'").fetchall()
    for nid, ndoc, text in cand:
        if not text: continue
        for m in SUBORD_RE.finditer(text):
            kk = kind(m.group(1), m.group(2))
            if not kk: continue
            tgt = subord.get((kk, m.group(3), m.group(4).rstrip('.').lower()))
            if tgt and tgt != ndoc: add(nid, root_of.get(tgt), m.group(0), f'реквизит → {kk}')
    n_sub = len(rows)
    # (Б) судебная практика → закон по облачным ссылкам base=LAW&n=
    court = [r[0] for r in c.execute("select id from graph_documents where document_type='court_practice'")]
    for i in range(0, len(court), 400):
        ch = court[i:i+400]; qm = ",".join("?"*len(ch))
        for nid, ndoc, text in c.execute(f"select id,document_id,text from graph_nodes where document_id in ({qm}) and text like '%online.cgi%'", ch):
            if not text: continue
            for link in CLOUD_LINK.findall(text):
                if 'base=LAW' not in link: continue
                mm = NID.search(link)
                if not mm: continue
                tgt = docid2gdoc.get(mm.group(1))
                if tgt and tgt != ndoc: add(nid, root_of.get(tgt), link, 'court→law')
    c.executemany("insert into graph_edges (id,source_id,target_id,edge_type,edge_class,status,evidence,rationale,confidence,extracted_by,created_at,updated_at) values (?,?,?,?,?,?,?,?,?,?,?,?)", rows)
    c.commit()
    print(f"RELINK: всего новых рёбер {len(rows)} (подзаконка→{n_sub}, court→law {len(rows)-n_sub}); рёбер в графе {c.execute('select count(*) from graph_edges').fetchone()[0]}")

if __name__ == "__main__":
    main()
