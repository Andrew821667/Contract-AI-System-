# -*- coding: utf-8 -*-
"""Замер pool-union: raw vs replace vs UNION (get_legal_context aux_query=рерайт).
Реальный deepseek-chat. Одни и те же рерайты для всех вариантов."""
import os, sys, re
os.environ.setdefault("HF_HUB_OFFLINE", "1"); os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
sys.path.insert(0, "/Users/legalai/projects/Contract-AI-System-"); sys.path.insert(0, "/tmp")
_key = os.environ.get("DSKEY", "").strip()
if not _key: print("НЕТ DSKEY"); sys.exit(1)
from config.settings import settings
settings.deepseek_api_key = _key
from src.services.admin_rag_retriever import get_legal_context
from src.services.llm_gateway import LLMGateway
from rageval_paired import PAIRS

SYS = ("Ты — помощник юридического поиска по российскому праву. Перепиши бытовой "
       "вопрос пользователя в краткий поисковый запрос на языке закона: укажи область "
       "права и ключевые правовые термины/институты (как в названиях статей кодексов). "
       "НЕ отвечай на вопрос. Верни ТОЛЬКО переписанный запрос одной строкой, без кавычек.")
FEWSHOT = ("Примеры (для других тем):\n"
    "Вопрос: сколько времени есть на возврат денег за авиабилет\n"
    "Запрос: возврат провозной платы при отказе пассажира от воздушной перевозки\n\n"
    "Вопрос: что будет если не платить транспортный налог\n"
    "Запрос: ответственность за неуплату транспортного налога, взыскание недоимки\n\n"
    "Вопрос: {q}\nЗапрос:")
gw = LLMGateway(provider="deepseek", model="deepseek-chat")

def rewrite(q):
    out = gw.call(prompt=FEWSHOT.format(q=q), system_prompt=SYS,
                  response_format="text", temperature=0.0, max_tokens=120)
    s = out if isinstance(out, str) else str(out)
    return s.strip().strip('"').split("\n")[0].strip()

def hit(q, exp, n=3, aux=None):
    ctx = get_legal_context(q, collections=["laws", "case_law"], n_results=n, aux_query=aux)
    titles = re.findall(r'\[(?:Законы и НПА|Судебная практика)\] — ([^\n]+)', ctx)
    return any(re.search(exp, t, re.I) for t in titles)

raw_ok = rep_ok = uni_ok = 0
g_uni = []; l_uni = []
for topic, aq, cq, exp in PAIRS:
    rq = rewrite(cq)
    r_raw = hit(cq, exp)
    r_rep = hit(rq, exp)
    r_uni = hit(cq, exp, aux=rq)
    raw_ok += r_raw; rep_ok += r_rep; uni_ok += r_uni
    if r_uni and not r_raw: g_uni.append((topic, cq, rq))
    if r_raw and not r_uni: l_uni.append((topic, cq, rq))

N = len(PAIRS)
print(f"\n{'='*72}", flush=True)
print(f"raw:                  {raw_ok}/{N} = {100*raw_ok/N:.0f}% (top-3)", flush=True)
print(f"REPLACE (рерайт):     {rep_ok}/{N} = {100*rep_ok/N:.0f}%", flush=True)
print(f"POOL-UNION:           {uni_ok}/{N} = {100*uni_ok/N:.0f}%   (+{len(g_uni)} / -{len(l_uni)})", flush=True)
print(f"\n=== UNION выигрыш (raw✗ → union✓) ===", flush=True)
for t, cq, rq in g_uni: print(f"  • [{t}] «{cq}» → «{rq}»", flush=True)
print(f"\n=== UNION регресс (raw✓ → union✗) ===", flush=True)
for t, cq, rq in l_uni: print(f"  • [{t}] «{cq}» → «{rq}»", flush=True)
if not l_uni: print("  (нет регрессий)", flush=True)
