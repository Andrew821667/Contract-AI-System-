# -*- coding: utf-8 -*-
"""
ConsultantImporter — загрузка выгрузки OpenClaw_consultant-tools в graph_rag.

Источник данных: ~/consultant-data/
    kodeksy/converted-md/*.md
    federal-laws/fz/converted-md/*.md
    federal-laws/fkz/converted-md/*.md

Каждый .md — НПА с YAML-frontmatter (title/source_url/category/kind/number/
date/edition_date). source_url содержит cons_doc_LAW_<id> = doc_id.

Порядок (см. решение по архитектуре):
  Фаза 1 — ingest каждого документа (layer=npa): parse → ноды → внутри-
           документные рёбра → entities. ОБЯЗАТЕЛЬНАЯ валидация после каждого.
  Фаза 2 — resolve cross-document edges: связать ссылки между разными НПА
           (по doc_id из markdown-ссылок и по norm_ref-entities ГК/ТК/…),
           т.к. target нельзя связать пока он не загружен.

CLI:
    python -m src.core.graph_rag.importers.consultant_importer --dry-run
    python -m src.core.graph_rag.importers.consultant_importer --kind kodeksy
    python -m src.core.graph_rag.importers.consultant_importer            # всё
"""
from __future__ import annotations

import argparse
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

from ..enums import EdgeType, EdgeClass, EdgeStatus, ExtractedBy, LayerType
from ..parser import NPAGraphParser
from .validator import validate_parse_result, ValidationReport

logger = logging.getLogger(__name__)

DATA_ROOT = Path.home() / 'consultant-data'
SOURCES = {
    'kodeksy': DATA_ROOT / 'kodeksy' / 'converted-md',
    'fkz': DATA_ROOT / 'federal-laws' / 'fkz' / 'converted-md',
    'fz': DATA_ROOT / 'federal-laws' / 'fz' / 'converted-md',
}

# Заголовок НПА → нормализованный код (для матчинга norm_ref-ссылок).
# Совпадает по смыслу с NPA_CODES в reference_extractor, но в обратную сторону.
TITLE_TO_NORMCODE = [
    (re.compile(r'гражданск\w+\s+процессуальн', re.I), 'ГПК РФ'),
    (re.compile(r'арбитражн\w+\s+процессуальн', re.I), 'АПК РФ'),
    (re.compile(r'уголовн\w+\s+процессуальн', re.I), 'УПК РФ'),
    (re.compile(r'уголовн\w+\s+исполнительн', re.I), 'УИК РФ'),
    (re.compile(r'гражданск\w+\s+кодекс', re.I), 'ГК РФ'),
    (re.compile(r'налогов\w+\s+кодекс', re.I), 'НК РФ'),
    (re.compile(r'трудов\w+\s+кодекс', re.I), 'ТК РФ'),
    (re.compile(r'уголовн\w+\s+кодекс', re.I), 'УК РФ'),
    (re.compile(r'земельн\w+\s+кодекс', re.I), 'ЗК РФ'),
    (re.compile(r'жилищн\w+\s+кодекс', re.I), 'ЖК РФ'),
    (re.compile(r'семейн\w+\s+кодекс', re.I), 'СК РФ'),
    (re.compile(r'бюджетн\w+\s+кодекс', re.I), 'БК РФ'),
    (re.compile(r'лесн\w+\s+кодекс', re.I), 'ЛК РФ'),
    (re.compile(r'водн\w+\s+кодекс', re.I), 'ВК РФ'),
    (re.compile(r'градостроительн\w+\s+кодекс', re.I), 'ГрК РФ'),
    (re.compile(r'кодекс\w*\s+.*административн', re.I), 'КоАП РФ'),
    (re.compile(r'административн\w+\s+правонаруш', re.I), 'КоАП РФ'),
]

# Markdown inline-ссылка на документ КП: [текст](/document/cons_doc_LAW_<id>/<hash>/)
_DOC_LINK_RE = re.compile(
    r'\[[^\]]+\]\((?:https?:)?(?://www\.consultant\.ru)?'
    r'/document/cons_doc_LAW_(\d+)/[a-f0-9]{16,}/?\)'
)


def _load_all_models() -> None:
    """Импортировать ВСЕ модель-модули, чтобы SQLAlchemy-registry был полным.

    При изолированном запуске импортёра (не через src.main) не все модели
    зарегистрированы, и configure_mappers падает на relationship по имени
    (напр. Counterparty → 'Organization'). Догружаем все известные модули
    моделей до первого запроса к БД.
    """
    import importlib
    import pkgutil
    try:
        import src.models as _m
        for _, name, _is_pkg in pkgutil.iter_modules(_m.__path__):
            importlib.import_module(f"src.models.{name}")
    except Exception as e:
        logger.warning(f"_load_all_models: src.models — {e}")
    for mod in ("src.core.identity_org.models", "src.core.graph_rag.models"):
        try:
            importlib.import_module(mod)
        except Exception as e:
            logger.warning(f"_load_all_models: {mod} — {e}")


