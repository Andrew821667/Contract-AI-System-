# -*- coding: utf-8 -*-
"""
Graph-RAG Parsers

Парсинг документов в графовое дерево:
- ContractGraphParser — договоры (DOCX, PDF, TXT, XML)
- NPAGraphParser — НПА (TXT, HTML, PDF, DOCX)
- GraphBuilder — сохранение дерева в БД + structural edges
"""

from .base_parser import BaseDocumentGraphParser, ParsedNode, ParseResult
from .contract_parser import ContractGraphParser
from .npa_parser import NPAGraphParser
from .graph_builder import GraphBuilder

__all__ = [
    "BaseDocumentGraphParser",
    "ParsedNode",
    "ParseResult",
    "ContractGraphParser",
    "NPAGraphParser",
    "GraphBuilder",
]
