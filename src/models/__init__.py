"""
Database models and connection management
"""
from loguru import logger
from .database import Base, engine, SessionLocal, get_db, Template, Contract, AnalysisResult, ReviewTask, LegalDocument, ExportLog, ContractFeedback, ScheduledTaskLog
from .auth_models import (
    User, UserSession, DemoToken, AuditLog,
    PasswordResetRequest, EmailVerification, LoginAttempt
)
from .analyzer_models import ContractRisk, ContractRecommendation, ContractAnnotation, ContractSuggestedChange, AnalysisFeedback
from .disagreement_models import Disagreement, DisagreementObjection, DisagreementExportLog, DisagreementFeedback
from .changes_models import ContractVersion, ContractChange, ChangeAnalysisResult, ChangeReviewFeedback
from .analytics_models import AnalyticsMetricLog, AggregatedMetric
from .ml_feedback_models import RiskPredictionFeedback, ModelTrainingBatch
from .digital_models import DigitalContract
from .clause_models import ExtractedClause


def init_db():
    """Initialize database (create all tables)"""
    Base.metadata.create_all(bind=engine)
    logger.info("Database initialized")


__all__ = [
    "engine",
    "SessionLocal",
    "init_db",
    "get_db",
    "Base",
    # Auth models
    "User",
    "UserSession",
    "DemoToken",
    "AuditLog",
    "PasswordResetRequest",
    "EmailVerification",
    "LoginAttempt",
    # Core models
    "Template",
    "Contract",
    "AnalysisResult",
    "ReviewTask",
    "LegalDocument",
    "ExportLog",
    "ContractFeedback",
    "ScheduledTaskLog",
    # Analyzer models
    "ContractRisk",
    "ContractRecommendation",
    "ContractAnnotation",
    "ContractSuggestedChange",
    "AnalysisFeedback",
    # Disagreement models
    "Disagreement",
    "DisagreementObjection",
    "DisagreementExportLog",
    "DisagreementFeedback",
    # Changes models
    "ContractVersion",
    "ContractChange",
    "ChangeAnalysisResult",
    "ChangeReviewFeedback",
    # Analytics models
    "AnalyticsMetricLog",
    "AggregatedMetric",
    # ML Feedback models
    "RiskPredictionFeedback",
    "ModelTrainingBatch",
    # Digital contract models
    "DigitalContract",
    # Clause library models
    "ExtractedClause"
]
