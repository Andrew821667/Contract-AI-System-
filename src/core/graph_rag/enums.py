# -*- coding: utf-8 -*-
"""
Graph-RAG Enums

Типы узлов, рёбер, слоёв и статусов для графовой модели документов.
"""
from enum import Enum


class LayerType(str, Enum):
    """Слой данных в графе."""
    CONTRACT = "contract"       # Слой 1 — Договоры
    NPA = "npa"                 # Слой 2 — НПА (нормативно-правовые акты)
    COURT = "court"             # Слой 3 — Судебная практика (после MVP)
    INTERNAL = "internal"       # Слой 4 — Внутренние документы (после MVP)


class NodeType(str, Enum):
    """Тип узла в графе документа."""
    # Общие
    DOCUMENT = "document"           # Корневой узел документа
    SECTION = "section"             # Раздел
    CLAUSE = "clause"               # Пункт
    SUBCLAUSE = "subclause"         # Подпункт
    PARAGRAPH = "paragraph"         # Абзац
    TABLE = "table"                 # Таблица
    TABLE_ROW = "table_row"         # Строка таблицы
    LIST_ITEM = "list_item"         # Элемент списка
    APPENDIX = "appendix"           # Приложение
    TERM = "term"                   # Определение/термин
    HEADER = "header"               # Заголовок
    PREAMBLE = "preamble"           # Преамбула
    SIGNATURE_BLOCK = "signature_block"  # Блок подписей

    # Специфичные для НПА
    ARTICLE = "article"             # Статья НПА
    PART = "part"                   # Часть статьи
    CHAPTER = "chapter"             # Глава
    TITLE = "title"                 # Раздел НПА (Раздел I, II...)
    NOTE = "note"                   # Примечание


class EdgeType(str, Enum):
    """Конкретный тип связи между узлами."""
    # Structural (создаются автоматически парсером)
    PARENT_CHILD = "parent_child"
    ADJACENT_TO = "adjacent_to"
    CONTAINS = "contains"
    BELONGS_TO_EDITION = "belongs_to_edition"

    # Fact (создаются парсером/правилами)
    REFERENCES = "references"           # Ссылка на другой узел/документ
    DEFINED_IN = "defined_in"           # Термин определён в узле
    AMENDS = "amends"                   # Изменяет (для НПА)
    SUPERSEDES = "supersedes"           # Заменяет
    TABLE_REF = "table_ref"             # Ссылка на таблицу
    APPENDIX_REF = "appendix_ref"       # Ссылка на приложение
    REGULATED_BY = "regulated_by"       # Регулируется нормой НПА

    # Analytical (только CandidateEdge в MVP)
    SIMILAR_TO_CLAUSE = "similar_to_clause"
    POTENTIAL_CONFLICT_WITH_NPA = "potential_conflict_with_npa"
    POSSIBLE_REQUIRES_APPROVAL = "possible_requires_approval"

    # Risk signals (только CandidateEdge в MVP)
    RISK_SIGNAL_FROM_RULE = "risk_signal_from_rule"


class EdgeClass(str, Enum):
    """Класс связи — определяет природу и надёжность."""
    STRUCTURAL = "structural"       # Объективная структурная связь
    FACT = "fact"                    # Прямо подтверждаемая текстом
    ANALYTICAL = "analytical"       # Связь-вывод (LLM/аналитика)
    RISK_SIGNAL = "risk_signal"     # Сигнал риска


class EdgeStatus(str, Enum):
    """Статус подтверждённости связи."""
    VERIFIED = "verified"                   # Подтверждена человеком или жёстким правилом
    MACHINE_EXTRACTED = "machine_extracted"  # Надёжно извлечена машиной
    HYPOTHESIS = "hypothesis"               # Предположение
    DEPRECATED = "deprecated"               # Устарела


class ExtractedBy(str, Enum):
    """Кем/чем создана связь или узел."""
    PARSER = "parser"       # Парсер документа
    RULE = "rule"           # Rule engine
    LLM = "llm"             # Языковая модель
    MANUAL = "manual"       # Ручной ввод юриста


class ChangeType(str, Enum):
    """Тип изменения версии узла."""
    NEW = "new"                     # Новый узел
    CORRECTION = "correction"       # Исправление ошибки
    NEW_EDITION = "new_edition"     # Новая редакция
    ARCHIVE = "archive"             # Архивирование


class ChangedBy(str, Enum):
    """Кто инициировал изменение."""
    USER = "user"
    AGENT = "agent"
    SYSTEM = "system"


class ParseStatus(str, Enum):
    """Статус парсинга документа."""
    FULLY_PARSED = "fully_parsed"
    PARTIAL_PARSE = "partial_parse"
    NEEDS_REVIEW = "needs_review"
    FAILED = "failed"


class ReviewResult(str, Enum):
    """Результат ревью candidate edge."""
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    MODIFIED = "modified"


class DocumentStatus(str, Enum):
    """Статус документа в графе."""
    ACTIVE = "active"
    ARCHIVED = "archived"
    SUPERSEDED = "superseded"


class AuditAction(str, Enum):
    """Тип действия в audit log."""
    NODE_CREATED = "node_created"
    NODE_UPDATED = "node_updated"
    NODE_ARCHIVED = "node_archived"
    VERSION_CREATED = "version_created"
    EDGE_CREATED = "edge_created"
    EDGE_UPDATED = "edge_updated"
    EDGE_STATUS_CHANGED = "edge_status_changed"
    CANDIDATE_CREATED = "candidate_created"
    CANDIDATE_REVIEWED = "candidate_reviewed"
    DOCUMENT_INGESTED = "document_ingested"
    DOCUMENT_ARCHIVED = "document_archived"
