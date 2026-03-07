#!/bin/sh
set -e

echo "==> Waiting for PostgreSQL..."
until pg_isready -h "${DB_HOST:-postgres}" -p "${DB_PORT:-5432}" -U "${DB_USER:-contract_user}" -q; do
    echo "PostgreSQL is not ready yet, retrying in 2s..."
    sleep 2
done
echo "==> PostgreSQL is ready."

# Create ALL tables via SQLAlchemy (authoritative schema from Python models)
echo "==> Creating database tables (SQLAlchemy)..."
python -c "
from src.models.database import Base, engine
from src.models.auth_models import *
from src.models.changes_models import *
Base.metadata.create_all(bind=engine)
print('All tables created successfully')
" || echo "WARNING: Table creation failed, continuing..."

echo "==> Running Alembic migrations..."
alembic upgrade head 2>/dev/null || echo "WARNING: Alembic migrations skipped (may not be configured for Docker yet)"

echo "==> Seeding initial users..."
python database/seed_users.py || echo "WARNING: User seeding failed (may already exist)"

echo "==> Starting application..."
exec "$@"
