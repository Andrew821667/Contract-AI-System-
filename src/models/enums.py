# -*- coding: utf-8 -*-
"""
Enums для Contract AI System

Централизованное определение всех енумов для:
- Типов контрактов
- Типов рисков
- Статусов
- Ролей пользователей
"""
from enum import Enum


class ContractType(str, Enum):
    """Типы договоров"""
    SUPPLY = "supply"  # Договор поставки
    SERVICE = "service"  # Договор оказания услуг
    LEASE = "lease"  # Договор аренды
    EMPLOYMENT = "employment"  # Трудовой договор
    PARTNERSHIP = "partnership"  # Договор партнерства
    CONFIDENTIALITY = "confidentiality"  # Соглашение о конфиденциальности (NDA)
    LICENSE = "license"  # Лицензионный договор
    LOAN = "loan"  # Кредитный договор
    PURCHASE = "purchase"  # Договор купли-продажи
    AGENCY = "agency"  # Агентский договор
    CONSTRUCTION = "construction"  # Строительный договор
    GENERAL = "general"  # Общий/неопределенный тип
    UNKNOWN = "unknown"  # Неизвестный тип


class RiskType(str, Enum):
    """Типы рисков в контракте"""
    FINANCIAL = "financial"  # Финансовые риски
    LEGAL = "legal"  # Юридические риски
    OPERATIONAL = "operational"  # Операционные риски
    REPUTATIONAL = "reputational"  # Репутационные риски
    COMPLIANCE = "compliance"  # Риски соответствия
    TEMPORAL = "temporal"  # Временные риски (сроки)
    QUALITY = "quality"  # Риски качества
    LIABILITY = "liability"  # Риски ответственности
    TERMINATION = "termination"  # Риски расторжения
    INTELLECTUAL_PROPERTY = "intellectual_property"  # Риски ИС


class RiskSeverity(str, Enum):
    """Уровни серьезности рисков"""
    CRITICAL = "critical"  # Критический
    HIGH = "high"  # Высокий
    MEDIUM = "medium"  # Средний
    LOW = "low"  # Низкий
    INFO = "info"  # Информационный


class ContractStatus(str, Enum):
    """Статусы обработки договора"""
    PENDING = "pending"  # Ожидает обработки
    ANALYZING = "analyzing"  # В процессе анализа
    REVIEWED = "reviewed"  # Проверен
    APPROVED = "approved"  # Утвержден
    REJECTED = "rejected"  # Отклонен
    REVISION_NEEDED = "revision_needed"  # Требуется доработка
    COMPLETED = "completed"  # Завершен
    ERROR = "error"  # Ошибка обработки
    ARCHIVED = "archived"  # Архивирован


class UserRole(str, Enum):
    """Роли пользователей"""
    ADMIN = "admin"  # Администратор - полный доступ к системе
    LAWYER = "lawyer"  # Юрист - стандартные права работы с договорами
    JUNIOR_LAWYER = "junior_lawyer"  # Пользователь - базовые права
    DEMO = "demo"  # Демо-пользователь - временный доступ только на просмотр

class ClauseType(str, Enum):
    """Типы пунктов договора"""
    FINANCIAL = "financial"  # Финансовые условия
    TEMPORAL = "temporal"  # Сроки и даты
    LIABILITY = "liability"  # Ответственность
    TERMINATION = "termination"  # Расторжение
    CONFIDENTIALITY = "confidentiality"  # Конфиденциальность
    INTELLECTUAL_PROPERTY = "intellectual_property"  # Интеллектуальная собственность
    DISPUTE_RESOLUTION = "dispute_resolution"  # Разрешение споров
    FORCE_MAJEURE = "force_majeure"  # Форс-мажор
    WARRANTIES = "warranties"  # Гарантии и заверения
    DEFINITIONS = "definitions"  # Определения
    GENERAL = "general"  # Общие положения
    OTHER = "other"  # Прочее


class DocumentFormat(str, Enum):
    """Форматы документов"""
    DOCX = "docx"
    DOC = "doc"
    PDF = "pdf"
    RTF = "rtf"
    ODT = "odt"
    XML = "xml"
    TXT = "txt"
    JSON = "json"