def _normcode_from_title(title: str) -> Optional[str]:
    for rx, code in TITLE_TO_NORMCODE:
        if rx.search(title):
            return code
    # ФЗ по номеру: "Федеральный закон от ... N 44-ФЗ"
    m = re.search(r'\bN\s*([\d.]+-ФЗ)\b', title)
    if m:
        return f'ФЗ-{m.group(1).replace("-ФЗ", "")}'
    return None


def _doc_id_from_url(url: str) -> Optional[str]:
    m = re.search(r'cons_doc_LAW_(\d+)', url or '')
    return m.group(1) if m else None


@dataclass
class ImportReport:
    total_files: int = 0
    ingested: int = 0
    skipped: int = 0
    failed: int = 0
    validation_failed: int = 0
    cross_edges_created: int = 0
    reports: List[ValidationReport] = field(default_factory=list)

    def log_summary(self):
        logger.info('=' * 64)
        logger.info(f'ИТОГО: файлов={self.total_files}, ingested={self.ingested}, '
                    f'skip={self.skipped}, fail={self.failed}, '
                    f'валидация-fail={self.validation_failed}, '
                    f'cross-рёбра={self.cross_edges_created}')


class ConsultantImporter:
    """Импорт НПА из ~/consultant-data в graph_rag.

    db=None → dry-run (только parse + валидация, без записи в граф).
    """

    def __init__(self, db=None, data_root: Path = DATA_ROOT):
        self.db = db
        self.data_root = data_root
        self.parser = NPAGraphParser()
        self.pipeline = None
        if db is not None:
            from ..pipeline import GraphRAGPipeline
            self.pipeline = GraphRAGPipeline(db)
        # doc_id → graph_document_id (для Фазы 2)
        self._docid_to_gdoc: Dict[str, str] = {}
        # norm_code → graph_document_id
        self._normcode_to_gdoc: Dict[str, str] = {}

    # ── discovery ──────────────────────────────────────────────
    def discover(self, kinds: Optional[List[str]] = None) -> List[Path]:
        kinds = kinds or list(SOURCES.keys())
        files: List[Path] = []
        for k in kinds:
            d = SOURCES.get(k)
            if d and d.exists():
                files.extend(sorted(d.glob('*.md')))
        return files

    # ── Фаза 1 ─────────────────────────────────────────────────
    def import_all(self, kinds: Optional[List[str]] = None,
                   dry_run: bool = False, limit: Optional[int] = None) -> ImportReport:
        if not dry_run and self.pipeline is not None:
            _load_all_models()  # полный SQLAlchemy-registry до первого запроса
        files = self.discover(kinds)
        if limit:
            files = files[:limit]
        rep = ImportReport(total_files=len(files))
        logger.info(f'Найдено файлов: {len(files)} (dry_run={dry_run})')

        for i, path in enumerate(files, 1):
            try:
                parse_result = self.parser.parse_file(str(path))
            except Exception as e:
                logger.error(f'[{i}/{len(files)}] PARSE FAIL {path.name}: {e}')
                rep.failed += 1
                continue

            # body для валидации (без frontmatter)
            raw = path.read_text(encoding='utf-8')
            body = re.sub(r'^---\n.*?\n---\n', '', raw, count=1, flags=re.DOTALL)

            # ОБЯЗАТЕЛЬНАЯ автопроверка
            vrep = validate_parse_result(parse_result, body, file_label=path.name)
            rep.reports.append(vrep)
            logger.info(f'[{i}/{len(files)}] {vrep.summary()}')
            if not vrep.ok:
                rep.validation_failed += 1
                continue  # битый документ в граф НЕ грузим

            if dry_run or self.pipeline is None:
                continue

            # Ingest (source_file = source_url, чтобы хранить doc_id)
            source_url = (parse_result.metadata or {}).get('source_url') or str(path)
            result = self.pipeline._ingest(parse_result, source_file=source_url)
            if result.extraction_warnings and 'уже загружен' in ' '.join(result.extraction_warnings):
                rep.skipped += 1
            else:
                rep.ingested += 1

            # Карты для Фазы 2
            gdoc_id = result.document.id
            doc_id = _doc_id_from_url(source_url)
            if doc_id:
                self._docid_to_gdoc[doc_id] = gdoc_id
            nc = _normcode_from_title(parse_result.title)
            if nc:
                self._normcode_to_gdoc[nc] = gdoc_id

        # ── Фаза 2 ──
        if not dry_run and self.pipeline is not None:
            rep.cross_edges_created = self.resolve_cross_document_edges()
            self.pipeline.repo.commit()

        rep.log_summary()
        return rep

    # ── Фаза 2: cross-document рёбра ───────────────────────────
    def resolve_cross_document_edges(self) -> int:
        """Связать ссылки между разными НПА.

        (А) norm_ref-entities (ГК РФ ст.330 и т.п.), сохранённые pipeline при
            ingest, → рёбра REGULATED_BY на конкретную статью целевого НПА.
        (Б) markdown inline-ссылки [..](/document/cons_doc_LAW_X/..) в тексте
            нод → рёбра REFERENCES на корень целевого документа (по doc_id).
        """
        if self.pipeline is None:
            return 0
        repo = self.pipeline.repo
        created = 0

        # (А) norm_ref entities → REGULATED_BY на статью целевого НПА
        for norm_code, target_gdoc in self._normcode_to_gdoc.items():
            ents = repo.entities.find_norm_references(norm_code=norm_code)
            for ent in ents:
                target_node = None
                if ent.norm_article:
                    target_node = repo.nodes.find_by_number(
                        target_gdoc, ent.norm_article
                    ) or repo.nodes.find_by_number(
                        target_gdoc, f'ст. {ent.norm_article}'
                    )
                if not target_node:
                    # на корень документа
                    roots = [n for n in repo.nodes.get_by_document(target_gdoc)
                             if n.node_type == 'document']
                    target_node = roots[0] if roots else None
                if not target_node or ent.node_id == target_node.id:
                    continue
                repo.edges.create(
                    actor='importer',
                    source_id=ent.node_id,
                    target_id=target_node.id,
                    edge_type=EdgeType.REGULATED_BY.value,
                    edge_class=EdgeClass.FACT.value,
                    status=EdgeStatus.MACHINE_EXTRACTED.value,
                    extracted_by=ExtractedBy.RULE.value,
                    confidence=float(ent.confidence or 0.8),
                    evidence=ent.raw_text,
                    rationale=f'norm_ref → {norm_code} ст.{ent.norm_article}',
                )
                created += 1

        # (Б) markdown inline-ссылки в тексте нод → REFERENCES на корень target
        for doc_id, src_gdoc in self._docid_to_gdoc.items():
            for node in repo.nodes.get_by_document(src_gdoc):
                if not node.text or 'cons_doc_LAW_' not in node.text:
                    continue
                for m in _DOC_LINK_RE.finditer(node.text):
                    tgt_doc_id = m.group(1)
                    tgt_gdoc = self._docid_to_gdoc.get(tgt_doc_id)
                    if not tgt_gdoc or tgt_gdoc == src_gdoc:
                        continue  # ссылка на не загруженный НПА или сам на себя
                    roots = [n for n in repo.nodes.get_by_document(tgt_gdoc)
                             if n.node_type == 'document']
                    if not roots:
                        continue
                    repo.edges.create(
                        actor='importer',
                        source_id=node.id,
                        target_id=roots[0].id,
                        edge_type=EdgeType.REFERENCES.value,
                        edge_class=EdgeClass.FACT.value,
                        status=EdgeStatus.MACHINE_EXTRACTED.value,
                        extracted_by=ExtractedBy.RULE.value,
                        confidence=0.95,
                        evidence=m.group(0)[:200],
                        rationale=f'inline-ссылка → cons_doc_LAW_{tgt_doc_id}',
                    )
                    created += 1

        logger.info(f'Фаза 2: создано cross-document рёбер: {created}')
        return created


# ── CLI ────────────────────────────────────────────────────────
def main():
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(message)s',
    )
    ap = argparse.ArgumentParser()
    ap.add_argument('--dry-run', action='store_true',
                    help='Только parse + валидация, без записи в граф (не нужна БД)')
    ap.add_argument('--kind', choices=list(SOURCES.keys()), action='append',
                    help='Какие источники грузить (можно несколько). По умолч. — все')
    ap.add_argument('--limit', type=int, help='Ограничить число файлов (тест)')
    args = ap.parse_args()

    db = None
    if not args.dry_run:
        from src.models.database import SessionLocal
        db = SessionLocal()
    try:
        importer = ConsultantImporter(db=db)
        importer.import_all(kinds=args.kind, dry_run=args.dry_run, limit=args.limit)
    finally:
        if db is not None:
            db.close()


if __name__ == '__main__':
    main()
