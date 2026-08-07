#!/bin/sh
# Проверка деплоя ПО ПУБЛИЧНОМУ адресу.
#
# Зачем: фронтенд отдаётся контейнером `contract-ai-frontend-seo` из собранного
# образа, а рядом живёт похожий сервис на :3000 под другим доменом. Легко
# пересобрать не тот и отрапортовать «готово» — так и было 04.08.2026: правки
# трижды объявлялись выкаченными, пока пользователь смотрел на сборку
# двухнедельной давности. Локальные проверки этого не ловят по определению,
# поэтому здесь всё запрашивается снаружи.
#
# Что проверяем:
#   1. сайт открывается;
#   2. снаружи отдаётся ИМЕННО та сборка, что лежит в запущенном контейнере
#      (сверяем BUILD_ID) — ловит «пересобрал не тот экземпляр»;
#   3. /api через публичный домен отвечает 401, а не 500 — ловит сборку с
#      неверным BACKEND_URL (дефолт в Dockerfile указывает на несуществующий
#      хост, и весь API отдаёт 500; так прод лежал несколько минут).
#
# Запуск:  sh scripts/verify_deploy.sh [домен] [имя-контейнера]
# Выход:   0 — всё сходится; 1 — деплой не доехал.

set -u

DOMAIN="${1:-contract.ai-verdict.ru}"
CONTAINER="${2:-contract-ai-frontend-seo}"
PATH="/usr/local/bin:/opt/homebrew/bin:$PATH"
export PATH

fail=0
say() { printf '%s\n' "$1"; }
bad() { printf '  ✗ %s\n' "$1"; fail=1; }
ok()  { printf '  ✓ %s\n' "$1"; }

say "Проверка деплоя: https://$DOMAIN"

# 1. сайт жив
code=$(curl -s -o /dev/null -w '%{http_code}' --max-time 20 "https://$DOMAIN/" || echo 000)
[ "$code" = "200" ] && ok "сайт отвечает 200" || bad "сайт отвечает $code (ожидали 200)"

# 2. снаружи отдаётся сборка из запущенного контейнера
build_id=$(docker exec "$CONTAINER" sh -c 'cat /app/.next/BUILD_ID' 2>/dev/null | tr -d '\r\n')
if [ -z "$build_id" ]; then
    bad "не удалось прочитать BUILD_ID из контейнера $CONTAINER"
else
    code=$(curl -s -o /dev/null -w '%{http_code}' --max-time 20 \
           "https://$DOMAIN/_next/static/$build_id/_buildManifest.js" || echo 000)
    if [ "$code" = "200" ]; then
        ok "снаружи отдаётся сборка контейнера ($build_id)"
    else
        bad "сборка контейнера ($build_id) снаружи недоступна: $code — публичный адрес обслуживает ДРУГОЙ экземпляр"
    fi
fi

# 3. API через публичный домен проксируется на бэкенд
code=$(curl -s -o /dev/null -w '%{http_code}' --max-time 20 \
       -X POST "https://$DOMAIN/api/v1/auth/login" -d 'username=deploy-check&password=deploy-check' || echo 000)
case "$code" in
    401|422) ok "API через домен отвечает $code (бэкенд доступен)" ;;
    500|502|503|504) bad "API через домен отвечает $code — прокси на бэкенд сломан (проверьте BACKEND_URL в сборке)" ;;
    *) bad "API через домен отвечает $code (ожидали 401)" ;;
esac

if [ "$fail" -eq 0 ]; then
    say "ИТОГ: деплой доехал"
else
    say "ИТОГ: деплой НЕ доехал — смотрите отметки ✗ выше"
fi
exit "$fail"
