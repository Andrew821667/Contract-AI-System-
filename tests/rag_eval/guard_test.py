# -*- coding: utf-8 -*-
"""GUARD-TEST: детерминированная метрика ВЫДУМАННЫХ ссылок под тремя answer-промптами.

Без LLM-судьи — чистая код-проверка (методика gram_ax): номер статьи, названный
в ОТВЕТЕ, но отсутствующий дословно в найденном КОНТЕКСТЕ = выдуманный. Номер,
который в контексте есть = законный (реальная опора). Цель промпта — минимум
выдуманных при сохранении законных.

Три arm'а одного и того же прод-пайплайна (get_legal_context: rewrite+hop, n=3,
max_chars=2000; ответ deepseek temp=0.0):
  BASE — старый промпт без guard («ссылайся на законы, указывай номера») →
         провоцирует цитаты ПО ПАМЯТИ (исторически 4 выдуманных).
  SOFT — прод-guard: номер ТОЛЬКО если он в контексте, иначе — словами
         (прод-цель: 0 выдуманных при сохранении законных).
  HARD — жёсткий запрет любых номеров → 0 выдуманных, но режет и законные
         (пере-зажим, в прод НЕ берём — для контраста).

Контекст на вопрос считается ОДИН раз (он не зависит от answer-промпта) и
переиспользуется всеми arm'ами. Прод не трогает (read-only retrieval).

Запуск (под legalai, прод-окружение):
  HOME=/Users/legalai HF_HOME=/Users/legalai/.cache/huggingface \
  HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 DSKEY=<deepseek_key> \
  .venv/bin/python tests/rag_eval/guard_test.py
"""
import os, sys, re
os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
sys.path.insert(0, "/Users/legalai/projects/Contract-AI-System-")

_key = os.environ.get("DSKEY", "").strip()
if not _key:
    print("НЕТ DSKEY"); sys.exit(1)

from config.settings import settings
settings.deepseek_api_key = _key
settings.rag_rewrite = True      # прод-путь
settings.rag_graph_hop = True    # прод-путь (нормы в бюджете контекста)

from src.services.admin_rag_retriever import get_legal_context
from src.services.llm_gateway import LLMGateway

gw = LLMGateway(provider="deepseek", model="deepseek-chat")

# Заголовок прод-промпта без строки о ссылках — строка о ссылках у каждого arm'а своя.
_HEADER = (
    "Ты — AI-ассистент юридической системы Contract AI System. "
    "Ты помогаешь юристам анализировать договоры, выявлять риски, предлагать "
    "формулировки и отвечать на вопросы о работе системы.\n\n"
    "Правила:\n- Отвечай на русском языке\n- Будь конкретным и полезным\n"
    "- Ссылайся на конкретные пункты документа, если они есть в контексте\n"
)
_TAIL = "- Если не знаешь ответ, честно скажи об этом\n"

RULES = {
    # старый прод-промпт (до guard'а) — провоцировал цитаты по памяти
    "BASE": "- Ссылайся на конкретные статьи и законы, указывай их номера\n",
    # прод-guard (softened): номер только если он в контексте
    "SOFT": ("- Ссылайся на закон/норму из правовой базы; номер статьи или закона "
             "указывай ТОЛЬКО если он есть в контексте — если номера в контексте "
             "нет, не придумывай его, опиши норму своими словами\n"),
    # пере-зажим (для контраста, в прод не берём)
    "HARD": ("- НЕ указывай номера статей или законов ни при каких условиях; "
             "описывай нормы только своими словами\n"),
}

def sys_prompt(arm: str) -> str:
    return _HEADER + RULES[arm] + _TAIL

# Детерминированная проверка ссылок: «статья N» / «ст. N» (в т.ч. N.M).
ART = re.compile(r"(?:стать[еийяю]\w*|ст\.)\s*(\d+(?:\.\d+)?)", re.I)

def refs(text: str):
    return set(ART.findall(text or ""))

def split_refs(ans: str, ctx: str):
    """Возвращает (законные, выдуманные): номера из ответа, которые ЕСТЬ / которых
    НЕТ в найденном контексте."""
    ctx_refs = refs(ctx)
    ans_refs = refs(ans)
    grounded = sorted(ans_refs & ctx_refs)
    invented = sorted(ans_refs - ctx_refs)
    return grounded, invented

# Разговорные вопросы (общие с answer_eval_paired — многие ретривят нормы, где
# точный номер статьи в контекст не попадает → соблазн процитировать по памяти).
QUESTIONS = [
    "в каких случаях суд может уменьшить неустойку",
    "как делится имущество супругов при разводе",
    "за что могут лишить родительских прав",
    "что грозит работнику за прогул",
    "какая ответственность за мошенничество",
    "соседи сверху затопили квартиру, что делать",
    "коллекторы звонят моим родственникам по моему долгу, законно ли это",
    "сколько алиментов положено на одного ребенка",
    "купил телефон, он сломался через месяц — что можно требовать",
    "чем задаток отличается от аванса при покупке квартиры",
    "могут ли уволить беременную сотрудницу",
    "что будет, если вовремя не оплатить административный штраф",
]

ARMS = ["BASE", "SOFT", "HARD"]

def answer(arm: str, q: str, ctx: str) -> str:
    sp = sys_prompt(arm) + (f"\n\n# Правовая база и база знаний\n{ctx}" if ctx else "")
    a = gw.call(prompt=f"Пользователь: {q}", system_prompt=sp,
                response_format="text", temperature=0.0, max_tokens=700)
    return (a if isinstance(a, str) else str(a)).strip()

def main():
    totals = {arm: {"grounded": 0, "invented": 0} for arm in ARMS}
    per_q = []
    for q in QUESTIONS:
        ctx = get_legal_context(q, collections=["laws", "case_law", "knowledge"],
                                n_results=3, max_chars=2000)
        row = {"q": q[:40]}
        for arm in ARMS:
            g, inv = split_refs(answer(arm, q, ctx), ctx)
            totals[arm]["grounded"] += len(g)
            totals[arm]["invented"] += len(inv)
            row[arm] = (len(g), inv)
        per_q.append(row)
        print(f"[{row['q']:40}] "
              + "  ".join(f"{arm}: закон={row[arm][0]} выдум={row[arm][1]}" for arm in ARMS),
              flush=True)

    print("\n" + "=" * 72)
    print(f"GUARD-TEST (детерминир., {len(QUESTIONS)} вопросов, прод-путь rewrite+hop)")
    print("=" * 72)
    for arm in ARMS:
        t = totals[arm]
        print(f"  {arm:4}: выдуманных={t['invented']:2}  законных={t['grounded']:2}")
    print("\nПрод-цель — SOFT: минимум выдуманных при сохранении законных.")

if __name__ == "__main__":
    main()
