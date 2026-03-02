# -*- coding: utf-8 -*-
"""
Complexity Scorer — оценка сложности документа для Smart Router

Возвращает score 0.0-1.0:
- 0.0-0.5: простой (стандартный договор, хорошее качество)
- 0.5-0.8: средний (много разделов, таблицы, большой объём)
- 0.8-1.0: сложный (скан, плохое OCR, огромный документ)
"""

import re
import logging
from typing import Any

logger = logging.getLogger(__name__)


class ComplexityScorer:
    """Rule-based оценка сложности документа."""

    def score(self, extraction_result: Any) -> float:
        """
        Оценивает сложность документа на основе ExtractionResult.

        Args:
            extraction_result: ExtractionResult из TextExtractor

        Returns:
            float 0.0-1.0
        """
        total = 0.0
        details = {}

        text = extraction_result.text or ""
        pages = extraction_result.pages or 1
        confidence = extraction_result.confidence
        method = extraction_result.method or ""
        metadata = extraction_result.metadata or {}

        # 1. Количество страниц
        if pages > 50:
            total += 0.30
            details["pages"] = f"{pages} pages → +0.30"
        elif pages > 20:
            total += 0.15
            details["pages"] = f"{pages} pages → +0.15"
        elif pages > 10:
            total += 0.05
            details["pages"] = f"{pages} pages → +0.05"

        # 2. OCR confidence (только для сканов)
        if confidence is not None and confidence < 0.8:
            penalty = min(0.30, (0.8 - confidence) * 1.0)
            total += penalty
            details["ocr_confidence"] = f"{confidence:.2f} → +{penalty:.2f}"

        # 3. Объём текста
        text_len = len(text)
        if text_len > 100000:
            total += 0.20
            details["text_length"] = f"{text_len} chars → +0.20"
        elif text_len > 50000:
            total += 0.15
            details["text_length"] = f"{text_len} chars → +0.15"
        elif text_len > 20000:
            total += 0.05
            details["text_length"] = f"{text_len} chars → +0.05"

        # 4. Количество разделов (эвристика по заголовкам)
        section_pattern = re.compile(
            r'^\s*\d+\.\s+[А-ЯЁA-Z]', re.MULTILINE
        )
        section_count = len(section_pattern.findall(text))
        if section_count > 20:
            total += 0.15
            details["sections"] = f"{section_count} sections → +0.15"
        elif section_count > 15:
            total += 0.10
            details["sections"] = f"{section_count} sections → +0.10"

        # 5. Наличие таблиц (эвристика)
        table_indicators = text.count('|')
        tab_count = text.count('\t')
        if table_indicators > 20 or tab_count > 30:
            total += 0.15
            details["tables"] = f"pipes={table_indicators}, tabs={tab_count} → +0.15"
        elif table_indicators > 5 or tab_count > 10:
            total += 0.05
            details["tables"] = f"pipes={table_indicators}, tabs={tab_count} → +0.05"

        # 6. Скан/OCR метод
        if method == "ocr":
            total += 0.15
            details["method"] = "OCR → +0.15"

        # 7. Низкая плотность текста (возможный скан)
        chars_per_page = metadata.get("chars_per_page", text_len / pages if pages > 0 else 0)
        if 0 < chars_per_page < 200:
            total += 0.10
            details["density"] = f"{chars_per_page:.0f} chars/page → +0.10"

        final_score = min(1.0, total)

        logger.info(
            f"Complexity score: {final_score:.2f} "
            f"(pages={pages}, text={text_len}, sections={section_count}, method={method})"
        )
        logger.debug(f"Complexity details: {details}")

        return round(final_score, 2)
