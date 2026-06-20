#!/bin/sh
# Полный РЕЗЮМИРУЕМЫЙ реэмбеддинг всех документов laws_u2/case_law_u2 с рестартом
# процесса на каждый батч (изоляция сбоев/памяти) и чекпоинтом по doc_id.
# Нужен при смене схемы эмбеддинга (contextual chunks / новая модель), где
# обычный skip-existing драйвер не годится (там --refresh не чекпоинтит).
#   kb_reembed_all.sh [model=user2] [batch_docs=150]
KS=/Users/legalai/projects/Contract-AI-System-
PY=$KS/.venv/bin/python
MODEL=${1:-user2}; BATCH=${2:-150}
DATA=/Users/legalai/consultant-data
IDS=$DATA/reembed_${MODEL}_ids.txt        # все doc_id (universe)
DONE=$DATA/reembed_${MODEL}_done.txt       # уже обработанные
LOG=$DATA/reembed_${MODEL}.log
LOCK=/tmp/kb_reembed_${MODEL}.lock
if [ -f "$LOCK" ] && kill -0 "$(cat $LOCK 2>/dev/null)" 2>/dev/null; then echo "уже запущен"; exit 0; fi
echo $$ > $LOCK; trap 'rm -f $LOCK' EXIT
cd "$KS" || exit 1
echo "=== $(date) REEMBED-ALL start model=$MODEL batch=$BATCH ===" >> $LOG

# 1) Один раз собрать перечень всех doc_id из u2-коллекций (universe).
if [ ! -s "$IDS" ]; then
  HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 $PY - "$MODEL" > "$IDS" <<'PYEOF'
import sys, chromadb
from chromadb.config import Settings
suf = "_u2" if sys.argv[1]=="user2" else ("_e5" if sys.argv[1]=="e5" else "")
cl = chromadb.PersistentClient(path="/Users/legalai/projects/Contract-AI-System-/data/chromadb",
                               settings=Settings(anonymized_telemetry=False))
seen=set()
for nm in ("laws"+suf, "case_law"+suf):
    try: c=cl.get_or_create_collection(name=nm)
    except Exception: continue
    n=c.count(); off=0
    while off < n:
        b=c.get(limit=10000, offset=off, include=["metadatas"])
        for m in b["metadatas"]:
            d=(m or {}).get("doc_id")
            if d and d not in seen: seen.add(d); print(d)
        off+=10000
PYEOF
  echo "$(date) universe doc_id: $(wc -l < $IDS)" >> $LOG
fi
[ -f "$DONE" ] || : > "$DONE"

# 2) Крутить батчи: взять BATCH не-сделанных doc_id, реэмбед с --refresh, рестарт.
fails=0
while :; do
  TODO=$(grep -F -x -v -f "$DONE" "$IDS" | head -n "$BATCH")
  [ -z "$TODO" ] && { echo "$(date) === ГОТОВО: все реэмбеднуты ===" >> $LOG; touch $DATA/reembed_${MODEL}_done.flag; break; }
  CSV=$(printf '%s' "$TODO" | paste -sd, -)
  HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 $PY scripts/kb_embed.py \
      --mode embed --collection all --model "$MODEL" --refresh --only-docids "$CSV" >> $LOG 2>&1
  rc=$?
  if [ "$rc" -ne 0 ]; then
    fails=$((fails+1)); echo "$(date) батч упал rc=$rc (fails=$fails), пауза" >> $LOG; sleep 15
    [ "$fails" -ge 5 ] && { echo "$(date) СТОП: 5 сбоев подряд" >> $LOG; exit 1; }
    continue
  fi
  fails=0
  printf '%s\n' "$TODO" >> "$DONE"
  echo "$(date) батч ок: сделано $(wc -l < $DONE)/$(wc -l < $IDS)" >> $LOG
done
