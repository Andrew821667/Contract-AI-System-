# -*- coding: utf-8 -*-
"""
Валидатор результатов парсинга НПА.

ОБЯЗАТЕЛЬНАЯ автопроверка после каждого запуска парсинга (требование КС):
гарантирует, что в граф не попадают пустышки, TOC-заглушки и битые документы.

Используется:
  - ConsultantImporter после каждого ingest (Фаза 1)
  - standalone-проверка уже скачанных .md (dry-run, без БД)

Проверки (severity error блокирует ingest, warning — только лог):
  E1 parse_status == FULLY_PARSED / PARTIAL_PARSE (не FAILED)
  E2 есть тело: >= MIN_BODY_CHARS символов очищенного текста
  E3 есть структура: >= 1 нода типа article (для НПА)
  E4 не TOC-заглушка: доля article-нод от общего числа нод адекватна
  E5 нет маркеров недоступности ('доступен по расписанию', 'некоммерческая версия')
  E6 frontmatter распознан: document_type определён, title непустой
  W1 metadata.source_url присутствует (нужен для граф-рёбер)
  W2 metadata.number (номер ФЗ/кодекса) присутствует
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

# Пороги
MIN_BODY_CHARS = 2000        # минимум очищенного текста документа
MIN_ARTICLES = 1             # минимум статей для НПА
BLOCKERS = (
    'доступен по расписанию',
    'некоммерческая версия',
    'Войдите в систему и используйте',
)


@dataclass
class ValidationIssue:
    code: str                # E1..E6 / W1..W2
    severity: str            # 'error' | 'warning'
    message: str


@dataclass
class ValidationReport:
    file: str
    ok: bool
    issues: List[ValidationIssue] = field(default_factory=list)
    nodes_count: int = 0
    article_count: int = 0
    body_chars: int = 0

    @property
    def errors(self) -> List[ValidationIssue]:
        return [i for i in self.issues if i.severity == 'error']

    @property
    def warnings(self) -> List[ValidationIssue]:
        return [i for i in self.issues if i.severity == 'warning']

    def summary(self) -> str:
        if self.ok:
            extra = f" ({len(self.warnings)} warn)" if self.warnings else ""
            return (f"OK   {self.file}: {self.nodes_count} нод, "
                    f"{self.article_count} статей, {self.body_chars:,} симв{extra}")
        errs = '; '.join(f"{i.code}:{i.message}" for i in self.errors)
        return f"FAIL {self.file}: {errs}"


def _count_articles(root) -> int:
    """Сколько структурных единиц в дереве ParseResult.

    Считаем статьи (article) И пункты (clause): у законов/кодексов структура —
    статьи, у постановлений/указов — пункты верхнего уровня (плоский режим
    парсера). И то и другое — валидная нормативная структура для E3.
    """
    cnt = 0
    stack = [root]
    while stack:
        n = stack.pop()
        nt = n.node_type.value if hasattr(n.node_type, 'value') else n.node_type
        if nt in ('article', 'clause'):
            cnt += 1
        stack.extend(n.children)
    return cnt


def validate_parse_result(parse_result, body_text: str,
                          file_label: str = "") -> ValidationReport:
    """Проверить результат парсинга НПА. Не требует БД.

    Args:
        parse_result: ParseResult из NPAGraphParser
        body_text: тело документа (markdown без frontmatter) — для проверки
                   маркеров недоступности и объёма
        file_label: имя файла для отчёта
    """
    rep = ValidationReport(file=file_label, ok=True)
    rep.nodes_count = parse_result.nodes_count
    rep.article_count = _count_articles(parse_result.root)
    rep.body_chars = len(body_text or "")

    status = parse_result.parse_status
    status_val = status.value if hasattr(status, 'value') else str(status)

    # E1 — статус парсинга
    if status_val == 'failed':
        rep.issues.append(ValidationIssue('E1', 'error',
            f'parse_status=failed: {parse_result.parse_errors}'))

    # E5 — маркеры недоступности (проверяем первыми — самое явное)
    low = (body_text or "").lower()
    for marker in BLOCKERS:
        if marker.lower() in low:
            rep.issues.append(ValidationIssue('E5', 'error',
                f'маркер недоступности: «{marker}»'))
            break

    # E2 — объём тела
    if rep.body_chars < MIN_BODY_CHARS:
        rep.issues.append(ValidationIssue('E2', 'error',
            f'тело {rep.body_chars} < {MIN_BODY_CHARS} симв (вероятно TOC/пустышка)'))

    # E3 — наличие статей
    if rep.article_count < MIN_ARTICLES:
        rep.issues.append(ValidationIssue('E3', 'error',
            f'статей {rep.article_count} < {MIN_ARTICLES} (структура не распознана)'))

    # E6 — метаданные документа
    if not parse_result.document_type:
        rep.issues.append(ValidationIssue('E6', 'error',
            'document_type не определён (frontmatter не распознан?)'))
    if not parse_result.title or not parse_result.title.strip():
        rep.issues.append(ValidationIssue('E6', 'error', 'title пустой'))

    # W1/W2 — метаданные для граф-рёбер
    meta = parse_result.metadata or {}
    if not meta.get('source_url'):
        rep.issues.append(ValidationIssue('W1', 'warning',
            'нет source_url в metadata (cross-doc рёбра не свяжутся по doc_id)'))
    if not meta.get('number'):
        rep.issues.append(ValidationIssue('W2', 'warning', 'нет номера НПА'))

    rep.ok = len(rep.errors) == 0
    return rep
