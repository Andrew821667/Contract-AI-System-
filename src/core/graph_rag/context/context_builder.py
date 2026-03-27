# -*- coding: utf-8 -*-
"""
Context Builder

Сборка структурированного контекста из результатов Graph-RAG
для передачи в LLM prompt.

Принцип: контекст строится «от найденного к окружению»:
  1. Основной узел (найденный ответ)
  2. Путь в дереве (предки → заголовок раздела → документ)
  3. Связанные узлы (ссылки, определения)
  4. Сущности (суммы, даты, нормы)

Контекст ограничен бюджетом токенов — сначала самое релевантное.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import List, Optional, Dict

from ..models import GraphNode, GraphDocument
from ..retrieval.graph_expander import ExpandedContext

logger = logging.getLogger(__name__)


@dataclass
class ContextBlock:
    """Блок контекста для LLM."""
    role: str               # primary, ancestor, sibling, reference, entity
    label: str              # Человекочитаемая метка
    content: str            # Текст блока
    source_node_id: Optional[str] = None
    source_document: Optional[str] = None
    priority: int = 0       # Чем выше, тем важнее (primary=100, ancestor=80...)
    char_count: int = 0

    def __post_init__(self):
        self.char_count = len(self.content)


@dataclass
class AssembledContext:
    """Собранный контекст для LLM."""
    blocks: List[ContextBlock] = field(default_factory=list)
    total_chars: int = 0
    truncated: bool = False
    sources: List[Dict] = field(default_factory=list)  # Ссылки на источники

    def to_prompt_text(self) -> str:
        """Сформировать текст контекста для вставки в prompt."""
        sections = []
        for block in self.blocks:
            sections.append(f"### {block.label}\n{block.content}")
        return "\n\n".join(sections)

    def to_structured(self) -> Dict:
        """Структурированное представление для API."""
        return {
            "context_text": self.to_prompt_text(),
            "blocks": [
                {
                    "role": b.role,
                    "label": b.label,
                    "content": b.content,
                    "source_node_id": b.source_node_id,
                    "source_document": b.source_document,
                }
                for b in self.blocks
            ],
            "sources": self.sources,
            "total_chars": self.total_chars,
            "truncated": self.truncated,
        }


class ContextBuilder:
    """
    Строит LLM-контекст из ExpandedContext.

    Использование:
        builder = ContextBuilder(max_chars=8000)
        context = builder.build(expanded_contexts, query="...")
        prompt_text = context.to_prompt_text()
    """

    def __init__(self, max_chars: int = 8000):
        """
        Args:
            max_chars: Максимальный размер контекста в символах.
                       ~8000 символов ≈ ~2000 токенов для русского текста.
        """
        self.max_chars = max_chars

    def build(
        self,
        contexts: List[ExpandedContext],
        query: str = "",
    ) -> AssembledContext:
        """
        Собрать контекст из расширенных результатов поиска.

        Args:
            contexts: Список ExpandedContext от GraphExpander
            query: Исходный запрос пользователя

        Returns:
            AssembledContext с блоками контекста
        """
        all_blocks: List[ContextBlock] = []
        sources = []

        for ctx in contexts:
            blocks, source = self._context_to_blocks(ctx)
            all_blocks.extend(blocks)
            if source:
                sources.append(source)

        # Сортируем по приоритету (desc) и убираем дубли
        all_blocks = self._deduplicate_blocks(all_blocks)
        all_blocks.sort(key=lambda b: b.priority, reverse=True)

        # Обрезаем по бюджету
        result = AssembledContext(sources=sources)
        budget = self.max_chars

        for block in all_blocks:
            if budget <= 0:
                result.truncated = True
                break

            if block.char_count > budget:
                # Обрезаем последний блок
                block.content = block.content[:budget] + "..."
                block.char_count = budget
                result.truncated = True

            result.blocks.append(block)
            budget -= block.char_count
            result.total_chars += block.char_count

        return result

    def _context_to_blocks(
        self,
        ctx: ExpandedContext,
    ) -> tuple[List[ContextBlock], Optional[Dict]]:
        """Конвертировать один ExpandedContext в блоки."""
        blocks = []
        node = ctx.primary_node.node
        doc_title = self._get_document_title(node)

        # 1. Primary node (самый важный)
        path_label = self._build_path_label(ctx.ancestors, node)
        blocks.append(ContextBlock(
            role="primary",
            label=path_label,
            content=node.text,
            source_node_id=node.id,
            source_document=doc_title,
            priority=100,
        ))

        # 2. Ancestors context (заголовок раздела)
        for ancestor in ctx.ancestors:
            if ancestor.node_type in ('section', 'chapter', 'title', 'article'):
                ancestor_label = self._node_label(ancestor)
                # Только заголовок, не полный текст предка
                text = ancestor.title or ancestor.text
                if len(text) > 200:
                    text = text[:200] + "..."
                blocks.append(ContextBlock(
                    role="ancestor",
                    label=f"Раздел: {ancestor_label}",
                    content=text,
                    source_node_id=ancestor.id,
                    source_document=doc_title,
                    priority=80,
                ))

        # 3. Children (если у пункта есть подпункты — показать)
        if ctx.children:
            children_text = "\n".join(
                f"- {self._node_label(c)}: {c.text[:100]}..."
                if len(c.text) > 100 else f"- {self._node_label(c)}: {c.text}"
                for c in ctx.children[:5]
            )
            blocks.append(ContextBlock(
                role="children",
                label=f"Подпункты ({self._node_label(node)})",
                content=children_text,
                source_node_id=node.id,
                source_document=doc_title,
                priority=70,
            ))

        # 4. Referenced nodes (факт-ссылки)
        for ref_node in ctx.referenced_nodes[:3]:
            ref_label = self._node_label(ref_node)
            ref_doc = self._get_document_title(ref_node)
            blocks.append(ContextBlock(
                role="reference",
                label=f"Ссылка → {ref_label} [{ref_doc}]",
                content=ref_node.text[:300],
                source_node_id=ref_node.id,
                source_document=ref_doc,
                priority=60,
            ))

        # 5. Entities summary
        if ctx.entities_summary:
            blocks.append(ContextBlock(
                role="entity",
                label="Извлечённые данные",
                content="; ".join(ctx.entities_summary[:10]),
                source_node_id=node.id,
                priority=50,
            ))

        # 6. Siblings (для контекста)
        for sib in ctx.siblings[:2]:
            blocks.append(ContextBlock(
                role="sibling",
                label=f"Смежный: {self._node_label(sib)}",
                content=sib.text[:200],
                source_node_id=sib.id,
                source_document=doc_title,
                priority=30,
            ))

        # Source info
        source = {
            "document": doc_title,
            "node_id": node.id,
            "node_type": node.node_type,
            "number": node.number,
            "match_type": ctx.primary_node.match_type,
            "score": ctx.primary_node.score,
        }

        return blocks, source

    # ──────────────────────────────────────────
    # Helpers
    # ──────────────────────────────────────────

    @staticmethod
    def _node_label(node: GraphNode) -> str:
        """Человекочитаемая метка узла."""
        parts = []
        type_labels = {
            'section': 'Раздел', 'clause': 'Пункт', 'subclause': 'Подпункт',
            'article': 'Статья', 'part': 'Часть', 'chapter': 'Глава',
            'title': 'Раздел', 'preamble': 'Преамбула', 'appendix': 'Приложение',
            'table': 'Таблица', 'term': 'Термин', 'note': 'Примечание',
            'paragraph': 'Параграф', 'document': 'Документ',
        }
        label = type_labels.get(node.node_type, node.node_type)
        if node.number:
            parts.append(f"{label} {node.number}")
        elif node.title:
            parts.append(f"{label} «{node.title[:50]}»")
        else:
            parts.append(label)
        return " ".join(parts)

    @staticmethod
    def _build_path_label(ancestors: List[GraphNode], node: GraphNode) -> str:
        """Построить путь от корня до узла: Документ > Раздел 1 > Пункт 1.1"""
        parts = []
        for a in ancestors:
            if a.node_type == 'document':
                parts.append(a.title or "Документ")
            elif a.number:
                parts.append(a.number)
            elif a.title:
                parts.append(a.title[:30])

        # Текущий узел
        if node.number:
            parts.append(f"п. {node.number}")
        elif node.title:
            parts.append(node.title[:30])

        return " > ".join(parts) if parts else "Контекст"

    @staticmethod
    def _get_document_title(node: GraphNode) -> str:
        """Получить название документа узла."""
        if node.document and node.document.title:
            return node.document.title
        return "Документ"

    @staticmethod
    def _deduplicate_blocks(blocks: List[ContextBlock]) -> List[ContextBlock]:
        """Убрать блоки с одинаковым source_node_id и role."""
        seen = set()
        result = []
        for b in blocks:
            key = (b.source_node_id, b.role)
            if key not in seen:
                seen.add(key)
                result.append(b)
        return result
