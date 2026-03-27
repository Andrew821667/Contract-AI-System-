# -*- coding: utf-8 -*-
"""
Reference Extractor

Regex + rule-based извлечение ссылок из текста узлов:
- Ссылки на НПА: ст. 330 ГК РФ, п. 2 ст. 15 ФЗ-44
- Ссылки на пункты договора: п. 7.3, п.п. 2.1.1
- Ссылки на приложения: Приложение №1
- Ссылки на таблицы: Таблица 1
- Ссылки на ГОСТы: ГОСТ 9353-2016
- Ссылки на определения: «термин» определён в п. ...

Создаёт fact edges (references, appendix_ref, table_ref, defined_in)
между узлами одного документа или между документами.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Tuple


# ──────────────────────────────────────────────
# Data classes для извлечённых ссылок
# ──────────────────────────────────────────────

@dataclass
class ExtractedReference:
    """Извлечённая ссылка из текста."""
    ref_type: str           # norm_ref, clause_ref, appendix_ref, table_ref, gost_ref, defined_in
    raw_text: str           # Оригинальный текст ссылки
    start: int              # Позиция начала в тексте
    end: int                # Позиция конца в тексте

    # Для norm_ref (ссылки на НПА)
    norm_code: Optional[str] = None     # "ГК РФ", "ФЗ-44", "ТК РФ"
    article: Optional[str] = None       # "330", "14.1"
    part: Optional[str] = None          # Часть статьи
    point: Optional[str] = None         # Пункт

    # Для clause_ref (ссылки на пункты договора)
    clause_number: Optional[str] = None  # "7.3", "2.1.1"

    # Для appendix/table/gost
    ref_number: Optional[str] = None     # "1", "2"
    gost_code: Optional[str] = None      # "9353-2016"

    # Confidence
    confidence: float = 1.0


# ──────────────────────────────────────────────
# Regex patterns
# ──────────────────────────────────────────────

# Кодексы и их сокращения
NPA_CODES = {
    'ГК РФ': 'ГК РФ',
    'Гражданского кодекса': 'ГК РФ',
    'Гражданским кодексом': 'ГК РФ',
    'ТК РФ': 'ТК РФ',
    'Трудового кодекса': 'ТК РФ',
    'НК РФ': 'НК РФ',
    'Налогового кодекса': 'НК РФ',
    'ЗК РФ': 'ЗК РФ',
    'Земельного кодекса': 'ЗК РФ',
    'КоАП': 'КоАП РФ',
    'УК РФ': 'УК РФ',
    'АПК РФ': 'АПК РФ',
    'ГПК РФ': 'ГПК РФ',
    'БК РФ': 'БК РФ',
    'ЖК РФ': 'ЖК РФ',
    'СК РФ': 'СК РФ',
}

# Паттерн: альтернативы кодексов для regex
_npa_alts = '|'.join(re.escape(k) for k in sorted(NPA_CODES.keys(), key=len, reverse=True))

# 1. Ссылка на статью НПА: "ст. 330 ГК РФ", "статьи 15 Гражданского кодекса"
RE_NORM_ARTICLE = re.compile(
    rf'(?:ст(?:атьи|атье|атья|атей|атьями|\.)\s*)'
    rf'(\d+(?:\.\d+)?)'                            # номер статьи
    rf'(?:\s+(?:ч(?:асти|асть|\.)\s*(\d+)))?'      # часть (опционально)
    rf'(?:\s+(?:п(?:ункта|ункт|\.)\s*(\d+)))?'     # пункт (опционально)
    rf'\s+({_npa_alts})',
    re.IGNORECASE
)

# 2. Ссылка на статью с предлогом: "в соответствии со ст. 330 ГК РФ"
RE_NORM_IN_ACCORDANCE = re.compile(
    rf'в\s+соответствии\s+(?:со?\s+)?'
    rf'ст(?:атьей|\.)\s*(\d+(?:\.\d+)?)'
    rf'\s+({_npa_alts})',
    re.IGNORECASE
)

# 3. Ссылка на ФЗ: "ФЗ от 05.04.2013 N 44-ФЗ", "Федеральный закон N 44-ФЗ"
RE_FEDERAL_LAW = re.compile(
    r'(?:Федеральн\w+\s+закон\w*|ФЗ)\s+'
    r'(?:от\s+\d{2}\.\d{2}\.\d{4}\s+)?'
    r'[NnНн№]\s*(\d+(?:-ФЗ)?)',
    re.IGNORECASE
)

# 4. Ссылка на пункт договора: "п. 7.3", "п.п. 2.1.1", "пункта 3.2"
RE_CLAUSE_REF = re.compile(
    r'(?:п\.?\s*п\.?|п(?:ункта|ункт|ункте|ункту|\.)?)\s*'
    r'(\d+(?:\.\d+)+)',
    re.IGNORECASE
)

# 5. Ссылка на раздел: "разд. 3", "раздела 5"
RE_SECTION_REF = re.compile(
    r'(?:разд(?:ела|ел|\.)?)\s*(\d+)',
    re.IGNORECASE
)

# 6. Приложение: "Приложение №1", "Приложения N 2", "приложении 3"
RE_APPENDIX_REF = re.compile(
    r'(?:Приложени[яеюиём]+)\s*[№NnНн]?\s*(\d+)',
    re.IGNORECASE
)

# 7. Таблица: "Таблица 1", "таблице №2"
RE_TABLE_REF = re.compile(
    r'(?:Таблиц[аеыуёой]+)\s*[№NnНн]?\s*(\d+)',
    re.IGNORECASE
)

# 8. ГОСТ: "ГОСТ 9353-2016", "ГОСТ Р 52554-2006"
RE_GOST_REF = re.compile(
    r'ГОСТ\s*(?:Р\s*)?(\d+(?:[.-]\d+)*(?:-\d{4})?)',
    re.IGNORECASE
)

# 9. Определение термина: текст в кавычках «» или "" с пояснением
RE_TERM_DEF = re.compile(
    r'[«"]([^»"]{3,50})[»"]\s*(?:–|—|-|означает|значит|является|именуем)',
    re.IGNORECASE
)


# ──────────────────────────────────────────────
# ReferenceExtractor
# ──────────────────────────────────────────────

class ReferenceExtractor:
    """
    Извлечение ссылок из текста узлов графа.

    Использование:
        extractor = ReferenceExtractor()
        refs = extractor.extract("Неустойка по ст. 330 ГК РФ, см. п. 4.2 и Приложение №1")
        # → [norm_ref(330, ГК РФ), clause_ref(4.2), appendix_ref(1)]
    """

    def extract(self, text: str) -> List[ExtractedReference]:
        """Извлечь все ссылки из текста."""
        refs: List[ExtractedReference] = []

        refs.extend(self._extract_norm_refs(text))
        refs.extend(self._extract_federal_laws(text))
        refs.extend(self._extract_clause_refs(text))
        refs.extend(self._extract_appendix_refs(text))
        refs.extend(self._extract_table_refs(text))
        refs.extend(self._extract_gost_refs(text))
        refs.extend(self._extract_term_defs(text))

        # Дедупликация по позиции (если перекрываются)
        refs = self._deduplicate(refs)

        return refs

    def extract_from_nodes(self, nodes: List[Dict]) -> Dict[str, List[ExtractedReference]]:
        """
        Извлечь ссылки из списка узлов.

        Args:
            nodes: Список {'node_id': str, 'text': str}

        Returns:
            Dict: node_id → [ExtractedReference, ...]
        """
        result = {}
        for node in nodes:
            refs = self.extract(node['text'])
            if refs:
                result[node['node_id']] = refs
        return result

    # ──────────────────────────────────────────
    # Extraction methods
    # ──────────────────────────────────────────

    def _extract_norm_refs(self, text: str) -> List[ExtractedReference]:
        """Ссылки на статьи НПА."""
        refs = []

        # Pattern 1: "ст. 330 ГК РФ"
        for m in RE_NORM_ARTICLE.finditer(text):
            code_raw = m.group(4)
            norm_code = NPA_CODES.get(code_raw, code_raw)
            refs.append(ExtractedReference(
                ref_type='norm_ref',
                raw_text=m.group(0),
                start=m.start(),
                end=m.end(),
                norm_code=norm_code,
                article=m.group(1),
                part=m.group(2),
                point=m.group(3),
            ))

        # Pattern 2: "в соответствии со ст. 330 ГК РФ"
        for m in RE_NORM_IN_ACCORDANCE.finditer(text):
            code_raw = m.group(2)
            norm_code = NPA_CODES.get(code_raw, code_raw)
            refs.append(ExtractedReference(
                ref_type='norm_ref',
                raw_text=m.group(0),
                start=m.start(),
                end=m.end(),
                norm_code=norm_code,
                article=m.group(1),
            ))

        return refs

    def _extract_federal_laws(self, text: str) -> List[ExtractedReference]:
        """Ссылки на федеральные законы."""
        refs = []
        for m in RE_FEDERAL_LAW.finditer(text):
            law_num = m.group(1)
            refs.append(ExtractedReference(
                ref_type='norm_ref',
                raw_text=m.group(0),
                start=m.start(),
                end=m.end(),
                norm_code=f"ФЗ-{law_num.replace('-ФЗ', '')}",
                confidence=0.9,
            ))
        return refs

    def _extract_clause_refs(self, text: str) -> List[ExtractedReference]:
        """Ссылки на пункты договора."""
        refs = []
        for m in RE_CLAUSE_REF.finditer(text):
            refs.append(ExtractedReference(
                ref_type='clause_ref',
                raw_text=m.group(0),
                start=m.start(),
                end=m.end(),
                clause_number=m.group(1),
            ))
        return refs

    def _extract_appendix_refs(self, text: str) -> List[ExtractedReference]:
        """Ссылки на приложения."""
        refs = []
        for m in RE_APPENDIX_REF.finditer(text):
            refs.append(ExtractedReference(
                ref_type='appendix_ref',
                raw_text=m.group(0),
                start=m.start(),
                end=m.end(),
                ref_number=m.group(1),
            ))
        return refs

    def _extract_table_refs(self, text: str) -> List[ExtractedReference]:
        """Ссылки на таблицы."""
        refs = []
        for m in RE_TABLE_REF.finditer(text):
            refs.append(ExtractedReference(
                ref_type='table_ref',
                raw_text=m.group(0),
                start=m.start(),
                end=m.end(),
                ref_number=m.group(1),
            ))
        return refs

    def _extract_gost_refs(self, text: str) -> List[ExtractedReference]:
        """Ссылки на ГОСТы."""
        refs = []
        for m in RE_GOST_REF.finditer(text):
            refs.append(ExtractedReference(
                ref_type='gost_ref',
                raw_text=m.group(0),
                start=m.start(),
                end=m.end(),
                gost_code=m.group(1),
                norm_code=f"ГОСТ {m.group(1)}",
            ))
        return refs

    def _extract_term_defs(self, text: str) -> List[ExtractedReference]:
        """Определения терминов."""
        refs = []
        for m in RE_TERM_DEF.finditer(text):
            refs.append(ExtractedReference(
                ref_type='defined_in',
                raw_text=m.group(0),
                start=m.start(),
                end=m.end(),
                clause_number=m.group(1),  # Используем clause_number для хранения термина
                confidence=0.8,
            ))
        return refs

    # ──────────────────────────────────────────
    # Helpers
    # ──────────────────────────────────────────

    @staticmethod
    def _deduplicate(refs: List[ExtractedReference]) -> List[ExtractedReference]:
        """Удалить перекрывающиеся ссылки, оставив более длинные."""
        if not refs:
            return refs

        # Сортируем по позиции начала
        refs.sort(key=lambda r: (r.start, -(r.end - r.start)))

        result = [refs[0]]
        for ref in refs[1:]:
            prev = result[-1]
            # Если не перекрывается с предыдущим
            if ref.start >= prev.end:
                result.append(ref)
            # Если перекрывается, но длиннее — заменяем
            elif (ref.end - ref.start) > (prev.end - prev.start):
                result[-1] = ref

        return result
