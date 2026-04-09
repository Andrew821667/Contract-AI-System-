#!/bin/sh
set -e

# Use the project virtualenv explicitly even if PATH is reset by the runtime shell.
export PATH="/opt/venv/bin:$PATH"

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
try:
    from src.models.changes_models import *
except ImportError:
    pass
# Phase 12 core models
import src.core.identity_org.models
import src.core.policies.models
import src.core.tools.models
import src.core.agents.models
import src.core.ai_collaboration.models
import src.core.orchestrator.models
import src.core.workflow.models
import src.core.collaboration.models
import src.core.templates.models
import src.core.integrations.models
import src.core.enterprise.integrity
Base.metadata.create_all(bind=engine)
print('All tables created successfully')
" || echo "WARNING: Table creation failed, continuing..."

echo "==> Ensuring PostgreSQL extensions..."
python -c "
import os
from sqlalchemy import create_engine, text

engine = create_engine(os.environ['DATABASE_URL'])
with engine.begin() as conn:
    conn.execute(text('CREATE EXTENSION IF NOT EXISTS vector'))
print('pgvector extension ensured')
" || echo "WARNING: Failed to ensure PostgreSQL extensions"

echo "==> Running Alembic migrations..."
/opt/venv/bin/alembic upgrade head 2>&1 && echo "Alembic migrations applied successfully" || {
    echo "WARNING: Alembic upgrade failed, stamping head as fallback..."
    /opt/venv/bin/alembic stamp head >/dev/null 2>&1 || true
}

echo "==> Seeding initial users..."
python database/seed_users.py || echo "WARNING: User seeding failed (may already exist)"

echo "==> Starting application..."
exec "$@"
