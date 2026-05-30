# -*- coding: utf-8 -*-
"""
Graph-RAG Importers

Загрузка внешних выгрузок НПА в graph_rag.
- ConsultantImporter — выгрузка OpenClaw_consultant-tools (~/consultant-data)
- validate_parse_result — обязательная автопроверка результата парсинга
"""
from .consultant_importer import ConsultantImporter, ImportReport
from .validator import validate_parse_result, ValidationReport, ValidationIssue

__all__ = [
    "ConsultantImporter",
    "ImportReport",
    "validate_parse_result",
    "ValidationReport",
    "ValidationIssue",
]
