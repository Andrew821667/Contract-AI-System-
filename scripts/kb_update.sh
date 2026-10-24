#!/bin/sh
# Регулярное обновление БЗ КС. Cron в ночном окне. Статус → JSON (для админки;
# Telegram с legalai заблокирован). Single-instance lock.
#   1) кодексы: перекачка и сравнение текста → изменённые → манифест changed_docids
#   2) добор новых документов ФЗ и ФКЗ (skip-existing, архивные редакции — тоже skip)
#   3) ingest: новые (skip) + изменённые (--update --only-docids)
#   4) embed: новые (resume) + изменённые (--refresh --only-docids)
#   4b) fts-build: пересборка лексического FTS гибрида из ChromaDB
#   5) relink → статус
#   6) рестарт бэкенда (KeepAlive) → новые/вычищенные доки в живой in-memory индекс
KS=/Users/legalai/projects/Contract-AI-System-
# Инструменты выгрузки из К+ — часть репозитория (tools/consultant, раньше
# отдельный OpenClaw_consultant-tools); своё окружение tools/consultant/.venv.
CT=$KS/tools/consultant
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
# Нефатальный сбой шага: строка в лог + в итоговый статус. Раньше «warn» жил
# только в середине лога, а статус говорил «ok» — так 24.10.2026 незаметно
# упала замена 23 кодексов в графе.
WARNS=""
warn() { echo "warn: $1" >> $LOG; WARNS="${WARNS:+$WARNS; }$1"; }

echo "=== $(date) KB UPDATE START ===" >> $LOG

# 1. Новые редакции кодексов. В К+ новая редакция кодекса — под тем же
#    номером документа: добор её не видит. Прежняя сверка по дате в облачном
#    интерфейсе К+ ослепла после смены вёрстки (с июля 2026 — «изменено 0»
#    каждую неделю, все 23 кодекса застряли в редакциях на 30.05.2026) и
#    отнимала ~4,5 ч прогона. Теперь кодекс перекачивается и текст
#    сравнивается с сохранённым; изменённые → манифест для точечного
#    обновления графа и векторов (шаги 3b и 4).
cd "$CT" || fail "инструменты К+ недоступны ($CT)"
status running "новые редакции кодексов"
$PYC modules/kodeksy.py --refresh >> $LOG 2>&1 || warn "kodeksy refresh — больше половины кодексов не скачалось"
# Изменённые копятся в PENDING, пока граф и векторы по ним не обновятся:
# манифест кодексов перезаписывается каждый прогон, а следующая сверка уже
# видит на диске новый текст («без изменений») — упавшее обновление иначе
# не повторится никогда.
PENDING=$DATA/refs/pending_docids.txt
cat "$MANIFEST" "$PENDING" 2>/dev/null | grep -E '^[0-9]+$' | sort -u > "$PENDING.tmp" && mv "$PENDING.tmp" "$PENDING"
CHANGED=$(tr '\n' ',' < "$PENDING" | sed 's/,$//')
NCH=$(grep -c . "$PENDING")

# 2. добор НОВЫХ документов (skip-existing)
status running "добор новых документов"
# ФЗ и ФКЗ (раньше --only fz: 27 ФКЗ не обновлялись с мая 2026).
$PYC modules/federal_laws.py --all --skip-amendments >> $LOG 2>&1 || warn "fz/fkz"
$PYC -m modules.decrees >> $LOG 2>&1 || warn "decrees"

# 2a. добор СУДЕБНОЙ ПРАКТИКИ.
#     Раньше этого шага не было вовсе: качались только ФЗ и подзаконка, а
#     `--kind court` ниже лишь заливает в граф уже лежащие файлы. В результате
#     корпус судебной практики стоял с 05.06.2026 (6927 файлов), и каждый
#     недельный прогон честно рапортовал «case_law: добавлено 0».
#     Органы и фильтр — те же, что в разовом court_night.sh, которым корпус
#     собирали изначально.
status running "добор судебной практики"
$PYC -m modules.court_practice --organ "Пленум Верховного Суда РФ" --slug plenum_vs \
     >> $LOG 2>&1 || warn "court plenum_vs"
$PYC -m modules.court_practice --organ "Верховный Суд РФ" --slug vs_all \
     >> $LOG 2>&1 || warn "court vs_all"
$PYC -m modules.court_practice --organ "Конституционный Суд РФ" --slug ks_post --title-filter "^Постановление" \
     >> $LOG 2>&1 || warn "court ks_post"

# 2b. дедуп редакций: у редакции закона в К+ свой doc_id, добор качает новую
#     редакцию как НОВЫЙ файл — без этого шага в сторах копятся устаревшие
#     редакции законов. Унесённые в архив добор больше не перекачивает.
cd "$KS" || fail "КС недоступна"
status running "дедуп редакций"
$PYK scripts/kb_dedup_editions.py >> $LOG 2>&1 || warn "dedup_editions"

# 3. ingest: новые
git pull -q origin main >> $LOG 2>&1
status running "заливка новых в граф"
$PYK -m src.core.graph_rag.importers.consultant_importer \
     --kind kodeksy --kind fkz --kind fz --kind decrees --kind court --no-phase2 >> $LOG 2>&1 || fail "ингест новых"
# 3b. изменённые редакции — точечный REPLACE. С Фазой 2: она строится только
#     от залитых в этом вызове документов (минуты на 23 кодекса) и возвращает
#     их исходящие ссылки; входящие из других документов переносит сам REPLACE.
CHANGED_OK=1
if [ -n "$CHANGED" ]; then
  status running "обновление изменённых редакций"
  $PYK -m src.core.graph_rag.importers.consultant_importer \
       --kind kodeksy --kind fkz --kind fz --kind decrees --update --only-docids "$CHANGED" >> $LOG 2>&1 \
    || { CHANGED_OK=0; warn "замена изменённых редакций в графе — повторится в следующий прогон"; }
