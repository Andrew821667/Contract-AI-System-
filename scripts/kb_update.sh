#!/bin/sh
# Регулярное обновление БЗ КС (скачивание новых из К+ → ingest → embed → relink).
# Запуск по cron в ночном окне. Статус → JSON (читает админка; Telegram с мини
# заблокирован, поэтому уведомление через статус-файл/БД). Single-instance lock.
CT=/Users/legalai/projects/OpenClaw_consultant-tools
KS=/Users/legalai/projects/Contract-AI-System-
DATA=/Users/legalai/consultant-data
LOG=$DATA/kb_update.log
STATUS=$DATA/kb_update_status.json
LOCK=/tmp/kb_update.lock
PYC=$CT/.venv/bin/python
PYK=$KS/.venv/bin/python
DB=$KS/contract_ai.db

if [ -f "$LOCK" ] && kill -0 "$(cat $LOCK 2>/dev/null)" 2>/dev/null; then exit 0; fi
echo $$ > $LOCK; trap 'rm -f $LOCK' EXIT
STARTED=$(date -u +%Y-%m-%dT%H:%M:%SZ)
write_status() {  # state message [extra]
  printf '{"started":"%s","finished":"%s","state":"%s","message":"%s"%s}\n' \
    "$STARTED" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$1" "$2" "$3" > "$STATUS"
}
fail() { echo "$(date) FAIL: $1" >> $LOG; write_status error "$1"; exit 1; }

echo "=== $(date) KB UPDATE START ===" >> $LOG
write_status running "скачивание обновлений из К+"

# 1. Скачивание НОВЫХ документов (skip-existing). REPLACE редакций — отдельным
#    edition-diff (TODO), здесь — добор новых.
cd "$CT" || fail "consultant-tools недоступен"
$PYC modules/federal_laws.py --all --only fz --skip-amendments >> $LOG 2>&1 || echo "warn: fz download" >> $LOG
$PYC -m modules.decrees >> $LOG 2>&1 || echo "warn: decrees download" >> $LOG

# 2. Ingest (идемпотентно; новые добавятся, существующие пропустятся)
cd "$KS" || fail "КС недоступна"
git pull -q origin main >> $LOG 2>&1
write_status running "заливка в граф"
$PYK -m src.core.graph_rag.importers.consultant_importer \
     --kind kodeksy --kind fkz --kind fz --kind decrees --kind court --no-phase2 >> $LOG 2>&1 \
     || fail "ошибка ingest"

# 3. Embed новых (resume)
write_status running "эмбеддинг новых документов"
$PYK scripts/kb_embed.py --mode embed --collection all >> $LOG 2>&1 || fail "ошибка embed"

# 4. Relink (decree→law, court→law)
write_status running "пересборка связей"
$PYK scripts/kb_relink.py "$DB" >> $LOG 2>&1 || echo "warn: relink" >> $LOG

DOCS=$($PYK -c "import sqlite3;print(sqlite3.connect('$DB',timeout=30).execute('select count(*) from graph_documents').fetchone()[0])" 2>/dev/null)
echo "=== $(date) KB UPDATE DONE (docs=$DOCS) ===" >> $LOG
write_status ok "обновление завершено" ",\"documents\":$DOCS"
