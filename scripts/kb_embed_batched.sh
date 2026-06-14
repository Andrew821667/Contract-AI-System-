#!/bin/sh
# Дискретная векторизация: батчи с РЕСТАРТОМ процесса на каждый батч.
# Изолирует сбои, освобождает память, чекпоинт после каждого батча (per-doc
# commit + skip-existing резюм). Крутит, пока есть новые документы.
#   kb_embed_batched.sh [model=e5] [batch=300]
KS=/Users/legalai/projects/Contract-AI-System-
PY=$KS/.venv/bin/python
MODEL=${1:-e5}; BATCH=${2:-300}
LOG=/Users/legalai/consultant-data/embed_${MODEL}_batched.log
LOCK=/tmp/kb_embed_batched.lock
if [ -f "$LOCK" ] && kill -0 "$(cat $LOCK 2>/dev/null)" 2>/dev/null; then echo "уже запущен"; exit 0; fi
echo $$ > $LOCK; trap 'rm -f $LOCK' EXIT
cd "$KS" || exit 1
echo "=== $(date) BATCHED EMBED start model=$MODEL batch=$BATCH ===" >> $LOG
pass=0; fails=0
while :; do
  pass=$((pass+1))
  out=$(HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 $PY scripts/kb_embed.py \
        --mode embed --collection all --model "$MODEL" --batch "$BATCH" 2>>$LOG)
  rc=$?
  added=$(printf '%s' "$out" | grep -oE 'ADDED_TOTAL=[0-9]+' | tail -1 | cut -d= -f2)
  echo "$(date) batch#$pass rc=$rc added=${added:-ERR}" >> $LOG
  if [ "$rc" -ne 0 ]; then
    fails=$((fails+1)); echo "  батч упал (fails=$fails), повтор после паузы" >> $LOG; sleep 15
    [ "$fails" -ge 5 ] && { echo "$(date) СТОП: 5 сбоев подряд" >> $LOG; exit 1; }
    continue
  fi
  fails=0
  [ "${added:-0}" -eq 0 ] 2>/dev/null && { echo "$(date) === ГОТОВО: новых нет ===" >> $LOG; break; }
done
