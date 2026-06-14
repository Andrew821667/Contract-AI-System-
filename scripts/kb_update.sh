#!/bin/sh
# Регулярное обновление БЗ КС. Cron в ночном окне. Статус → JSON (для админки;
# Telegram с legalai заблокирован). Single-instance lock.
#   1) edition-diff: изменённые редакции → перекачка → манифест changed_docids
#   2) добор новых документов (skip-existing)
#   3) ingest: новые (skip) + изменённые (--update --only-docids)
#   4) embed: новые (resume) + изменённые (--refresh --only-docids)
#   5) relink → статус
CT=/Users/legalai/projects/OpenClaw_consultant-tools
KS=/Users/legalai/projects/Contract-AI-System-
DATA=/Users/legalai/consultant-data
LOG=$DATA/kb_update.log
STATUS=$DATA/kb_update_status.json
MANIFEST=$DATA/refs/changed_docids.txt
LOCK=/tmp/kb_update.lock
PYC=$CT/.venv/bin/python
PYK=$KS/.venv/bin/python
DB=$KS/contract_ai.db

if [ -f "$LOCK" ] && kill -0 "$(cat $LOCK 2>/dev/null)" 2>/dev/null; then exit 0; fi
echo $$ > $LOCK; trap 'rm -f $LOCK' EXIT
STARTED=$(date -u +%Y-%m-%dT%H:%M:%SZ)
status() { printf '{"started":"%s","finished":"%s","state":"%s","message":"%s"%s}\n' \
  "$STARTED" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$1" "$2" "$3" > "$STATUS"; }
fail() { echo "$(date) FAIL: $1" >> $LOG; status error "$1"; exit 1; }

echo "=== $(date) KB UPDATE START ===" >> $LOG

# 1. edition-diff (изменённые редакции перекачиваются, doc_id → манифест)
cd "$CT" || fail "consultant-tools недоступен"
status running "сверка редакций (edition-diff)"
$PYC -m modules.edition_check --category all >> $LOG 2>&1 || echo "warn: edition_check" >> $LOG
CHANGED=$( [ -s "$MANIFEST" ] && tr '\n' ',' < "$MANIFEST" | sed 's/,$//' || echo "" )

# 2. добор НОВЫХ документов (skip-existing)
status running "добор новых документов"
$PYC modules/federal_laws.py --all --only fz --skip-amendments >> $LOG 2>&1 || echo "warn: fz" >> $LOG
$PYC -m modules.decrees >> $LOG 2>&1 || echo "warn: decrees" >> $LOG

# 3. ingest: новые
cd "$KS" || fail "КС недоступна"
git pull -q origin main >> $LOG 2>&1
status running "заливка новых в граф"
$PYK -m src.core.graph_rag.importers.consultant_importer \
     --kind kodeksy --kind fkz --kind fz --kind decrees --kind court --no-phase2 >> $LOG 2>&1 || fail "ингест новых"
# 3b. изменённые редакции — точечный REPLACE
if [ -n "$CHANGED" ]; then
  status running "обновление изменённых редакций"
  $PYK -m src.core.graph_rag.importers.consultant_importer \
       --kind kodeksy --kind fkz --kind fz --kind decrees --update --only-docids "$CHANGED" --no-phase2 >> $LOG 2>&1 || echo "warn: update changed" >> $LOG
fi

# 4. embed: новые (resume) + изменённые (refresh)
status running "эмбеддинг"
$PYK scripts/kb_embed.py --mode embed --collection all >> $LOG 2>&1 || fail "embed новых"
[ -n "$CHANGED" ] && $PYK scripts/kb_embed.py --mode embed --collection all --refresh --only-docids "$CHANGED" >> $LOG 2>&1

# 5. relink + статус
status running "пересборка связей"
$PYK scripts/kb_relink.py "$DB" >> $LOG 2>&1 || echo "warn: relink" >> $LOG
NCH=$( [ -s "$MANIFEST" ] && wc -l < "$MANIFEST" | tr -d ' ' || echo 0 )
DOCS=$($PYK -c "import sqlite3;print(sqlite3.connect('$DB',timeout=30).execute('select count(*) from graph_documents').fetchone()[0])" 2>/dev/null)
echo "=== $(date) KB UPDATE DONE (docs=$DOCS, changed=$NCH) ===" >> $LOG
status ok "обновление завершено" ",\"documents\":$DOCS,\"changed_editions\":$NCH"
