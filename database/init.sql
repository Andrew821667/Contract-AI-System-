-- Contract AI System — PostgreSQL initialization
-- Tables are created by SQLAlchemy via docker-entrypoint.sh
-- This file only sets up extensions and permissions

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "vector";  -- pgvector for RAG semantic search

-- Grant permissions
GRANT ALL PRIVILEGES ON DATABASE contract_ai TO contract_user;
