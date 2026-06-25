# -*- coding: utf-8 -*-
"""ANSWER-EVAL: оценка КАЧЕСТВА ОТВЕТА (не только retrieval).
Триада LLM-судьи: Coverage / Groundedness / Factuality (веса 25/35/40).
Пайплайн на каждый вопрос: get_legal_context (рерайт вкл, прод-путь) →
ответ deepseek-chat с юр-промптом → судья deepseek-chat (JSON-вердикт по
нумерованным найденным фрагментам + эталонным ключевым пунктам).
Методика: habr/gram_ax 1020248 (чанки судье явным списком, JSON, код-проверки)."""
import os, sys, re, json
os.environ.setdefault("HF_HUB_OFFLINE", "1"); os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
sys.path.insert(0, "/Users/legalai/projects/Contract-AI-System-")
_key = os.environ.get("DSKEY", "").strip()
if not _key: print("НЕТ DSKEY"); sys.exit(1)
from config.settings import settings
settings.deepseek_api_key = _key
settings.rag_rewrite = True  # прод-путь: авто-рерайт включён
from src.services.admin_rag_retriever import get_legal_context
from src.services.llm_gateway import LLMGateway

gw = LLMGateway(provider="deepseek", model="deepseek-chat")

# (id, разговорный вопрос, [эталонные ключевые пункты])
QUESTIONS = [
 ("товар-брак", "как вернуть деньги за бракованный телефон",
  ["право на возврат/замену по ЗоЗПП", "для технически сложного товара — 15 дней или существенный недостаток",
   "письменная претензия продавцу", "экспертиза за счёт продавца"]),
 ("залив", "соседи затопили квартиру кто должен возмещать",
  ["виновное лицо возмещает вред (ГК 1064/1082)", "если виновата УК — отвечает она",
   "зафиксировать актом, оценить ущерб", "досудебная претензия, затем суд"]),
 ("развод-дети", "как развестись если есть несовершеннолетний ребёнок",
  ["расторжение через суд (СК ст. 21)", "решается вопрос о детях и алиментах", "госпошлина"]),
 ("коллекторы", "имеет ли право коллектор звонить моим родственникам",
  ["230-ФЗ регулирует возврат просроченной задолженности", "взаимодействие с третьими лицами только с их согласия",
   "ограничения частоты и времени звонков", "должник вправе отказаться от взаимодействия"]),
 ("неуплата-алиментов", "что грозит за неуплату алиментов",
  ["неустойка (СК ст. 115)", "административная ответственность (КоАП 5.35.1)",
   "уголовная ответственность (УК 157)", "ограничение выезда/прав"]),
 ("увольнение-беременной", "могут ли уволить беременную женщину",
  ["запрет увольнения по инициативе работодателя (ТК ст. 261)", "исключение — ликвидация организации",
   "срочный договор продлевается до окончания беременности"]),
 ("наследство", "как оформить наследство после смерти отца",
  ["обратиться к нотариусу в течение 6 месяцев (ГК 1154)", "наследование по закону, очередь (ГК 1141)",
   "заявление о принятии наследства", "свидетельство о праве на наследство"]),
 ("дду-просрочка", "застройщик задерживает сдачу квартиры по дду",
  ["214-ФЗ о долевом строительстве", "неустойка за просрочку передачи (ст. 6)",
   "претензия застройщику", "право расторгнуть договор"]),
 ("приватизация", "как приватизировать квартиру",
  ["Закон 1541-1 о приватизации", "бесплатно и однократно", "согласие всех проживающих",
   "договор передачи и регистрация права"]),
 ("страховка-кредит", "можно ли вернуть навязанную страховку по кредиту",
  ["период охлаждения 14 дней", "возврат при досрочном погашении кредита", "заявление страховщику"]),
 ("пьяное-вождение", "что грозит за вождение в нетрезвом виде",
  ["КоАП 12.8 — штраф 30000 и лишение прав 1.5-2 года", "повторно — уголовная (УК 264.1)",
   "отказ от освидетельствования приравнен к опьянению"]),
 ("долг-расписка", "как взыскать долг по расписке через суд",
  ["договор займа подтверждается распиской (ГК 808)", "досудебная претензия",
   "исковое заявление в суд", "проценты по ст. 395"]),
]

SYS_ANSWER = (
    "Ты — юридический ассистент по российскому праву. Ответь на вопрос пользователя, "
    "опираясь ТОЛЬКО на предоставленный контекст из нормативных документов и судебной "
    "практики. Если в контексте нет ответа — честно скажи об этом. Указывай конкретные "
    "статьи/законы. Кратко, по делу, 4-8 предложений.")

