"""
SQLAlchemy <>45;8 4;O Contract AI System
>445@6:0 PostgreSQL 8 SQLite
"""
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import (
    Boolean, Column, String, Text, Integer, Float, Numeric,
    DateTime, ForeignKey, CheckConstraint, UniqueConstraint, JSON
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid

Base = declarative_base()


def generate_uuid():
    """5=5@0F8O UUID 4;O 8A?>;L7>20=8O :0: primary key"""
    return str(uuid.uuid4())


# class User(Base):  # MOVED TO auth_models.py
#     """>45;L ?>;L7>20B5;O"""
#     __tablename__ = "users"
#     __table_args__ = {"extend_existing": True}
# 
#     id = Column(String(36), primary_key=True, default=generate_uuid)
#     email = Column(String(255), unique=True, nullable=False, index=True)
#     name = Column(String(255), nullable=False)
#     role = Column(String(50), nullable=False)  # admin, senior_lawyer, lawyer, junior_lawyer
#     active = Column(Boolean, default=True)
#     created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
# 
#     # Relationships
#     templates = relationship("Template", back_populates="creator")
#     assigned_tasks = relationship("ReviewTask", foreign_keys="ReviewTask.assigned_to", back_populates="assignee")
#     export_logs = relationship("ExportLog", back_populates="user")
# 
#     __table_args__ = (
#         CheckConstraint(
#             role.in_(['admin', 'senior_lawyer', 'lawyer', 'junior_lawyer']),
#             name='check_user_role'
#         ),
#     )
# 
#     def __repr__(self):
#         return f"<User(id={self.id}, email={self.email}, role={self.role})>"
# 
# 
class Template(Base):
    """>45;L H01;>=0 4>3>2>@0"""
    __tablename__ = "templates"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    name = Column(String(255), nullable=False)
    contract_type = Column(String(50), nullable=False, index=True)
    xml_content = Column(Text, nullable=False)
    structure = Column(Text)  # JSON
    meta_info = Column(JSON, nullable=True)  # renamed from metadata to avoid SQLAlchemy reserved word
    version = Column(String(20), nullable=False)
    active = Column(Boolean, default=True, index=True)
    created_by = Column(String(36), ForeignKey('users.id', ondelete='SET NULL'))
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    creator = relationship("User", back_populates="templates")

    __table_args__ = (
        UniqueConstraint('contract_type', 'version', name='uq_template_type_version'),
    )

    def __repr__(self):
        return f"<Template(id={self.id}, name={self.name}, type={self.contract_type}, version={self.version})>"


class Contract(Base):
    """>45;L 4>3>2>@0"""
    __tablename__ = "contracts"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    file_name = Column(String(255), nullable=False)
    file_path = Column(Text, nullable=False)
    document_type = Column(String(50), nullable=False, index=True)
    contract_type = Column(String(50))
    upload_date = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    status = Column(String(50), default='pending', index=True)
    assigned_to = Column(String(36), ForeignKey('users.id', ondelete='SET NULL'), index=True)
    organization_id = Column(
        String(36),
        ForeignKey('organizations.id', ondelete='SET NULL'),
        nullable=True,
        index=True,
    )
    risk_level = Column(String(20), index=True)
    meta_info = Column(JSON, nullable=True)

    # Реквизиты договора (миграция 022)
    contract_number = Column(String(100), nullable=True, index=True)
    contract_date = Column(DateTime, nullable=True, index=True)
    effective_from = Column(DateTime, nullable=True)
    effective_to = Column(DateTime, nullable=True)
    total_amount = Column(Numeric(18, 2), nullable=True)
    currency = Column(String(3), nullable=True)

    # Извлечённый из документа текст для full-text поиска
    parsed_text = Column(Text, nullable=True)

    # Денормализованная копия ContractRelation.relation_type для быстрой
    # фильтрации в списке (источник истины — ContractRelation).
    primary_relation_type = Column(String(50), nullable=True, index=True)

    # Кэш сторон для отображения в списке без join
    parties_summary = Column(JSON, nullable=True)

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    assignee = relationship("User", foreign_keys=[assigned_to])
    analysis_results = relationship("AnalysisResult", back_populates="contract", cascade="all, delete-orphan")
    review_tasks = relationship("ReviewTask", back_populates="contract", cascade="all, delete-orphan")
    export_logs = relationship("ExportLog", back_populates="contract")

    parties = relationship(
        "ContractParty",
        back_populates="contract",
        cascade="all, delete-orphan",
        foreign_keys="ContractParty.contract_id",
    )
    derivative_relations = relationship(
        "ContractRelation",
        back_populates="parent_contract",
        cascade="all, delete-orphan",
        foreign_keys="ContractRelation.parent_contract_id",
    )
    parent_relations = relationship(
        "ContractRelation",
        back_populates="child_contract",
        cascade="all, delete-orphan",
        foreign_keys="ContractRelation.child_contract_id",
    )

    __table_args__ = (
        CheckConstraint(
            document_type.in_(['contract', 'disagreement', 'tracked_changes', 'derivative']),
            name='check_document_type'
        ),
        CheckConstraint(
            status.in_(['pending', 'uploaded', 'parsing', 'analyzing', 'reviewing', 'completed', 'error', 'deleted']),
            name='check_contract_status'
        ),
        CheckConstraint(
            risk_level.in_(['CRITICAL', 'HIGH', 'MEDIUM', 'LOW']),
            name='check_risk_level'
        ),
    )

    def __repr__(self):
        return f"<Contract(id={self.id}, file_name={self.file_name}, status={self.status})>"


class AnalysisResult(Base):
    """>45;L @57C;LB0B0 0=0;870 4>3>2>@0"""
    __tablename__ = "analysis_results"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    contract_id = Column(String(36), ForeignKey('contracts.id', ondelete='CASCADE'), nullable=False, index=True)
    entities = Column(JSON, nullable=True)
    compliance_issues = Column(JSON, nullable=True)
    legal_issues = Column(JSON, nullable=True)
    risks_by_category = Column(JSON, nullable=True)
    recommendations = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    version = Column(Integer, default=1)

    # Relationships
    contract = relationship("Contract", back_populates="analysis_results")

    def __repr__(self):
        return f"<AnalysisResult(id={self.id}, contract_id={self.contract_id}, version={self.version})>"


class ReviewTask(Base):
    """>45;L 7040G8 =0 ?@>25@:C G5;>25:><"""
    __tablename__ = "review_tasks"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    contract_id = Column(String(36), ForeignKey('contracts.id', ondelete='CASCADE'), nullable=False, index=True)
    assigned_to = Column(String(36), ForeignKey('users.id', ondelete='SET NULL'), index=True)
    assigned_by = Column(String(36), ForeignKey('users.id', ondelete='SET NULL'))
    status = Column(String(50), default='pending', index=True)
    priority = Column(String(20), default='medium', index=True)
    deadline = Column(DateTime, index=True)
    decision = Column(String(50))
    comments = Column(Text)

    # Timestamps
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    assigned_at = Column(DateTime)
    started_at = Column(DateTime)
    completed_at = Column(DateTime)

    # SLA tracking
    expected_duration = Column(Integer)  # expected minutes to complete
    actual_duration = Column(Integer)  # actual minutes taken
    sla_breached = Column(Boolean, default=False, index=True)

    # Audit trail
    history = Column(JSON, default=list)  # JSON array of status changes with timestamps

    # Relationships
    contract = relationship("Contract", back_populates="review_tasks")
    assignee = relationship("User", foreign_keys=[assigned_to], back_populates="assigned_tasks")
    assigner = relationship("User", foreign_keys=[assigned_by])

    __table_args__ = (
        CheckConstraint(
            status.in_(['pending', 'in_review', 'approved', 'rejected', 'completed']),
            name='check_task_status'
        ),
        CheckConstraint(
            priority.in_(['high', 'medium', 'low']),
            name='check_task_priority'
        ),
        CheckConstraint(
            decision.in_(['approve', 'reject', 'negotiate']),
            name='check_task_decision'
        ),
    )

    def __repr__(self):
        return f"<ReviewTask(id={self.id}, contract_id={self.contract_id}, status={self.status})>"


class LegalDocument(Base):
    """>45;L N@848G5A:>3> 4>:C<5=B0 4;O RAG"""
    __tablename__ = "legal_documents"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    doc_id = Column(String(64), unique=True, nullable=False, index=True)
    title = Column(Text, nullable=False)
    doc_type = Column(String(50), nullable=False, index=True)
    content = Column(Text, nullable=False)
    status = Column(String(20), default='active', index=True)
    is_vectorized = Column(Boolean, default=False, index=True)
    meta_info = Column(JSON, nullable=True)
    file_hash = Column(String(64), nullable=True, index=True)
    file_name = Column(String(255), nullable=True)
    file_path = Column(String(512), nullable=True)
    chunks_count = Column(Integer, default=0)
    source = Column(String(50), default='manual')
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        CheckConstraint(
            status.in_(['active', 'inactive', 'pending', 'processing', 'error']),
            name='check_legal_doc_status'
        ),
    )

    def __repr__(self):
        return f"<LegalDocument(id={self.id}, doc_id={self.doc_id}, type={self.doc_type})>"


