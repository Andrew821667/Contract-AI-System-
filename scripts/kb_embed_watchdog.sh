#!/bin/sh
# Watchdog (cron каждые 30 мин): если e5-векторизация НЕ завершена и драйвер не
# работает — поднять caffeinate + батч-драйвер (резюмирует). Защита долгого
# прогона от сна/перезагрузки мини.
MODEL=e5; BATCH=192
DATA=/Users/legalai/consultant-data
KS=/Users/legalai/projects/Contract-AI-System-
[ -f "$DATA/embed_${MODEL}_done" ] && exit 0          # уже завершено
pgrep -f kb_embed_batched >/dev/null && exit 0          # уже идёт
pgrep -x caffeinate >/dev/null || nohup caffeinate -is >/dev/null 2>&1 &
nohup sh "$KS/scripts/kb_embed_batched.sh" "$MODEL" "$BATCH" >> "$DATA/kb_embed_batched_nohup.out" 2>&1 &
echo "$(date) watchdog: поднял драйвер" >> "$DATA/embed_${MODEL}_batched.log"