class ExportFormat(str, Enum):
    """Форматы экспорта"""
    DOCX = "docx"
    PDF = "pdf"
    XML = "xml"
    JSON = "json"
    TXT = "txt"
    EMAIL = "email"
    EDO = "edo"  # Электронный документооборот


class AnalysisType(str, Enum):
    """Типы анализа"""
    QUICK = "quick"  # Быстрый анализ
    DEEP = "deep"  # Глубокий анализ
    FULL = "full"  # Полный анализ
    RISK_ONLY = "risk_only"  # Только риски
    CLAUSE_BY_CLAUSE = "clause_by_clause"  # Постатейный


class AgentType(str, Enum):
    """Типы агентов"""
    ONBOARDING = "onboarding"
    GENERATOR = "generator"
    ANALYZER = "analyzer"
    DISAGREEMENT = "disagreement"
    CHANGES = "changes"
    EXPORT = "export"
    ORCHESTRATOR = "orchestrator"


class LLMProvider(str, Enum):
    """LLM провайдеры"""
    OPENAI = "openai"
    CLAUDE = "claude"
    PERPLEXITY = "perplexity"
    YANDEX = "yandex"
    DEEPSEEK = "deepseek"
    QWEN = "qwen"


class DisputeProbability(str, Enum):
    """Вероятность спора"""
    VERY_HIGH = "very_high"  # Очень высокая
    HIGH = "high"  # Высокая
    MEDIUM = "medium"  # Средняя
    LOW = "low"  # Низкая
    VERY_LOW = "very_low"  # Очень низкая


# Маппинги для обратной совместимости
CONTRACT_TYPE_NAMES = {
    ContractType.SUPPLY: "Договор поставки",
    ContractType.SERVICE: "Договор оказания услуг",
    ContractType.LEASE: "Договор аренды",
    ContractType.EMPLOYMENT: "Трудовой договор",
    ContractType.PARTNERSHIP: "Договор партнерства",
    ContractType.CONFIDENTIALITY: "Соглашение о конфиденциальности (NDA)",
    ContractType.LICENSE: "Лицензионный договор",
    ContractType.LOAN: "Кредитный договор",
    ContractType.PURCHASE: "Договор купли-продажи",
    ContractType.AGENCY: "Агентский договор",
    ContractType.CONSTRUCTION: "Строительный договор",
    ContractType.GENERAL: "Общий договор",
    ContractType.UNKNOWN: "Неопределенный тип",
}

RISK_TYPE_NAMES = {
    RiskType.FINANCIAL: "Финансовый риск",
    RiskType.LEGAL: "Юридический риск",
    RiskType.OPERATIONAL: "Операционный риск",
    RiskType.REPUTATIONAL: "Репутационный риск",
    RiskType.COMPLIANCE: "Риск соответствия",
    RiskType.TEMPORAL: "Временной риск",
    RiskType.QUALITY: "Риск качества",
    RiskType.LIABILITY: "Риск ответственности",
    RiskType.TERMINATION: "Риск расторжения",
    RiskType.INTELLECTUAL_PROPERTY: "Риск ИС",
}

RISK_SEVERITY_COLORS = {
    RiskSeverity.CRITICAL: "#dc3545",  # red
    RiskSeverity.HIGH: "#fd7e14",  # orange
    RiskSeverity.MEDIUM: "#ffc107",  # yellow
    RiskSeverity.LOW: "#28a745",  # green
    RiskSeverity.INFO: "#17a2b8",  # cyan
}


__all__ = [
    # Enums
    "ContractType",
    "RiskType",
    "RiskSeverity",
    "ContractStatus",
    "UserRole",
    "ClauseType",
    "DocumentFormat",
    "ExportFormat",
    "AnalysisType",
    "AgentType",
    "LLMProvider",
    "DisputeProbability",
    # Mappings
    "CONTRACT_TYPE_NAMES",
    "RISK_TYPE_NAMES",
    "RISK_SEVERITY_COLORS",
]
