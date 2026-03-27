# -*- coding: utf-8 -*-
"""
Graph-RAG Base Parser

Абстрактный интерфейс для парсеров документов в графовое дерево.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any

from ..enums import LayerType, NodeType, ParseStatus


@dataclass
class ParsedNode:
    """
    Промежуточное представление узла до сохранения в БД.

    Парсер возвращает дерево ParsedNode, которое затем
    сохраняется в GraphNode через repository.
    """
    node_type: NodeType
    text: str
    title: Optional[str] = None
    number: Optional[str] = None            # "1.1", "ст. 330"
    level: int = 0
    position: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)
    children: List[ParsedNode] = field(default_factory=list)

    def add_child(self, child: ParsedNode) -> ParsedNode:
        """Добавить дочерний узел, автоматически выставив position."""
        child.level = self.level + 1
        child.position = len(self.children)
        self.children.append(child)
        return child

    def total_nodes(self) -> int:
        """Общее количество узлов в поддереве."""
        return 1 + sum(c.total_nodes() for c in self.children)

    def flatten(self) -> List[ParsedNode]:
        """Преобразовать дерево в плоский список (DFS pre-order)."""
        result = [self]
        for child in self.children:
            result.extend(child.flatten())
        return result


@dataclass
class ParseResult:
    """Результат парсинга документа."""
    root: ParsedNode                         # Корень дерева
    layer: LayerType                         # contract | npa
    title: str                               # Название документа
    document_type: Optional[str] = None      # supply, service, federal_law...
    document_date: Optional[str] = None      # Дата документа
    edition_date: Optional[str] = None       # Дата редакции (для НПА)
    source_format: Optional[str] = None      # docx, pdf, html, txt
    parse_status: ParseStatus = ParseStatus.FULLY_PARSED
    parse_errors: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def nodes_count(self) -> int:
        return self.root.total_nodes()


class BaseDocumentGraphParser(ABC):
    """
    Абстрактный парсер документов в графовое дерево.

    Каждая реализация (ContractGraphParser, NPAGraphParser) знает
    специфику своего типа документов: как определять нумерацию,
    какие node_type назначать, как строить иерархию.
    """

    @abstractmethod
    def parse_file(self, file_path: str) -> ParseResult:
        """
        Распарсить файл в дерево узлов.

        Args:
            file_path: Путь к файлу (DOCX, PDF, HTML, TXT)

        Returns:
            ParseResult с корнем дерева и метаданными
        """
        ...

    @abstractmethod
    def parse_text(self, text: str, title: str = "Без названия") -> ParseResult:
        """
        Распарсить текст в дерево узлов.

        Args:
            text: Текст документа
            title: Название документа

        Returns:
            ParseResult с корнем дерева и метаданными
        """
        ...

    def parse_xml(self, xml_content: str, title: str = "Без названия") -> ParseResult:
        """
        Распарсить XML от существующего DocumentParser.

        Позволяет переиспользовать текущий pipeline:
        DocumentParser.parse() → xml → ContractGraphParser.parse_xml() → дерево

        По умолчанию: не реализован (override в подклассах).
        """
        raise NotImplementedError(f"{self.__class__.__name__} does not support XML parsing")