class ExportLog(Base):
    """>45;L ;>30 M:A?>@B0"""
    __tablename__ = "export_logs"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    contract_id = Column(String(36), ForeignKey('contracts.id', ondelete='SET NULL'))
    exported_by = Column(String(36), ForeignKey('users.id', ondelete='SET NULL'))
    export_type = Column(String(50))  # "full_review", "quick_export"
    exported_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    meta_info = Column(JSON, nullable=True)

    # Relationships
    contract = relationship("Contract", back_populates="export_logs")
    user = relationship("User", back_populates="export_logs")

    def __repr__(self):
        return f"<ExportLog(id={self.id}, contract_id={self.contract_id}, type={self.export_type})>"


class ContractFeedback(Base):
    """Модель обратной связи для сбора данных обучения ML"""
    __tablename__ = "contract_feedback"

    id = Column(Integer, primary_key=True, autoincrement=True)
    contract_id = Column(String(36), ForeignKey('contracts.id', ondelete='CASCADE'), index=True)
    user_id = Column(String(36), ForeignKey('users.id', ondelete='SET NULL'), index=True)

    # User feedback
    rating = Column(Integer)  # 1-5 stars
    acceptance_status = Column(Boolean, default=None, index=True)  # true=accepted, false=rejected, null=pending

    # User corrections (what user changed)
    user_corrections = Column(JSON, default=None)

    # Generation parameters (for reproducing)
    generation_params = Column(JSON, default=None)

    # Template and context used
    template_id = Column(String(36), ForeignKey('templates.id', ondelete='SET NULL'))
    rag_context_used = Column(JSON, default=None)

    # Quality metrics
    validation_errors = Column(Integer, default=0)
    validation_warnings = Column(Integer, default=0)
    generation_duration = Column(Float)

    # Comments
    user_comment = Column(Text)

    # Timestamps
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    contract = relationship("Contract")
    user = relationship("User")
    template = relationship("Template")

    __table_args__ = (
        CheckConstraint(
            'rating >= 1 AND rating <= 5',
            name='check_rating_range'
        ),
    )

    def __repr__(self):
        return f"<ContractFeedback(id={self.id}, contract_id={self.contract_id}, rating={self.rating})>"