fi

# 4. embed: новые (resume) + изменённые (refresh).
# ВАЖНО: два прохода. Дефолтный minilm кормит легаси-коллекции (laws/case_law),
# а ПРОД ищет по *_u2 (USER2) — без явного --model user2 новые доки невидимы
# семантике прода и FTS-гибриду (u2 наполнялся разовой миграцией kb_reembed_all,
# регулярного u2-доэмбеда не было — дыра всплыла 2026-07-11: 39 новых доков
# попали только в minilm).
status running "эмбеддинг"
$PYK scripts/kb_embed.py --mode embed --collection all >> $LOG 2>&1 || fail "embed новых"
$PYK scripts/kb_embed.py --mode embed --collection all --model user2 >> $LOG 2>&1 || fail "embed новых (user2)"
if [ -n "$CHANGED" ]; then
  $PYK scripts/kb_embed.py --mode embed --collection all --refresh --only-docids "$CHANGED" >> $LOG 2>&1 \
    || { CHANGED_OK=0; warn "векторы изменённых редакций (minilm)"; }
  $PYK scripts/kb_embed.py --mode embed --collection all --model user2 --refresh --only-docids "$CHANGED" >> $LOG 2>&1 \
    || { CHANGED_OK=0; warn "векторы изменённых редакций (user2)"; }
  [ "$CHANGED_OK" = 1 ] && rm -f "$PENDING"
fi

# 4b. пересборка лексического FTS-индекса гибрида (RAG_HYBRID) из ChromaDB —
#     kb_embed его НЕ трогает; без этого шага лексический канал слепнет к новым докам.
status running "пересборка FTS (гибрид)"
$PYK scripts/kb_fts_build.py >> $LOG 2>&1 || warn "fts_build"

# 5. relink + статус
status running "пересборка связей"
$PYK scripts/kb_relink.py "$DB" >> $LOG 2>&1 || warn "relink"

# 5b. пересчёт счётчиков документов.
#     relink достраивает cross-document рёбра ПОСЛЕ ингеста и update_stats()
#     не зовёт — счётчики документов отстают и врут в админке. К 10.08.2026
#     недосчёт накопился до 90 891 ребра (879 854 в графе против 788 963 в
#     сумме счётчиков), расхождение было у 6879 документов из 8212.
status running "пересчёт счётчиков графа"
$PYK scripts/graph_recount_stats.py >> $LOG 2>&1 || warn "graph_recount_stats"

# 6. рестарт бэкенда: KeepAlive-LaunchDaemon грузит ChromaDB-HNSW в память ПРИ
#    СТАРТЕ — новые (ингест) и вычищенные (дедуп 2b) доки не видны ЖИВОМУ индексу
#    до рестарта. Убиваем uvicorn (legalai владеет процессом) → launchd поднимает
#    заново (~30с). Non-fatal: обновление уже на диске, рестарт лишь делает его
#    живым. Без этого шага недельное обновление применялось только ручным рестартом.
status running "рестарт бэкенда"
BPID=$(pgrep -f "uvicorn src.main:app" | head -1)
if [ -n "$BPID" ]; then
  # Обычного TERM недостаточно: uvicorn регулярно виснет на async-shutdown —
  # процесс остаётся жив, launchd его не переподнимает (он ведь не умер), и
  # бэкенд стоит мёртвым, отвечая пустотой. Ровно так прод пролежал после
  # прогона 09.08.2026: скрипт написал «не поднялся за 60с» и завершился ОК.
  # Поэтому: TERM → ждём смерти → добиваем KILL → ждём health.
  kill "$BPID" 2>/dev/null
  for _ in $(seq 1 10); do
    kill -0 "$BPID" 2>/dev/null || break
    sleep 2
  done
  if kill -0 "$BPID" 2>/dev/null; then
    echo "$(date) backend не умер по TERM за 20с — добиваю KILL (pid $BPID)" >> $LOG
    kill -9 "$BPID" 2>/dev/null
  fi

  RESTARTED=0
  for _ in $(seq 1 45); do
    sleep 2
    if curl -s -m 3 http://127.0.0.1:8000/health 2>/dev/null | grep -q healthy; then
      echo "$(date) backend respawned (was pid $BPID)" >> $LOG; RESTARTED=1; break
    fi
  done
  # Не поднялся — это НЕ мелочь: система лежит. Пишем в статус, чтобы падение
  # было видно снаружи, а не только строкой «warn» в середине лога.
  # fail, а не status error: иначе итоговый «ok» ниже затирал эту ошибку.
  if [ "$RESTARTED" != 1 ]; then
    fail "backend не поднялся за 90с после рестарта — система недоступна"
  fi
else
  warn "uvicorn не найден — рестарт пропущен"
fi

DOCS=$($PYK -c "import sqlite3;print(sqlite3.connect('$DB',timeout=30).execute('select count(*) from graph_documents').fetchone()[0])" 2>/dev/null)
echo "=== $(date) KB UPDATE DONE (docs=$DOCS, changed=$NCH${WARNS:+, warn: $WARNS}) ===" >> $LOG
if [ -n "$WARNS" ]; then
  status warning "обновление завершено с предупреждениями: $WARNS" ",\"documents\":$DOCS,\"changed_editions\":$NCH"
else
  status ok "обновление завершено" ",\"documents\":$DOCS,\"changed_editions\":$NCH"
fi
