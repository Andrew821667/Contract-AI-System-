# Docker Setup

## Подготовка

Создайте локальный файл окружения и заполните обязательные секреты:

```bash
cp .env.example .env
```

Минимально нужны `POSTGRES_PASSWORD`, `REDIS_PASSWORD`, `SECRET_KEY` и ключ хотя бы одного LLM-провайдера. Не коммитьте `.env`.

## Запуск

```bash
docker compose up -d --build
docker compose ps
```

Состав production-стека:

- `postgres` — PostgreSQL 16 с pgvector;
- `redis` — кэш и сессии;
- `backend` — FastAPI;
- `frontend` — Next.js, включая React-админку;
- `nginx` — единая точка входа.

После запуска приложение доступно на [http://localhost](http://localhost), админка — на [http://localhost/admin](http://localhost/admin), API — через `/api`, health check — через `/health`.

## Проверка

```bash
curl -fsS http://localhost/health
docker compose ps
docker compose logs --tail=100 backend frontend nginx
```

Все сервисы должны иметь статус `running` или `healthy`. База данных и Redis по умолчанию доступны только внутри compose-сети.

## Управление

```bash
# Логи
docker compose logs -f backend frontend nginx

# Перезапуск приложения
docker compose restart backend frontend nginx

# Остановка
docker compose down

# Остановка с удалением локальных томов данных
docker compose down -v
```

Команду с `-v` используйте только когда данные действительно можно удалить.

## Миграции

Backend запускает штатный entrypoint. Для ручной проверки или применения миграций:

```bash
docker compose exec backend alembic current
docker compose exec backend alembic upgrade head
```

## Production

В production не публикуйте PostgreSQL и Redis наружу. TLS и внешний домен должны завершаться на действующем reverse proxy, а `CONTRACT_AI_PUBLIC_URL` должен указывать на `https://contract.ai-verdict.ru`.