# -:A?>@B 2A5E <>45;59
__all__ = [
    "Base",
    "User",
    "Template",
    "Contract",
    "AnalysisResult",
    "ReviewTask",
    "LegalDocument",
    "ExportLog",
    "ContractFeedback",
    "ScheduledTaskLog",
    "LLMCache"
]


class ScheduledTaskLog(Base):
    """Лог выполнения фоновых задач планировщика"""
    __tablename__ = "scheduled_task_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    job_id = Column(String(100), nullable=False, index=True)
    job_name = Column(String(200), nullable=False)
    status = Column(String(20), nullable=False, default='running', index=True)
    started_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    finished_at = Column(DateTime, nullable=True)
    duration_sec = Column(Float, nullable=True)
    result = Column(Text, nullable=True)
    error = Column(Text, nullable=True)
    items_processed = Column(Integer, default=0)

    __table_args__ = (
        CheckConstraint(
            status.in_(['running', 'success', 'error', 'skipped']),
            name='check_task_log_status'
        ),
    )

    def __repr__(self):
        return f"<ScheduledTaskLog(id={self.id}, job={self.job_id}, status={self.status})>"


class LLMCache(Base):
    """Кэш LLM запросов для экономии токенов"""
    __tablename__ = "llm_cache"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    prompt_hash = Column(String(64), nullable=False, index=True, unique=True)  # SHA256 хэш промпта
    provider = Column(String(50), nullable=False)  # openai, claude, etc
    model = Column(String(100), nullable=False)  # gpt-4o-mini, gpt-4o, etc
    prompt = Column(Text, nullable=False)  # Оригинальный промпт
    system_prompt = Column(Text)  # System prompt если есть
    response = Column(Text, nullable=False)  # Ответ от LLM
    response_format = Column(String(20), nullable=False)  # text или json
    temperature = Column(Float)  # Температура генерации
    max_tokens = Column(Integer)  # Макс токенов
    input_tokens = Column(Integer)  # Использовано input токенов
    output_tokens = Column(Integer)  # Использовано output токенов
    cost_usd = Column(Float)  # Стоимость запроса в USD
    hit_count = Column(Integer, default=0)  # Сколько раз использован из кэша
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    last_accessed = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    def __repr__(self):
        return f"<LLMCache(id={self.id}, model={self.model}, hits={self.hit_count})>"


