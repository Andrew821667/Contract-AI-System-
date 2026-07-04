# -*- coding: utf-8 -*-
"""v4: тело статьи = текст после строки-заголовка «<КОДЕКС> РФ Статья N. ...»
(маркер начала тела в .md К+); `(?!\d)` чтобы N не матчился на N.1;
fallback — после последнего повтора «Статья N.»."""
import os, re, json, glob
MDDIRS=["/Users/legalai/consultant-data/kodeksy/converted-md","/Users/legalai/consultant-data/federal-laws/fz/converted-md"]
CODES=['5142','9027','34683','8982','19671','10699','39570','51057','34661','19702','33773','34154','34481','37800','64629']
def find_md(did):
    for d in MDDIRS:
        for f in glob.glob(d+"/*.md"):
            try:
                if f'cons_doc_LAW_{did}/' in open(f,encoding='utf-8',errors='replace').read(1200): return f
            except: pass
def clean(t):
    t=re.sub(r'\[([^\]]+)\]\([^)]+\)',r'\1',t)
    t=re.sub(r'\(в ред\.[^)]*\)|\(см\. текст[^)]*\)|Позиции высших судов[^\n]*|Путеводител[^\n]*|Перспективы и риски[^\n]*|Вопросы судебной практики[^\n]*|Готовое решение[^\n]*|Подготовлен[аы] редакци[яи][^\n]*|КонсультантПлюс|>>>','',t)
    out=[]
    for ln in t.split('\n'):
        l=ln.strip()
        if l=='См. также:' or re.match(r'^ч\.\s*\d',l) or re.match(r'^"[А-ЯЁ][^"]{5,}',l): continue
        out.append(ln)
    return re.sub(r'[ \t]+',' ',re.sub(r'\n{2,}','\n','\n'.join(out))).strip()
OUT={}
for did in CODES:
    f=find_md(did)
    if not f: print(did,"MD НЕ НАЙДЕН"); continue
    raw=re.sub(r'^---.*?---','',open(f,encoding='utf-8',errors='replace').read(),count=1,flags=re.DOTALL)
    parts=re.split(r'(?m)^\s*\*{0,2}\s*(?:#+\s*)?Статья\s+(\d+(?:\.\d+)?)\.(?!\d)', raw); A={}
    for i in range(1,len(parts)-1,2):
        num=parts[i]; seg=parts[i+1]; esc=re.escape(num)
        m=re.search(rf'(?m)^.{{0,20}}РФ\s+Стать[яи]\s+{esc}\.(?!\d)[^\n]*$', seg)
        if m: body=seg[m.end():]
        else:
            reps=list(re.finditer(rf'Стать[яи]\s+{esc}\.(?!\d)[^\n]*', seg))
            body=seg[reps[-1].end():] if reps else seg
        b=clean(body)
        if len(b)>60 and len(b)>len(A.get(num,'')): A[num]=b
    OUT[did]={k:v[:1200] for k,v in A.items()}
json.dump(OUT,open('/Users/legalai/projects/Contract-AI-System-/data/article_texts.json','w',encoding='utf-8'),ensure_ascii=False)
print("ИТОГО:",len(OUT),"кодексов,",sum(len(v) for v in OUT.values()),"статей,",round(os.path.getsize('/Users/legalai/projects/Contract-AI-System-/data/article_texts.json')/1e6,1),"MB")