def answer(q, ctx):
    prompt = f"КОНТЕКСТ:\n{ctx}\n\nВОПРОС: {q}\n\nОТВЕТ:"
    out = gw.call(prompt=prompt, system_prompt=SYS_ANSWER,
                  response_format="text", temperature=0.0, max_tokens=400)
    return (out if isinstance(out, str) else str(out)).strip()

SYS_JUDGE = (
    "Ты — строгий оценщик качества ответов юридического ассистента. Тебе дают: вопрос, "
    "нумерованные НАЙДЕННЫЕ ФРАГМЕНТЫ (контекст), ОТВЕТ ассистента и ЭТАЛОННЫЕ ПУНКТЫ. "
    "Оцени по трём осям от 0.0 до 1.0:\n"
    "• coverage — доля эталонных пунктов, раскрытых в ответе;\n"
    "• groundedness — насколько КАЖДОЕ утверждение ответа подтверждается найденными фрагментами "
    "(штрафуй за факты, которых нет в контексте);\n"
    "• factuality — юридическая корректность ответа по существу.\n"
    "Верни СТРОГО JSON одной строкой: "
    '{"coverage":0.0,"groundedness":0.0,"factuality":0.0,"issues":["..."]}')

def judge(q, ctx, ans, gold):
    chunks = re.split(r'\n\n(?=\[)', ctx)
    numbered = "\n".join(f"[{i+1}] {c[:500]}" for i, c in enumerate(chunks))
    gold_s = "\n".join(f"- {g}" for g in gold)
    prompt = (f"ВОПРОС: {q}\n\nНАЙДЕННЫЕ ФРАГМЕНТЫ:\n{numbered}\n\n"
              f"ЭТАЛОННЫЕ ПУНКТЫ:\n{gold_s}\n\nОТВЕТ АССИСТЕНТА:\n{ans}\n\nJSON-оценка:")
    out = gw.call(prompt=prompt, system_prompt=SYS_JUDGE,
                  response_format="text", temperature=0.0, max_tokens=300)
    s = out if isinstance(out, str) else str(out)
    m = re.search(r'\{.*\}', s, re.DOTALL)
    if not m: return None
    try: return json.loads(m.group(0))
    except Exception: return None

# код-проверки (не через LLM): цитирует ли ответ закон/статью; не пустой
def code_checks(ans):
    cites = bool(re.search(r'ст\.?\s*\d+|N\s*\d+-ФЗ|кодекс|закон', ans, re.I))
    nonempty = len(ans) > 40
    return {"cites_law": cites, "nonempty": nonempty}

print(f"{'='*72}\nANSWER-EVAL (триада, веса cov.25/gr.35/fact.40), вопросов: {len(QUESTIONS)}\n{'='*72}", flush=True)
agg = {"coverage": 0.0, "groundedness": 0.0, "factuality": 0.0}
weighted_sum = 0.0; n_ok = 0; low_ground = []
for qid, q, gold in QUESTIONS:
    ctx = get_legal_context(q, collections=["laws", "case_law"], n_results=3)
    ans = answer(q, ctx)
    v = judge(q, ctx, ans, gold)
    cc = code_checks(ans)
    if not v:
        print(f"  [{qid}] СУДЬЯ НЕ ВЕРНУЛ JSON", flush=True); continue
    n_ok += 1
    cov, gr, fa = float(v.get("coverage",0)), float(v.get("groundedness",0)), float(v.get("factuality",0))
    agg["coverage"]+=cov; agg["groundedness"]+=gr; agg["factuality"]+=fa
    w = 0.25*cov + 0.35*gr + 0.40*fa
    weighted_sum += w
    if gr < 0.7: low_ground.append((qid, gr, v.get("issues", [])))
    flag = "⚠️" if gr < 0.7 else ("  " if w >= 0.7 else " ·")
    cite = "" if cc["cites_law"] else " [нет ссылки на закон]"
    print(f"{flag} [{qid}] cov={cov:.2f} gr={gr:.2f} fact={fa:.2f} → {w:.2f}{cite}", flush=True)

if n_ok:
    print(f"\n{'─'*72}", flush=True)
    print(f"СРЕДНЕЕ по {n_ok}: coverage={agg['coverage']/n_ok:.2f}  "
          f"groundedness={agg['groundedness']/n_ok:.2f}  factuality={agg['factuality']/n_ok:.2f}", flush=True)
    print(f"ИТОГОВЫЙ ВЗВЕШЕННЫЙ БАЛЛ: {weighted_sum/n_ok:.2f} / 1.00", flush=True)
    if low_ground:
        print(f"\n⚠️  НИЗКАЯ ОПОРА НА КОНТЕКСТ (риск галлюцинаций), gr<0.7:", flush=True)
        for qid, gr, issues in low_ground:
            print(f"   • [{qid}] gr={gr:.2f}: {'; '.join(issues[:2])}", flush=True)
