#!/bin/sh
set -e

echo "==> Waiting for PostgreSQL..."
until pg_isready -h "${DB_HOST:-postgres}" -p "${DB_PORT:-5432}" -U "${DB_USER:-contract_user}" -q; do
    echo "PostgreSQL is not ready yet, retrying in 2s..."
    sleep 2
done
echo "==> PostgreSQL is ready."

echo "==> Running Alembic migrations..."
alembic upgrade head || echo "WARNING: Alembic migrations failed, continuing with init.sql schema"

echo "==> Starting application..."
exec "$@"
