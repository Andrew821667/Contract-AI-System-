#!/bin/sh
# Деплой Contract AI на Mac mini — запускать на хосте от пользователя legalai.
#
# Зачем скрипт: раньше выкатывали руками, и 14.09.2026 после перезагрузки
# хоста порт 3103 занял rollback-контейнер старой сборки, а актуальная
# поднялась без порта — публика три дня смотрела на фронт месячной давности.
# Здесь порядок зафиксирован: обновить код → миграции → backend → образ
# фронта → единственный контейнер на 3103 → проверка снаружи.
#
# Как устроен прод:
#   backend  — launchd ru.legalaipro.contractai.backend (.venv, uvicorn :8000)
#   frontend — docker-контейнер contract-ai-frontend-seo, 127.0.0.1:3103 → Caddy
#   docker   — доступен только через sudo -u andrej
#
# Использование:  sh scripts/deploy_prod_macmini.sh            # текущий HEAD после pull
#                 SKIP_PULL=1 sh scripts/deploy_prod_macmini.sh # без git pull
#                 (SKIP_PULL — переменная окружения, не аргумент)

set -eu

APP_DIR="${APP_DIR:-$HOME/projects/Contract-AI-System-}"
CONTAINER="${CONTAINER:-contract-ai-frontend-seo}"
PUBLISH="${PUBLISH:-127.0.0.1:3103:3000}"
DOMAIN="${DOMAIN:-contract.ai-verdict.ru}"
BACKEND_LABEL="${BACKEND_LABEL:-system/ru.legalaipro.contractai.backend}"
BACKEND_URL_FOR_IMAGE="${BACKEND_URL_FOR_IMAGE:-http://host.docker.internal:8000}"
PATH="/usr/local/bin:/opt/homebrew/bin:$PATH"; export PATH

say() { printf '\n== %s\n' "$1"; }
d() { sudo -n -u andrej -i /usr/local/bin/docker "$@"; }

cd "$APP_DIR"

if [ "${SKIP_PULL:-0}" != "1" ]; then
  say "код"
  git fetch -q origin
  git pull --ff-only origin main
fi
sha=$(git rev-parse --short HEAD)
say "HEAD $sha"

say "зависимости backend"
.venv/bin/python -m pip install -q -r requirements.txt

say "миграции"
.venv/bin/python -m alembic upgrade head

say "backend: перезапуск"
sudo -n launchctl kickstart -k "$BACKEND_LABEL"
i=0
until curl -sf -m 3 http://127.0.0.1:8000/health >/dev/null; do
  i=$((i+1)); [ "$i" -gt 30 ] && { echo "backend не поднялся за 90 с"; exit 1; }
  sleep 3
done
curl -s -m 3 http://127.0.0.1:8000/health; echo

say "frontend: образ contract-ai-frontend:$sha"
# Пути только абсолютные: docker запускается через sudo -i от andrej, и
# текущий каталог там — его домашний, а не $APP_DIR.
d build -q \
  --build-arg NEXT_PUBLIC_API_URL= \
  --build-arg NEXT_PUBLIC_WS_URL= \
  --build-arg BACKEND_URL="$BACKEND_URL_FOR_IMAGE" \
  -t "contract-ai-frontend:$sha" -f "$APP_DIR/frontend/Dockerfile" "$APP_DIR/frontend" >/dev/null

say "frontend: контейнер на $PUBLISH"
# Всё, что публикует порт, кроме нового контейнера, — останавливается: два
# контейнера с одним портом после перезагрузки хоста спорят, кто первый.
for name in $(d ps -a --filter "publish=3103" --format '{{.Names}}'); do
  [ "$name" = "$CONTAINER" ] && continue
  d rm -f "$name" >/dev/null && echo "  убран: $name"
done
if d inspect "$CONTAINER" >/dev/null 2>&1; then
  old=$(d inspect "$CONTAINER" --format '{{.Config.Image}}' | sed 's/.*://')
  d rm -f "$CONTAINER" >/dev/null && echo "  прежний контейнер ($old) убран; образ contract-ai-frontend:$old остаётся для отката"
fi
d run -d --name "$CONTAINER" --restart always -p "$PUBLISH" "contract-ai-frontend:$sha" >/dev/null
i=0
until [ "$(d inspect "$CONTAINER" --format '{{.State.Health.Status}}')" = "healthy" ]; do
  i=$((i+1)); [ "$i" -gt 30 ] && { echo "frontend не стал healthy за 90 с"; d logs --tail 20 "$CONTAINER"; exit 1; }
  sleep 3
done

say "проверка снаружи: https://$DOMAIN"
build_id=$(d exec "$CONTAINER" sh -c 'cat /app/.next/BUILD_ID' | tr -d '\r\n')
code=$(curl -s -o /dev/null -w '%{http_code}' -m 20 "https://$DOMAIN/_next/static/$build_id/_buildManifest.js" || echo 000)
[ "$code" = "200" ] && echo "  ✓ снаружи отдаётся сборка контейнера ($build_id)" || { echo "  ✗ сборка $build_id снаружи недоступна: $code"; exit 1; }
code=$(curl -s -o /dev/null -w '%{http_code}' -m 20 -X POST "https://$DOMAIN/api/v1/auth/login" -d 'username=deploy-check&password=deploy-check' || echo 000)
case "$code" in 401|422) echo "  ✓ API через домен: $code";; *) echo "  ✗ API через домен: $code"; exit 1;; esac

say "готово: $sha"