# ==================== DATABASE CONNECTION ====================
import os
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session

# Load environment variables
load_dotenv()

# Get database URL from environment — PostgreSQL only
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://contract_user:dev_password@localhost:5432/contract_ai"
)

# Create engine — PostgreSQL with connection pooling
# pool_size=20 + max_overflow=40 = 60 max connections
# Accounts for: API requests, WebSocket polling, background tasks, bootstrap session
if DATABASE_URL.startswith("sqlite"):
    # SQLite allowed only in tests (via conftest.py override)
    engine = create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False},
        echo=False,
    )
else:
    engine = create_engine(
        DATABASE_URL,
        echo=False,
        pool_size=20,
        max_overflow=30,
        pool_pre_ping=True,  # Detect stale connections
        pool_recycle=300,     # Recycle connections after 5 minutes
    )

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Thread-local scoped session for core services.
# Each thread gets its own Session instance automatically,
# preventing concurrent access to a shared session under FastAPI's threadpool.
ScopedSession = scoped_session(SessionLocal)


def get_db():
    """
    Dependency for FastAPI to get database session (sync).

    Usage:
    ```python
    @app.get("/users")
    def get_users(db: Session = Depends(get_db)):
        users = db.query(User).all()
        return users
    ```
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ==================== ASYNC DATABASE (PostgreSQL) ====================
# Non-blocking DB access via asyncpg. Falls back to sync in tests (SQLite).

async_engine = None
AsyncSessionLocal = None

if not DATABASE_URL.startswith("sqlite"):
    try:
        from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

        # Convert postgresql:// → postgresql+asyncpg://
        ASYNC_DATABASE_URL = DATABASE_URL.replace(
            "postgresql://", "postgresql+asyncpg://"
        ).replace(
            "postgresql+psycopg2://", "postgresql+asyncpg://"
        )

        async_engine = create_async_engine(
            ASYNC_DATABASE_URL,
            echo=False,
            pool_size=10,
            max_overflow=20,
            pool_pre_ping=True,
            pool_recycle=300,
        )

        AsyncSessionLocal = async_sessionmaker(
            async_engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )
    except ImportError:
        pass  # asyncpg not installed — async features disabled


async def get_async_db():
    """
    Dependency for FastAPI async endpoints (PostgreSQL only).

    Falls back to sync session wrapped in a thread if async engine is unavailable.

    Usage:
    ```python
    @app.get("/users")
    async def get_users(db: AsyncSession = Depends(get_async_db)):
        result = await db.execute(select(User))
        return result.scalars().all()
    ```
    """
    if AsyncSessionLocal is None:
        # Fallback: yield sync session (tests only)
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()
        return

    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


# Re-export User from auth_models for backwards compatibility
# (User was moved to auth_models.py but some code imports from here)
from .auth_models import User  # noqa: E402,F401
