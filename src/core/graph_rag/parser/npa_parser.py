# -*- coding: utf-8 -*-
"""
NPA Graph Parser

Парсинг нормативно-правовых актов (ГК РФ, ФЗ, подзаконные акты, ГОСТы)
в нормализованное дерево GraphNode.

Структура НПА:
  Раздел (Title) → Глава (Chapter) → Статья (Article) → Часть (Part) → Пункт (Clause)

Приоритеты определения структуры:
  1. HTML-разметка источника (consultant.ru, garant.ru)
  2. Явные заголовки и номера (Статья N, Глава N)
  3. Регулярные шаблоны
"""
from __future__ import annotations

import os
import re
from pathlib import Path
from typing import List, Optional, Dict, Any

from .base_parser import BaseDocumentGraphParser, ParsedNode, ParseResult
from ..enums import LayerType, NodeType, ParseStatus


# ──────────────────────────────────────────────
# Regex patterns для НПА
# ──────────────────────────────────────────────

# Раздел: "Раздел I.", "РАЗДЕЛ ПЕРВЫЙ"
RE_NPA_TITLE = re.compile(
    r'^(?:Раздел|РАЗДЕЛ)\s+([IVXLC]+|\d+)\.?\s*(.*)',
    re.IGNORECASE
)

# Подраздел: "Подраздел 1"
RE_NPA_SUBTITLE = re.compile(
    r'^(?:Подраздел|ПОДРАЗДЕЛ)\s+(\d+)\.?\s*(.*)',
    re.IGNORECASE
)

# Глава: "Глава 1.", "ГЛАВА 42"
RE_NPA_CHAPTER = re.compile(
    r'^(?:Глава|ГЛАВА)\s+(\d+(?:\.\d+)?)\.?\s*(.*)',
    re.IGNORECASE
)

# Параграф (§): "§ 1.", "Параграф 1"
RE_NPA_PARAGRAPH_SECTION = re.compile(
    r'^(?:§|Параграф)\s*(\d+)\.?\s*(.*)',
    re.IGNORECASE
)

# Статья: "Статья 330.", "Ст. 14.1", а также с префиксом кода кодекса из
# выгрузки К+: "УК РФ Статья 105.", "КоАП РФ Статья 5.27.1", "ТК ЕАЭС Статья 2".
# Номер статьи допускает несколько точек (5.27.1).
RE_NPA_ARTICLE = re.compile(
    r'^(?:[А-ЯЁ][А-Яа-яЁё]{1,4}\s+(?:РФ|ЕАЭС)\s+)?'
    r'(?:Статья|Ст\.?)\s+(\d+(?:\.\d+)*)\.?\s*(.*)',
    re.IGNORECASE
)

# Часть статьи / пункт: строка начинается с "1.", "2." (одна цифра).
# Точка может быть ЭКРАНИРОВАНА markdown-конвертером (html2text) как "1\." —
# так он подавляет авто-нумерацию списков. Поэтому слэш перед точкой опционален.
RE_NPA_PART = re.compile(r'^(\d+)\\?\.\s+(.*)')

# Пункт внутри части: "1)", "а)", "а."
RE_NPA_SUBPOINT = re.compile(r'^(\d+\)|[а-яё]\))\s*(.*)', re.IGNORECASE)

# Примечание
RE_NPA_NOTE = re.compile(r'^(?:Примечани[ея]|Прим\.)\s*(.*)', re.IGNORECASE)

# Дата редакции: "(в ред. Федерального закона от 01.07.2024 N 123-ФЗ)"
RE_EDITION = re.compile(r'\(в\s+ред\.\s+.*?(?:от\s+(\d{2}\.\d{2}\.\d{4})).*?\)')

# Тип НПА по заголовку
NPA_TYPE_PATTERNS = {
    'federal_law': re.compile(r'федеральн\w+\s+закон', re.IGNORECASE),
    'codex': re.compile(r'кодекс', re.IGNORECASE),
    'presidential_decree': re.compile(r'указ\s+президент', re.IGNORECASE),
    'government_decree': re.compile(r'постановлени\w+\s+правительств', re.IGNORECASE),
    'ministry_order': re.compile(r'приказ\s+(?:минист|мин)', re.IGNORECASE),
    'gost': re.compile(r'ГОСТ', re.IGNORECASE),
}


def _detect_npa_type(title: str) -> str:
    """Определить тип НПА по заголовку."""
    for npa_type, pattern in NPA_TYPE_PATTERNS.items():
        if pattern.search(title):
            return npa_type
    return "unknown"


