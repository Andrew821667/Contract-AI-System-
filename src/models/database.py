"""
SQLAlchemy <>45;8 4;O Contract AI System
>445@6:0 PostgreSQL 8 SQLite
"""
from datetime import datetime
from typing import Optional
from sqlalchemy import (
    Boolean, Column, String, Text, Integer, Float,
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
#     created_at = Column(DateTime, default=datetime.utcnow)
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
    meta_info = Column(Text)  # JSON (renamed from metadata to avoid SQLAlchemy reserved word)
    version = Column(String(20), nullable=False)
    active = Column(Boolean, default=True, index=True)
    created_by = Column(String(36), ForeignKey('users.id'))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

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
    upload_date = Column(DateTime, default=datetime.utcnow, index=True)
    status = Column(String(50), default='pending', index=True)
    assigned_to = Column(String(36), ForeignKey('users.id'), index=True)
    risk_level = Column(String(20), index=True)
    meta_info = Column(Text)  # JSON
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    assignee = relationship("User", foreign_keys=[assigned_to])
    analysis_results = relationship("AnalysisResult", back_populates="contract", cascade="all, delete-orphan")
    review_tasks = relationship("ReviewTask", back_populates="contract", cascade="all, delete-orphan")
    export_logs = relationship("ExportLog", back_populates="contract")

    __table_args__ = (
        CheckConstraint(
            document_type.in_(['contract', 'disagreement', 'tracked_changes']),
            name='check_document_type'
        ),
        CheckConstraint(
            status.in_(['pending', 'analyzing', 'reviewing', 'completed', 'error']),
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
    entities = Column(Text)  # JSON
    compliance_issues = Column(Text)  # JSON
    legal_issues = Column(Text)  # JSON
    risks_by_category = Column(Text)  # JSON
    recommendations = Column(Text)  # JSON
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
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
    assigned_to = Column(String(36), ForeignKey('users.id'), index=True)
    assigned_by = Column(String(36), ForeignKey('users.id'))
    status = Column(String(50), default='pending', index=True)
    priority = Column(String(20), default='medium', index=True)
    deadline = Column(DateTime, index=True)
    decision = Column(String(50))
    comments = Column(Text)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    assigned_at = Column(DateTime)
    started_at = Column(DateTime)
    completed_at = Column(DateTime)

    # SLA tracking
    expected_duration = Column(Integer)  # expected minutes to complete
    actual_duration = Column(Integer)  # actual minutes taken
    sla_breached = Column(Boolean, default=False, index=True)

    # Audit trail
    history = Column(Text)  # JSON array of status changes with timestamps

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
    meta_info = Column(Text)  # JSON
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        CheckConstraint(
            status.in_(['active', 'inactive']),
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
    exported_by = Column(String(36), ForeignKey('users.id'))
    export_type = Column(String(50))  # "full_review", "quick_export"
    exported_at = Column(DateTime, default=datetime.utcnow, index=True)
    meta_info = Column(Text)  # JSON

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
    user_corrections = Column(JSON, default={})

    # Generation parameters (for reproducing)
    generation_params = Column(JSON, default={})

    # Template and context used
    template_id = Column(String(36), ForeignKey('templates.id', ondelete='SET NULL'))
    rag_context_used = Column(JSON, default={})

    # Quality metrics
    validation_errors = Column(Integer, default=0)
    validation_warnings = Column(Integer, default=0)
    generation_duration = Column(Float)

    # Comments
    user_comment = Column(Text)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

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
    "LLMCache"
]


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
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    last_accessed = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<LLMCache(id={self.id}, model={self.model}, hits={self.hit_count})>"


# ==================== DATABASE CONNECTION ====================
import os
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Load environment variables
load_dotenv()

# Get database URL from environment
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./contract_ai.db")

# Create engine
# For SQLite, we need to enable check_same_thread=False to allow FastAPI to use it
if DATABASE_URL.startswith("sqlite"):
    engine = create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False},
        echo=False  # Set to True for SQL query logging
    )
else:
    # For PostgreSQL or other databases
    engine = create_engine(DATABASE_URL, echo=False)

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    """
    Dependency for FastAPI to get database session

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
