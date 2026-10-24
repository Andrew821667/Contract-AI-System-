# -*- coding: utf-8 -*-
"""
ConsultantImporter — загрузка выгрузки инструментов К+ (tools/consultant) в graph_rag.

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
from ..models import CandidateEdge, GraphDocument, GraphEdge, GraphEntity, GraphNode, NodeVersion
from ..parser import NPAGraphParser
from .validator import validate_parse_result, ValidationReport

logger = logging.getLogger(__name__)

DATA_ROOT = Path.home() / 'consultant-data'
SOURCES = {
    'kodeksy': DATA_ROOT / 'kodeksy' / 'converted-md',
    'fkz': DATA_ROOT / 'federal-laws' / 'fkz' / 'converted-md',
    'fz': DATA_ROOT / 'federal-laws' / 'fz' / 'converted-md',
    # Подзаконные акты (постановления/распоряжения Правительства, указы
    # Президента) — frontmatter category: government_decree|government_order|
    # presidential_decree. Парсятся в плоском режиме (пункты-CLAUSE).
    'decrees': DATA_ROOT / 'decrees' / 'converted-md',
    # Судебная практика высших судов (Пленумы ВС, ВС, КС, обзоры) — подпапки
    # по слугам органов: court-practice/<slug>/converted-md/*.md. category=
    # court_practice. Парсятся в плоском режиме (пункты/абзацы).
    'court': DATA_ROOT / 'court-practice',
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

# Markdown inline-ссылка на документ КП. Форматы в тексте К+:
#   [текст](/document/cons_doc_LAW_<id>/<hash>/)
#   [текст](/document/cons_doc_LAW_<id>/<hash>/#dst100017)   ← с якорем!
#   [текст](//www.consultant.ru/document/cons_doc_LAW_<id>/) ← без хэша
_DOC_LINK_RE = re.compile(
    r'\[[^\]]+\]\((?:https?:)?(?://www\.consultant\.ru)?'
    r'/document/cons_doc_LAW_(\d+)(?:/[a-f0-9]{16,})?/?(?:#[^)]*)?\)'
)

# Реквизит подзаконного акта в ТЕКСТЕ НПА (для линкера закон→подзаконка).
# Подзаконка цитируется простым текстом «Постановлением Правительства РФ от
# 07.02.2011 N 55» (без гиперссылки и норм-кода), поэтому Фаза 2 (А)/(Б) её не
# ловит. Сопоставляем по (вид, дата, номер) с заголовками залитых подзаконных
# актов. Группы: 1=корень вида, 2=орган, 3=дата (dd.mm.yyyy), 4=номер.
_SUBORD_REQ_RE = re.compile(
    r'(постановлени|распоряжени|указ)\w*\s+'
    r'(Правительств|Президент)\w*\s+(?:Российской\s+Федерации|РФ)\s+'
    r'от\s+(\d{2}\.\d{2}\.\d{4})\s+N\s*([0-9][\w\-/.]*)',
    re.IGNORECASE,
)


def _subord_kind(stem: str, organ: str) -> Optional[str]:
    """(корень вида, орган) → document_type подзаконного акта."""
    s, o = stem.lower(), organ.lower()
    if s.startswith('постановлени') and o.startswith('правительств'):
        return 'government_decree'
    if s.startswith('распоряжени') and o.startswith('правительств'):
        return 'government_order'
    if s.startswith('указ') and o.startswith('президент'):
        return 'presidential_decree'
    return None


# Реквизит из ЗАГОЛОВКА подзаконного акта (для построения карты целей).
_SUBORD_TITLE_RE = re.compile(
    r'(постановлени|распоряжени|указ)\w*\s+'
    r'(Правительств|Президент)\w*\s+(?:Российской\s+Федерации|РФ)\s+'
    r'от\s+(\d{2}\.\d{2}\.\d{4})\s+N\s*([0-9][\w\-/.]*)',
    re.IGNORECASE,
)


def _file_docid(path) -> Optional[str]:
    """Прочитать doc_id (cons_doc_LAW_<id>) из frontmatter source_url .md-файла.

    Дёшево (только начало файла) — для пропуска уже загруженных без полного парса.
    """
    try:
        with open(path, 'r', encoding='utf-8', errors='replace') as f:
            head = f.read(600)
    except Exception:
        return None
    m = re.search(r'cons_doc_LAW_(\d+)', head)
    return m.group(1) if m else None


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
    replaced: int = 0
    inbound_restored: int = 0
    failed: int = 0
    validation_failed: int = 0
    cross_edges_created: int = 0
    reports: List[ValidationReport] = field(default_factory=list)

    def log_summary(self):
        logger.info('=' * 64)
        logger.info(f'ИТОГО: файлов={self.total_files}, ingested={self.ingested}, '
                    f'skip={self.skipped}, replaced={self.replaced}, '
                    f'входящих-перенесено={self.inbound_restored}, fail={self.failed}, '
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
                # rglob — чтобы охватить подпапки по слугам (court-practice/<slug>/...)
                files.extend(sorted(d.rglob('*.md')))
        return files

    # ── Фаза 1 ─────────────────────────────────────────────────
    def _node_paths(self, gdoc_id: str) -> Dict[str, tuple]:
        """node_id → адрес узла в документе: цепочка (тип, номер) от корня.

        У новой редакции другие id узлов, а адрес тот же: «статья 330, пункт 2»
        остаётся собой. По адресу входящие ссылки переносятся на новую редакцию.
        """
        rows = (self.pipeline.db.query(GraphNode.id, GraphNode.parent_id,
                                       GraphNode.node_type, GraphNode.number)
                .filter(GraphNode.document_id == gdoc_id)
                .order_by(GraphNode.level, GraphNode.position).all())
        paths: Dict[str, tuple] = {}
        for nid, parent_id, node_type, number in rows:  # родитель раньше детей (level)
            paths[nid] = paths.get(parent_id, ()) + ((node_type, (number or '').strip()),)
        return paths

    def _purge_by_source(self, source_url: str) -> Optional[List[dict]]:
        """Полностью удалить документ и его граф по source_file (для REPLACE).

        Удаляет рёбра (ссылающиеся на ноды документа), entities, версии нод,
        ноды и сам документ. Возвращает None, если документа не было, иначе —
        входящие рёбра из ДРУГИХ документов (адрес цели + поля ребра): их
        создавала Фаза 2 и прямой линкер по всему графу, а повторный прогон по
        одному документу их не восстановит — _restore_inbound переносит их на
        новую редакцию.
        """
        db = self.pipeline.db
        doc = (db.query(GraphDocument)
               .filter(GraphDocument.source_file == source_url).first())
        if not doc:
            return None
        paths = self._node_paths(doc.id)
        own = db.query(GraphNode.id).filter(GraphNode.document_id == doc.id)
        inbound = []
        for e in (db.query(GraphEdge)
                  .join(GraphNode, GraphNode.id == GraphEdge.source_id)
                  .filter(GraphEdge.target_id.in_(own), GraphNode.document_id != doc.id)):
            inbound.append({
                'source_id': e.source_id, 'target_path': paths.get(e.target_id, ()),
                'edge_type': e.edge_type, 'edge_class': e.edge_class, 'status': e.status,
                'evidence': e.evidence, 'rationale': e.rationale, 'confidence': e.confidence,
                'extracted_by': e.extracted_by, 'valid_from': e.valid_from, 'valid_to': e.valid_to,
            })
        # подзапрос, а не список id: у кодекса десятки тысяч нод
        for model, cols in ((GraphEdge, ('source_id', 'target_id')),
                            (CandidateEdge, ('source_id', 'target_id')),
                            (NodeVersion, ('node_id',))):
            for col in cols:
                db.query(model).filter(getattr(model, col).in_(own)).delete(synchronize_session=False)
        from sqlalchemy import text as _sql
        db.execute(_sql("DELETE FROM graph_entities WHERE node_id IN (SELECT id FROM graph_nodes WHERE document_id=:d)"), {"d": doc.id})
        db.query(GraphNode).filter(GraphNode.document_id == doc.id).delete(synchronize_session=False)
        db.query(GraphDocument).filter(GraphDocument.id == doc.id).delete(synchronize_session=False)
        db.flush()
        logger.info(f'PURGE: удалён старый документ {doc.id} ({len(paths)} нод, '
                    f'входящих рёбер к переносу {len(inbound)}) для замены')
        return inbound

    def _restore_inbound(self, inbound: List[dict], new_gdoc_id: str) -> int:
        """Перевесить входящие рёбра на узлы новой редакции по адресу.

        Узла с тем же адресом нет (пункт исключён, статьи перенумерованы) —
        ребро уходит на ближайшего сохранившегося предка, в крайнем случае на
        корень документа: ссылка на кодекс важнее точной статьи.
        """
        by_path: Dict[tuple, str] = {}
        root = None
        for nid, path in self._node_paths(new_gdoc_id).items():
            by_path.setdefault(path, nid)  # дубль адреса — первый по порядку
            if root is None and path and path[-1][0] == 'document':
                root = nid
        restored = 0
        seen = set()
        for spec in inbound:
            path = spec['target_path']
            while path and path not in by_path:
                path = path[:-1]
            target = by_path[path] if path else root
            if target is None:
                continue
            key = (spec['source_id'], target, spec['edge_type'])
            if key in seen:
                continue  # два старых ребра свелись к одному узлу
            seen.add(key)
            fields = {k: v for k, v in spec.items() if k != 'target_path'}
            self.pipeline.repo.edges.create(actor='importer', target_id=target, **fields)
            restored += 1
        self.pipeline.repo.commit()
        return restored

    def import_all(self, kinds: Optional[List[str]] = None,
                   dry_run: bool = False, limit: Optional[int] = None,
                   no_phase2: bool = False, update: bool = False,
                   only_docids: Optional[set] = None) -> ImportReport:
        if not dry_run and self.pipeline is not None:
            _load_all_models()  # полный SQLAlchemy-registry до первого запроса
        files = self.discover(kinds)
        # Точечный режим: только указанные doc_id (для edition-diff обновления).
        if only_docids:
            files = [f for f in files if _file_docid(f) in only_docids]
            logger.info(f'Только указанные doc_id: {len(files)} файлов')
        # Пропуск уже загруженных (по doc_id из frontmatter source_url) — чтобы
        # инкрементальные ночные заливки не перепарсивали тысячи готовых файлов.
        # В режиме update пропуск НЕ применяем (нужно перезалить существующие).
        if not dry_run and self.pipeline is not None and not update:
            loaded = set()
            for (sf,) in self.pipeline.db.query(GraphDocument.source_file).filter(
                    GraphDocument.layer == LayerType.NPA.value):
                mm = re.search(r'cons_doc_LAW_(\d+)', sf or '')
                if mm:
                    loaded.add(mm.group(1))
            if loaded:
                before = len(files)
                files = [f for f in files if _file_docid(f) not in loaded]
                logger.info(f'Пропущено уже загруженных: {before - len(files)}')
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
            # Режим обновления: если документ уже есть — удалить старую версию
            # целиком (ноды/рёбра/entities/документ) перед перезаливкой, а
            # ссылки на неё из других документов перенести на новую.
            inbound = None
            if update:
                inbound = self._purge_by_source(source_url)
                if inbound is not None:
                    rep.replaced += 1
            result = self.pipeline._ingest(parse_result, source_file=source_url)
            if result.extraction_warnings and 'уже загружен' in ' '.join(result.extraction_warnings):
                rep.skipped += 1
            else:
                rep.ingested += 1
                if inbound:
                    rep.inbound_restored += self._restore_inbound(inbound, result.document.id)

            # Карты для Фазы 2
            gdoc_id = result.document.id
            doc_id = _doc_id_from_url(source_url)
            if doc_id:
                self._docid_to_gdoc[doc_id] = gdoc_id
            nc = _normcode_from_title(parse_result.title)
            if nc:
                self._normcode_to_gdoc[nc] = gdoc_id

        # ── Фаза 2 ──
        if dry_run or self.pipeline is None:
            pass
        elif no_phase2:
            self.pipeline.repo.commit()
            logger.info('Фаза 2 пропущена (--no-phase2)')
        elif not self._docid_to_gdoc:
            # Без источников resolve_cross_document_edges взял бы ВСЕ НПА графа —
            # это режим --relink, а не инкрементальный прогон.
            logger.info('Фаза 2: в прогоне не залито ни одного документа — пропуск')
        else:
            rep.cross_edges_created = self.resolve_cross_document_edges()
            self.pipeline.repo.commit()

        rep.log_summary()
        return rep

    # ── Фаза 2: cross-document рёбра ───────────────────────────
    def resolve_cross_document_edges(self) -> int:
        """Связать ссылки между разными НПА — по ВСЕЙ БД, не только по тек. запуску.

        Карты целей (doc_id→gdoc, norm_code→gdoc) строятся из ВСЕХ активных НПА
        в графе, поэтому ссылки только что залитых документов резолвятся на уже
        существующие (напр. ФКЗ → ранее залитый ГК/УК). Источники — узлы текущего
        запуска (чтобы не пересканировать весь граф). Дедуп по существующим рёбрам.

        (А) norm_ref-entities (ГК РФ ст.330 …) → REGULATED_BY на статью цели.
        (Б) inline-ссылки [..](/document/cons_doc_LAW_X/..) → REFERENCES на цель.
        """
        if self.pipeline is None:
            return 0
        repo = self.pipeline.repo
        db = self.pipeline.db
        created = 0

        # Карты целей из ВСЕЙ БД
        docid_all: Dict[str, str] = {}
        # norm_code → документы: у кодекса все части (ГК — 4, НК — 2; нумерация
        # статей сквозная), у прочих — один документ, как раньше
        normcode_all: Dict[str, List[str]] = {}
        code_ids: set = set()
        ambiguous: set = set()
        # (вид, дата, номер) → gdoc подзаконного акта (для линкера (В))
        subord_by_req: Dict[tuple, str] = {}
        # Порядок решает, кому достанется код: «ГК РФ» матчит и сам ГК, и ФЗ
        # «О введении в действие … Гражданского кодекса». Раньше выигрывал ГК —
        # его залили первым; после замены редакции новый ГК — последний, и
        # ссылки «ст. 330 ГК РФ» ушли бы в закон о введении. Поэтому кодексы —
        # вперёд (части по порядку: ч.1 раньше ч.2), прочие — по времени
        # загрузки, как было.
        docs = (db.query(GraphDocument)
                .filter(GraphDocument.layer == LayerType.NPA.value,
                        GraphDocument.status == 'active')
                .order_by(GraphDocument.created_at).all())
        # kodeks — из frontmatter выгрузки К+, codex — тип парсера по заголовку
        is_code = lambda d: d.document_type in ('kodeks', 'codex')  # noqa: E731
        docs.sort(key=lambda d: (not is_code(d), (d.title or '') if is_code(d) else ''))
        for d in docs:
            mm = re.search(r'cons_doc_LAW_(\d+)', d.source_file or '')
            if mm:
                docid_all[mm.group(1)] = d.id
            nc = _normcode_from_title(d.title)
            if nc and is_code(d):
                normcode_all.setdefault(nc, []).append(d.id)
            elif nc and nc not in normcode_all:
                normcode_all[nc] = [d.id]
            elif nc and normcode_all[nc][0] not in code_ids:
                ambiguous.add(nc)  # второй ФЗ с тем же номером (другого года)
            if is_code(d):
                code_ids.add(d.id)
            # подзаконные акты → карта по реквизитам (из заголовка)
            if (d.document_type in ('government_decree', 'government_order',
                                    'presidential_decree') and d.title):
                tm = _SUBORD_TITLE_RE.search(d.title)
                if tm:
                    kind = _subord_kind(tm.group(1), tm.group(2))
                    if kind:
                        key = (kind, tm.group(3), tm.group(4).rstrip('.').lower())
                        subord_by_req.setdefault(key, d.id)

        # Источники — gdoc'и текущего запуска (если карта пуста — берём все НПА)
        src_gdocs = set(self._docid_to_gdoc.values()) or set(docid_all.values())
        # node_id → True для узлов источников (для фильтра (А))
        src_node_ids = set()
        roots_by_gdoc: Dict[str, str] = {}
        nodes_by_gdoc: Dict[str, list] = {}
        # Ноды — запросом только по document_id, архив отсекается в Python.
        # В прод-SQLite нет статистики индексов (ANALYZE), и с условием
        # is_archived=0 (repo.nodes.get_by_document/find_by_number) планировщик
        # берёт ix_graph_nodes_is_archived — перебор ВСЕХ нод графа с текстами
        # (334 тыс.) на каждый вызов: Фаза 2 по 23 кодексам не кончалась и за час.
        for gd in src_gdocs:
            nodes = [n for n in (db.query(GraphNode).filter(GraphNode.document_id == gd)
                                 .order_by(GraphNode.level, GraphNode.position))
                     if not n.is_archived]
            nodes_by_gdoc[gd] = nodes
            for n in nodes:
                src_node_ids.add(n.id)
                if n.node_type == 'document':
                    roots_by_gdoc[gd] = n.id

        # корень любого целевого документа (кэш)
        root_cache: Dict[str, Optional[str]] = {}
        def _root(gdoc: str) -> Optional[str]:
            # только корень, а не все ноды цели с текстами (у кодекса их тысячи;
            # индекс ix_graph_nodes_doc_level: document_id + level корня)
            if gdoc not in root_cache:
                rows = (db.query(GraphNode.id, GraphNode.node_type, GraphNode.is_archived)
                        .filter(GraphNode.document_id == gdoc, GraphNode.level == 0)
                        .order_by(GraphNode.position).all())
                root_cache[gdoc] = next((r.id for r in rows if r.node_type == 'document'
                                         and not r.is_archived), None)
            return root_cache[gdoc]

        # Существующие рёбра (дедуп)
        existing = set()
        for s, t, et in db.query(GraphEdge.source_id, GraphEdge.target_id,
                                 GraphEdge.edge_type).filter(
                GraphEdge.edge_type.in_([EdgeType.REGULATED_BY.value,
                                         EdgeType.REFERENCES.value])):
            existing.add((s, t, et))

        def _add_edge(src, tgt, etype, conf, evidence, rationale):
            nonlocal created
            if not tgt or src == tgt or (src, tgt, etype) in existing:
                return
            repo.edges.create(
                actor='importer', source_id=src, target_id=tgt,
                edge_type=etype, edge_class=EdgeClass.FACT.value,
                status=EdgeStatus.MACHINE_EXTRACTED.value,
                extracted_by=ExtractedBy.RULE.value,
                confidence=conf, evidence=evidence, rationale=rationale,
            )
            existing.add((src, tgt, etype))
            created += 1

        # (А) norm_ref entities → REGULATED_BY (источник из текущего запуска).
        # Одним запросом по нодам источников. Прежний цикл «по каждому коду —
        # ILIKE по всем entities графа» при тысячах кодов ФЗ-N перечитывал
        # 4-гигабайтную базу десятки минут (замена 23 кодексов, 24.10.2026).
        # Код — точным совпадением. Прежний ILIKE '%ФЗ-4%' цеплял и ФЗ-425,
        # ФЗ-42…: на копии прод-базы все неточные совпадения были ложными.
        # Номер ФЗ без даты, который в базе носят несколько законов разных лет
        # (235 из 391), не связываем — цель была бы случайной.
        # Тип entity — в Python: с ним в SQL планировщик идёт индексом типа по
        # всем norm_ref графа, без него — индексом node_id по нодам источников.
        if self._docid_to_gdoc:
            src_nodes_q = db.query(GraphNode.id).filter(GraphNode.document_id.in_(src_gdocs))
            ent_q = db.query(GraphEntity).filter(GraphEntity.node_id.in_(src_nodes_q))
        else:
            ent_q = db.query(GraphEntity).filter(GraphEntity.entity_type == 'norm_ref')
        targets_for: Dict[str, list] = {}
        numbers_of: Dict[str, Dict[str, str]] = {}

        def _by_number(gdoc: str, number: str) -> Optional[str]:
            # номер → первая нода с ним (как find_by_number), одним запросом на цель
            if gdoc not in numbers_of:
                m: Dict[str, str] = {}
                for nid, num, archived in (db.query(GraphNode.id, GraphNode.number,
                                                    GraphNode.is_archived)
                                           .filter(GraphNode.document_id == gdoc)):
                    if num and not archived:
                        m.setdefault(num, nid)
                numbers_of[gdoc] = m
            return numbers_of[gdoc].get(number)

        for ent in ent_q.all():
            if ent.entity_type != 'norm_ref' or ent.node_id not in src_node_ids:
                continue
            code = ent.norm_code or ''
            if code not in targets_for:
                targets_for[code] = ([(code, normcode_all[code])]
                                     if code in normcode_all and code not in ambiguous else [])
            for norm_code, target_gdocs in targets_for[code]:
                tgt = None
                if ent.norm_article:
                    # статья — в той части кодекса, где она есть (ст. 506 ГК — ч.2)
                    tgt = next((t for g in target_gdocs
                                for t in (_by_number(g, ent.norm_article),
                                          _by_number(g, f'ст. {ent.norm_article}')) if t), None)
                _add_edge(ent.node_id, tgt or _root(target_gdocs[0]), EdgeType.REGULATED_BY.value,
                          float(ent.confidence or 0.8), ent.raw_text,
                          f'norm_ref → {norm_code} ст.{ent.norm_article}')

        # (Б) inline-ссылки cons_doc_LAW → REFERENCES (источник из текущего запуска)
        # (В) текстовые реквизиты подзаконки → REFERENCES на акт-цель
        for gd, nodes in nodes_by_gdoc.items():
            for node in nodes:
                if not node.text:
                    continue
                if 'cons_doc_LAW_' in node.text:
                    for m in _DOC_LINK_RE.finditer(node.text):
                        tgt_gdoc = docid_all.get(m.group(1))
                        if not tgt_gdoc or tgt_gdoc == gd:
                            continue
                        _add_edge(node.id, _root(tgt_gdoc), EdgeType.REFERENCES.value,
                                  0.95, m.group(0)[:200],
                                  f'inline-ссылка → cons_doc_LAW_{m.group(1)}')
                # (В) «Постановлением Правительства РФ от ДАТА N НОМЕР» текстом
                if subord_by_req and ('равительств' in node.text or 'резидент' in node.text):
                    for m in _SUBORD_REQ_RE.finditer(node.text):
                        kind = _subord_kind(m.group(1), m.group(2))
                        if not kind:
                            continue
                        key = (kind, m.group(3), m.group(4).rstrip('.').lower())
                        tgt_gdoc = subord_by_req.get(key)
                        if not tgt_gdoc or tgt_gdoc == gd:
                            continue
                        _add_edge(node.id, _root(tgt_gdoc), EdgeType.REFERENCES.value,
                                  0.9, m.group(0)[:200],
                                  f'реквизит → {kind} от {m.group(3)} N {m.group(4)}')

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
    ap.add_argument('--relink', action='store_true',
                    help='Только Фаза 2: пересобрать cross-document рёбра по всему '
                         'графу (без ingest). Бэкфилл связей между уже залитыми НПА.')
    ap.add_argument('--no-phase2', action='store_true',
                    help='Заливка без Фазы 2 (быстро, для инкрементальных прогонов). '
                         'Cross-рёбра строить отдельно прямым линкером.')
    ap.add_argument('--update', action='store_true',
                    help='REPLACE-режим: существующие документы (по source_file) '
                         'удаляются целиком и перезаливаются (обновление редакций).')
    ap.add_argument('--only-docids', default='',
                    help='Через запятую: обрабатывать только эти doc_id (точечно).')
    args = ap.parse_args()

    db = None
    if not args.dry_run:
        from src.models.database import SessionLocal
        db = SessionLocal()
    try:
        importer = ConsultantImporter(db=db)
        if args.relink:
            _load_all_models()
            n = importer.resolve_cross_document_edges()
            importer.pipeline.repo.commit()
            logger.info(f'RELINK: создано рёбер {n}')
        else:
            only = set(x.strip() for x in args.only_docids.split(',') if x.strip())
            importer.import_all(kinds=args.kind, dry_run=args.dry_run, limit=args.limit,
                                no_phase2=args.no_phase2, update=args.update,
                                only_docids=only or None)
    finally:
        if db is not None:
            db.close()


if __name__ == '__main__':
    main()