class NPAGraphParser(BaseDocumentGraphParser):
    """
    Парсер НПА в нормализованное дерево.

    Поддерживает:
    - Plain text (скопированный из КонсультантПлюс/Гарант)
    - HTML (со структурными тегами)
    - Файлы (TXT, PDF, DOCX)
    """

    def parse_file(self, file_path: str) -> ParseResult:
        """Распарсить файл НПА."""
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")

        ext = Path(file_path).suffix.lower()
        file_name = Path(file_path).name

        if ext == '.html' or ext == '.htm':
            return self._parse_html(file_path)
        elif ext == '.txt':
            with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
                text = f.read()
            result = self.parse_text(text, title=file_name)
            result.source_format = 'txt'
            return result
        elif ext == '.md' or ext == '.markdown':
            return self._parse_md(file_path)
        elif ext == '.pdf':
            return self._parse_pdf(file_path)
        elif ext == '.docx':
            return self._parse_docx(file_path)
        else:
            raise ValueError(f"Unsupported format for NPA: {ext}")

    def _parse_md(self, file_path: str) -> ParseResult:
        """Распарсить .md-файл НПА из выгрузки consultant-tools.

        Формат: YAML-frontmatter (--- title/source_url/category/kind/number/
        date/edition_date ---) + тело markdown. Метаданные frontmatter
        авторитетнее извлечённых из текста и проставляются в ParseResult.
        """
        with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
            raw = f.read()

        fm, body = self._split_frontmatter(raw)
        title = fm.get('title') or Path(file_path).stem
        # Многострочный title (название НПА переносится) — схлопываем
        title = ' '.join(title.split())

        result = self.parse_text(body, title=title)
        result.source_format = 'md'

        # Метаданные из frontmatter — авторитетные
        if fm.get('document_type') or fm.get('category'):
            result.document_type = fm.get('document_type') or fm.get('category')
        if fm.get('date'):
            result.document_date = fm['date']
        if fm.get('edition_date'):
            result.edition_date = fm['edition_date']
        # Сохраняем КП-метаданные (source_url с cons_doc_LAW_<id>, номер) в metadata
        for k in ('source_url', 'number', 'kind'):
            if fm.get(k):
                result.metadata[k] = fm[k]
        return result

    @staticmethod
    def _split_frontmatter(raw: str) -> tuple:
        """Разделить YAML-frontmatter и тело. Возвращает (dict, body_str).

        Простой парсер key: value (без вложенности) — достаточно для нашего
        frontmatter. Значение может занимать несколько строк (напр. title
        с переносом до следующего ключа).
        """
        if not raw.startswith('---'):
            return {}, raw
        m = re.match(r'^---\n(.*?)\n---\n?(.*)$', raw, re.DOTALL)
        if not m:
            return {}, raw
        fm_block, body = m.group(1), m.group(2)
        fm: Dict[str, str] = {}
        cur_key = None
        for line in fm_block.split('\n'):
            km = re.match(r'^([a-zA-Z_][\w]*):\s?(.*)$', line)
            if km:
                cur_key = km.group(1)
                fm[cur_key] = km.group(2).strip()
            elif cur_key is not None and line.strip():
                # продолжение многострочного значения
                fm[cur_key] = (fm[cur_key] + ' ' + line.strip()).strip()
        return fm, body

    def parse_text(self, text: str, title: str = "Без названия") -> ParseResult:
        """Распарсить текст НПА в дерево."""
        root = ParsedNode(
            node_type=NodeType.DOCUMENT,
            text=title,
            title=title,
            level=0,
            position=0,
        )

        lines = text.split('\n')
        lines = [ln.strip() for ln in lines if ln.strip()]

        if not lines:
            return ParseResult(
                root=root, layer=LayerType.NPA, title=title,
                parse_status=ParseStatus.FAILED,
                parse_errors=["Empty document"],
            )

        # Определяем тип НПА
        npa_type = _detect_npa_type(title)
        if npa_type == "unknown" and lines:
            npa_type = _detect_npa_type(lines[0])

        # Извлекаем дату редакции из первых строк
        edition_date = None
        for line in lines[:10]:
            m = RE_EDITION.search(line)
            if m:
                edition_date = m.group(1)
                break

        # «Плоский» режим для не-статейных НПА (постановления/распоряжения
        # Правительства, указы Президента и т.п.): в тексте нет ни одной
        # «Статьи», структура держится на нумерованных ПУНКТАХ «1.», «2.».
        # В этом режиме пункты верхнего уровня становятся структурными нодами
        # (CLAUSE). Гейт по отсутствию статей — законы/кодексы не затрагиваются.
        flat_mode = not any(RE_NPA_ARTICLE.match(ln) for ln in lines)

        # Парсим структуру
        self._build_npa_tree(root, lines, flat_mode=flat_mode)

        parse_status = ParseStatus.FULLY_PARSED if root.children else ParseStatus.PARTIAL_PARSE
        errors = [] if root.children else ["No NPA structure detected"]

        return ParseResult(
            root=root,
            layer=LayerType.NPA,
            title=title,
            document_type=npa_type,
            edition_date=edition_date,
            source_format='txt',
            parse_status=parse_status,
            parse_errors=errors,
        )

    # ──────────────────────────────────────────
    # Построение дерева НПА
    # ──────────────────────────────────────────

    def _build_npa_tree(self, root: ParsedNode, lines: List[str],
                        flat_mode: bool = False):
        """
        Построение иерархического дерева НПА.

        Иерархия: Раздел → Глава → § → Статья → Часть → Пункт → Подпункт

        flat_mode: для не-статейных НПА (постановления/указы) — пункты верхнего
            уровня «N.» становятся структурными нодами CLAUSE под текущим
            контейнером (вместо PART под статьёй).
        """
        current_title: Optional[ParsedNode] = None       # Раздел
        current_chapter: Optional[ParsedNode] = None      # Глава
        current_para_sec: Optional[ParsedNode] = None     # §
        current_article: Optional[ParsedNode] = None      # Статья
        current_part: Optional[ParsedNode] = None         # Часть

        preamble_lines: List[str] = []
        in_preamble = True
        note_lines: List[str] = []
        in_note = False

        for line in lines:
            # Является ли строка структурным заголовком (Раздел/Глава/§/Статья).
            # Нужно, чтобы примечание (см. ниже) корректно ЗАВЕРШАЛОСЬ при
            # появлении нового структурного элемента, а не проглатывало весь
            # остаток документа.
            is_structural = bool(
                RE_NPA_TITLE.match(line)
                or RE_NPA_CHAPTER.match(line)
                or RE_NPA_PARAGRAPH_SECTION.match(line)
                or RE_NPA_ARTICLE.match(line)
            )

            # Примечание: начинается с "Примечание"/"Прим." и тянется до
            # следующего структурного заголовка. Структурную строку НЕ глотаем —
            # она пройдёт ниже и сбросит in_note через _flush_note.
            m_note = RE_NPA_NOTE.match(line)
            if (m_note or in_note) and not is_structural:
                in_note = True
                note_lines.append(line)
                continue

            # Раздел
            m = RE_NPA_TITLE.match(line)
            if m:
                in_preamble = False
                self._flush_preamble(root, preamble_lines)
                self._flush_note(current_article or current_chapter or root, note_lines)
                preamble_lines = []
                in_note = False
                note_lines = []

                current_title = ParsedNode(
                    node_type=NodeType.TITLE,
                    text=m.group(2) or line,
                    title=m.group(2) or line,
                    number=m.group(1),
                )
                root.add_child(current_title)
                current_chapter = None
                current_para_sec = None
                current_article = None
                current_part = None
                continue

            # Глава
            m = RE_NPA_CHAPTER.match(line)
            if m:
                in_preamble = False
                self._flush_preamble(root, preamble_lines)
                self._flush_note(current_article or current_chapter or root, note_lines)
                preamble_lines = []
                in_note = False
                note_lines = []

                current_chapter = ParsedNode(
                    node_type=NodeType.CHAPTER,
                    text=m.group(2) or line,
                    title=m.group(2) or line,
                    number=m.group(1),
                )
                parent = current_title or root
                parent.add_child(current_chapter)
                current_para_sec = None
                current_article = None
                current_part = None
                continue

            # Параграф (§)
            m = RE_NPA_PARAGRAPH_SECTION.match(line)
            if m:
                in_preamble = False
                self._flush_preamble(root, preamble_lines)
                preamble_lines = []

                current_para_sec = ParsedNode(
                    node_type=NodeType.SECTION,
                    text=m.group(2) or line,
                    title=m.group(2) or line,
                    number=f"§{m.group(1)}",
                )
                parent = current_chapter or current_title or root
                parent.add_child(current_para_sec)
                current_article = None
                current_part = None
                continue

            # Статья
            m = RE_NPA_ARTICLE.match(line)
            if m:
                in_preamble = False
                self._flush_preamble(root, preamble_lines)
                self._flush_note(current_article or current_chapter or root, note_lines)
                preamble_lines = []
                in_note = False
                note_lines = []

                current_article = ParsedNode(
                    node_type=NodeType.ARTICLE,
                    text=m.group(2) or line,
                    title=m.group(2) or line,
                    number=m.group(1),
                )
                parent = current_para_sec or current_chapter or current_title or root
                parent.add_child(current_article)
                current_part = None
                continue

            # Пункт «N.» — в плоском режиме (не-статейный НПА) это структурная
            # единица CLAUSE верхнего уровня; иначе — Часть статьи (PART).
            m = RE_NPA_PART.match(line)
            if m and flat_mode:
                in_preamble = False
                self._flush_preamble(root, preamble_lines)
                self._flush_note(current_article or current_chapter or root, note_lines)
                preamble_lines = []
                in_note = False
                note_lines = []

                clause = ParsedNode(
                    node_type=NodeType.CLAUSE,
                    text=m.group(2),
                    title=(m.group(2) or '')[:80],
                    number=m.group(1),
                )
                parent = current_para_sec or current_chapter or current_title or root
                parent.add_child(clause)
                # пункт становится текущим контейнером (для текста/подпунктов)
                current_article = clause
                current_part = None
                continue
            if m and current_article:
                current_part = ParsedNode(
                    node_type=NodeType.PART,
                    text=m.group(2),
                    number=m.group(1),
                )
                current_article.add_child(current_part)
                continue

            # Подпункт (1), а))
            m = RE_NPA_SUBPOINT.match(line)
            if m and (current_part or current_article):
                subpoint = ParsedNode(
                    node_type=NodeType.SUBCLAUSE,
                    text=m.group(2),
                    number=m.group(1).rstrip(')'),
                )
                parent = current_part or current_article
                parent.add_child(subpoint)
                continue

            # Преамбула (до первого структурного элемента)
            if in_preamble:
                preamble_lines.append(line)
                continue

            # Обычный текст → присоединяем к текущему элементу
            target = current_part or current_article or current_para_sec or current_chapter or current_title or root
            if target.children and target.children[-1].node_type == NodeType.PARAGRAPH:
                # Дописываем к последнему параграфу
                target.children[-1].text += '\n' + line
            else:
                target.add_child(ParsedNode(
                    node_type=NodeType.PARAGRAPH,
                    text=line,
                ))

        # Финализация
        self._flush_preamble(root, preamble_lines)
        self._flush_note(current_article or current_chapter or root, note_lines)

    def _flush_preamble(self, root: ParsedNode, lines: List[str]):
        """Сохранить преамбулу если есть."""
        if lines:
            root.add_child(ParsedNode(
                node_type=NodeType.PREAMBLE,
                text='\n'.join(lines),
                title="Преамбула",
            ))
            lines.clear()

    def _flush_note(self, parent: ParsedNode, lines: List[str]):
        """Сохранить примечание если есть."""
        if lines:
            parent.add_child(ParsedNode(
                node_type=NodeType.NOTE,
                text='\n'.join(lines),
                title="Примечание",
            ))
            lines.clear()

    # ──────────────────────────────────────────
    # HTML parsing (consultant.ru / garant.ru)
    # ──────────────────────────────────────────

    def _parse_html(self, file_path: str) -> ParseResult:
        """Парсинг HTML-источника НПА."""
        with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
            html_content = f.read()

        # Извлекаем текст из HTML, убираем теги
        text = re.sub(r'<[^>]+>', '\n', html_content)
        text = re.sub(r'\n{3,}', '\n\n', text)

        title = Path(file_path).stem
        # Попробуем извлечь title из HTML
        m = re.search(r'<title[^>]*>([^<]+)</title>', html_content, re.IGNORECASE)
        if m:
            title = m.group(1).strip()

        result = self.parse_text(text, title=title)
        result.source_format = 'html'
        return result

    def _parse_pdf(self, file_path: str) -> ParseResult:
        """Парсинг PDF НПА."""
        text_content = []
        try:
            import pdfplumber
            with pdfplumber.open(file_path) as pdf:
                for page in pdf.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text_content.append(page_text)
        except Exception:
            try:
                import pypdf
                reader = pypdf.PdfReader(file_path)
                for page in reader.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text_content.append(page_text)
            except Exception as e:
                return ParseResult(
                    root=ParsedNode(node_type=NodeType.DOCUMENT, text=Path(file_path).name),
                    layer=LayerType.NPA, title=Path(file_path).name,
                    parse_status=ParseStatus.FAILED,
                    parse_errors=[f"PDF extraction failed: {e}"],
                )

        full_text = '\n\n'.join(text_content)
        result = self.parse_text(full_text, title=Path(file_path).name)
        result.source_format = 'pdf'
        return result

    def _parse_docx(self, file_path: str) -> ParseResult:
        """Парсинг DOCX НПА."""
        try:
            from docx import Document
            doc = Document(file_path)
            text = '\n'.join(p.text for p in doc.paragraphs if p.text.strip())
            title = doc.core_properties.title or Path(file_path).name
            result = self.parse_text(text, title=title)
            result.source_format = 'docx'
            return result
        except Exception as e:
            return ParseResult(
                root=ParsedNode(node_type=NodeType.DOCUMENT, text=Path(file_path).name),
                layer=LayerType.NPA, title=Path(file_path).name,
                parse_status=ParseStatus.FAILED,
                parse_errors=[f"DOCX extraction failed: {e}"],
            )
