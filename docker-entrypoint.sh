#!/bin/sh
set -e

echo "==> Waiting for PostgreSQL..."
until pg_isready -h "${DB_HOST:-postgres}" -p "${DB_PORT:-5432}" -U "${DB_USER:-contract_user}" -q; do
    echo "PostgreSQL is not ready yet, retrying in 2s..."
    sleep 2
done
echo "==> PostgreSQL is ready."

# Create base tables (users, contracts, etc.) via SQLAlchemy
# These are required before Alembic migrations that reference them via FK
echo "==> Creating base tables (SQLAlchemy)..."
python -c "
from src.models.database import Base, engine
from src.models.auth_models import *
Base.metadata.create_all(bind=engine)
print('Base tables created successfully')
" || echo "WARNING: Base table creation failed, continuing..."

echo "==> Running Alembic migrations..."
alembic upgrade head || echo "WARNING: Alembic migrations failed, continuing with init.sql schema"

echo "==> Starting application..."
exec "$@"
