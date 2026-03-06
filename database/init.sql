-- =====================================================
-- Contract AI System - Database Schema
-- =====================================================
-- PostgreSQL 14+
-- =====================================================

-- Extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- =====================================================
-- Table: users
-- =====================================================
CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY DEFAULT replace(gen_random_uuid()::text, '-', ''),
    email VARCHAR(255) UNIQUE NOT NULL,
    name VARCHAR(255) NOT NULL,
    role VARCHAR(50) NOT NULL CHECK (role IN ('admin', 'senior_lawyer', 'lawyer', 'junior_lawyer')),
    active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
CREATE INDEX IF NOT EXISTS idx_users_role ON users(role);

-- =====================================================
-- Table: templates
-- =====================================================
CREATE TABLE IF NOT EXISTS templates (
    id TEXT PRIMARY KEY DEFAULT replace(gen_random_uuid()::text, '-', ''),
    name VARCHAR(255) NOT NULL,
    contract_type VARCHAR(50) NOT NULL,
    xml_content TEXT NOT NULL,
    structure TEXT,
    metadata TEXT,
    version VARCHAR(20) NOT NULL,
    active BOOLEAN DEFAULT TRUE,
    created_by TEXT REFERENCES users(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    UNIQUE(contract_type, version)
);

CREATE INDEX IF NOT EXISTS idx_templates_type ON templates(contract_type);
CREATE INDEX IF NOT EXISTS idx_templates_active ON templates(active);
CREATE INDEX IF NOT EXISTS idx_templates_created_by ON templates(created_by);

-- =====================================================
-- Table: contracts
-- =====================================================
CREATE TABLE IF NOT EXISTS contracts (
    id TEXT PRIMARY KEY DEFAULT replace(gen_random_uuid()::text, '-', ''),
    file_name VARCHAR(255) NOT NULL,
    file_path TEXT NOT NULL,
    document_type VARCHAR(50) NOT NULL CHECK (document_type IN ('contract', 'disagreement', 'tracked_changes')),
    contract_type VARCHAR(50),
    upload_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    status VARCHAR(50) DEFAULT 'pending' CHECK (status IN ('pending', 'analyzing', 'reviewing', 'completed', 'error')),
    assigned_to TEXT REFERENCES users(id),
    risk_level VARCHAR(20) CHECK (risk_level IN ('CRITICAL', 'HIGH', 'MEDIUM', 'LOW')),
    metadata TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_contracts_status ON contracts(status);
CREATE INDEX IF NOT EXISTS idx_contracts_risk_level ON contracts(risk_level);
CREATE INDEX IF NOT EXISTS idx_contracts_assigned_to ON contracts(assigned_to);
CREATE INDEX IF NOT EXISTS idx_contracts_document_type ON contracts(document_type);
CREATE INDEX IF NOT EXISTS idx_contracts_upload_date ON contracts(upload_date);

-- =====================================================
-- Table: analysis_results
-- =====================================================
CREATE TABLE IF NOT EXISTS analysis_results (
    id TEXT PRIMARY KEY DEFAULT replace(gen_random_uuid()::text, '-', ''),
    contract_id TEXT NOT NULL REFERENCES contracts(id) ON DELETE CASCADE,
    entities TEXT,
    compliance_issues TEXT,
    legal_issues TEXT,
    risks_by_category TEXT,
    recommendations TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    version INTEGER DEFAULT 1
);

CREATE INDEX IF NOT EXISTS idx_analysis_contract_id ON analysis_results(contract_id);
CREATE INDEX IF NOT EXISTS idx_analysis_created_at ON analysis_results(created_at);

-- =====================================================
-- Table: review_tasks
-- =====================================================
CREATE TABLE IF NOT EXISTS review_tasks (
    id TEXT PRIMARY KEY DEFAULT replace(gen_random_uuid()::text, '-', ''),
    contract_id TEXT NOT NULL REFERENCES contracts(id) ON DELETE CASCADE,
    assigned_to TEXT REFERENCES users(id),
    status VARCHAR(50) DEFAULT 'pending' CHECK (status IN ('pending', 'in_progress', 'completed')),
    priority VARCHAR(20) DEFAULT 'normal' CHECK (priority IN ('critical', 'high', 'normal', 'low')),
    deadline TIMESTAMP,
    decision VARCHAR(50) CHECK (decision IN ('approve', 'reject', 'negotiate')),
    comments TEXT,
    completed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_review_tasks_assigned ON review_tasks(assigned_to);
CREATE INDEX IF NOT EXISTS idx_review_tasks_status ON review_tasks(status);
CREATE INDEX IF NOT EXISTS idx_review_tasks_deadline ON review_tasks(deadline);
CREATE INDEX IF NOT EXISTS idx_review_tasks_priority ON review_tasks(priority);

-- =====================================================
-- Table: legal_documents (RAG knowledge base)
-- =====================================================
CREATE TABLE IF NOT EXISTS legal_documents (
    id TEXT PRIMARY KEY DEFAULT replace(gen_random_uuid()::text, '-', ''),
    doc_id VARCHAR(64) UNIQUE NOT NULL,
    title TEXT NOT NULL,
    doc_type VARCHAR(50) NOT NULL,
    content TEXT NOT NULL,
    status VARCHAR(20) DEFAULT 'active' CHECK (status IN ('active', 'inactive')),
    is_vectorized BOOLEAN DEFAULT FALSE,
    metadata TEXT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_legal_docs_type ON legal_documents(doc_type);
CREATE INDEX IF NOT EXISTS idx_legal_docs_status ON legal_documents(status);
CREATE INDEX IF NOT EXISTS idx_legal_docs_vectorized ON legal_documents(is_vectorized);
CREATE INDEX IF NOT EXISTS idx_legal_docs_doc_id ON legal_documents(doc_id);
CREATE INDEX IF NOT EXISTS idx_legal_docs_content_fts ON legal_documents USING GIN(to_tsvector('russian', content));

-- =====================================================
-- Table: export_logs
-- =====================================================
CREATE TABLE IF NOT EXISTS export_logs (
    id TEXT PRIMARY KEY DEFAULT replace(gen_random_uuid()::text, '-', ''),
    contract_id TEXT REFERENCES contracts(id) ON DELETE SET NULL,
    exported_by TEXT REFERENCES users(id),
    export_type VARCHAR(50),
    exported_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    metadata TEXT
);

CREATE INDEX IF NOT EXISTS idx_export_logs_contract ON export_logs(contract_id);
CREATE INDEX IF NOT EXISTS idx_export_logs_user ON export_logs(exported_by);
CREATE INDEX IF NOT EXISTS idx_export_logs_date ON export_logs(exported_at);

-- =====================================================
-- Triggers for automatic updated_at
-- =====================================================
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS update_contracts_timestamp ON contracts;
CREATE TRIGGER update_contracts_timestamp
    BEFORE UPDATE ON contracts
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_templates_timestamp ON templates;
CREATE TRIGGER update_templates_timestamp
    BEFORE UPDATE ON templates
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_legal_docs_timestamp ON legal_documents;
CREATE TRIGGER update_legal_docs_timestamp
    BEFORE UPDATE ON legal_documents
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- =====================================================
-- Seed data
-- =====================================================
INSERT INTO users (id, email, name, role) VALUES
('test-admin-001', 'admin@example.com', 'Admin User', 'admin'),
('test-lawyer-001', 'lawyer@example.com', 'Senior Lawyer', 'senior_lawyer')
ON CONFLICT (id) DO NOTHING;
