# -*- coding: utf-8 -*-
"""
Graph-RAG Analyze Tools

Аналитические инструменты для AI-агента:
- graph_stats — статистика документа/графа
- graph_compare — сравнить два узла/документа
- graph_find_references — найти все ссылки на НПА в документе
- graph_entity_summary — сводка сущностей документа (суммы, даты, нормы)
"""
from __future__ import annotations

import json
import logging
import threading
import time
from collections import Counter
from pathlib import Path
from typing import Any, Optional, List, Dict

from sqlalchemy import func
from sqlalchemy.orm import Session

from ..models import GraphDocument, GraphNode, GraphEdge, GraphEntity, CandidateEdge
from ..repository import GraphRepository

logger = logging.getLogger(__name__)

# ── Кеш глобальной статистики графа ─────────────────────────────────────────
# Четыре COUNT(*) по таблицам графа на проде занимают ~28с (узлы 16.9с, связи
# 7.2с, сущности 3.8с — 300 тыс./865 тыс./694 тыс. строк), при таймауте фронта
# 30с. Замер стабилен между прогонами, то есть панель Graph-RAG работала в двух
# секундах от обрыва: любая параллельная нагрузка — и вкладка показывает пустоту.
# Индекс по is_archived есть и используется, дело в объёме перебора.
# Подставить предрассчитанные graph_documents.nodes_count/edges_count нельзя:
# по узлам сумма сходится точно (303590), а по связям занижает (763418 против
# 865220) — счётчик рёбер неполный. Поэтому считаем честно, но фоном.
_GRAPH_STATS_TTL = 15 * 60.0            # пересчёт не чаще раза в 15 минут
_GRAPH_STATS_FILE = Path("data/graph_stats.json")
_graph_stats: Optional[Dict[str, Any]] = None
_graph_stats_at: float = 0.0
_graph_stats_lock = threading.Lock()
_graph_stats_running = False


def _load_graph_stats() -> None:
    """Поднять кеш с диска — иначе после каждого рестарта первый заход снова ждёт 28с."""
    global _graph_stats, _graph_stats_at
    try:
        raw = json.loads(_GRAPH_STATS_FILE.read_text(encoding="utf-8"))
        _graph_stats = raw.get("stats")
        _graph_stats_at = float(raw.get("computed_at") or 0.0)
    except (OSError, ValueError, TypeError) as e:
        logger.debug(f"Graph-stats кеш не поднят с диска: {e}")


def _save_graph_stats(stats: Dict[str, Any], computed_at: float) -> None:
    try:
        _GRAPH_STATS_FILE.parent.mkdir(parents=True, exist_ok=True)
        _GRAPH_STATS_FILE.write_text(
            json.dumps({"stats": stats, "computed_at": computed_at}, ensure_ascii=False),
            encoding="utf-8",
        )
    except OSError as e:
        logger.warning(f"Не удалось сохранить graph-stats кеш: {e}")


def _compute_global_stats(db: Session) -> Dict[str, Any]:
    """Честный пересчёт. Дорого (~28с на проде) — звать только фоном."""
    docs_count = db.query(func.count(GraphDocument.id)).scalar()
    nodes_count = db.query(func.count(GraphNode.id)).filter(
        GraphNode.is_archived == False
    ).scalar()
    edges_count = db.query(func.count(GraphEdge.id)).scalar()
    entities_count = db.query(func.count(GraphEntity.id)).scalar()

    by_layer = dict(
        db.query(GraphDocument.layer, func.count(GraphDocument.id))
        .group_by(GraphDocument.layer)
        .all()
    )

    return {
        "documents_total": docs_count,
        "nodes_total": nodes_count,
        "edges_total": edges_count,
        "entities_total": entities_count,
        "by_layer": by_layer,
    }


def _refresh_graph_stats() -> None:
    """Фоновый пересчёт со своей сессией: сессия запроса к этому моменту закрыта."""
    global _graph_stats, _graph_stats_at, _graph_stats_running
    from src.models.database import SessionLocal

    db = SessionLocal()
    try:
        stats = _compute_global_stats(db)
        now = time.time()
        with _graph_stats_lock:
            _graph_stats = stats
            _graph_stats_at = now
        _save_graph_stats(stats, now)
        logger.info(
            "Graph-stats обновлён: документов=%s узлов=%s связей=%s сущностей=%s",
            stats.get("documents_total"), stats.get("nodes_total"),
            stats.get("edges_total"), stats.get("entities_total"),
        )
    except Exception as e:
        logger.warning(f"Фоновый пересчёт graph-stats не удался: {e}")
    finally:
        db.close()
        with _graph_stats_lock:
            _graph_stats_running = False


def _graph_stats_fresh() -> bool:
    return _graph_stats is not None and (time.time() - _graph_stats_at) < _GRAPH_STATS_TTL


def _ensure_graph_stats_fresh() -> None:
    """Запустить фоновый пересчёт, если кеш протух. Запрос не блокирует."""
    global _graph_stats_running
    with _graph_stats_lock:
        if _graph_stats_running:
            return
        fresh = _graph_stats_fresh()
    # Файл мог обновиться уже после импорта — например, кеш прогрели при деплое.
    if not fresh:
        _load_graph_stats()
        with _graph_stats_lock:
            fresh = _graph_stats_fresh()
    if fresh:
        return
    with _graph_stats_lock:
        if _graph_stats_running:
            return
        _graph_stats_running = True
    threading.Thread(target=_refresh_graph_stats, name="graph-stats", daemon=True).start()


_load_graph_stats()


class GraphAnalyzeTools:
    """
    Аналитические tools для графа.
    Read-only: не изменяют данные.
    """

    def __init__(self, db: Session):
        self.db = db
        self.repo = GraphRepository(db)

    def stats(self, document_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Статистика графа или конкретного документа.

        Returns:
            {documents, nodes_total, edges_total, entities_total, by_layer, by_node_type}
        """
        if document_id:
            return self._document_stats(document_id)
        return self._global_stats()

    def entity_summary(
        self,
        document_id: str,
    ) -> Dict[str, Any]:
        """
        Сводка сущностей документа: суммы, даты, ссылки на нормы.

        Returns:
            {monetary: [...], dates: [...], norm_refs: [...], clause_types: [...]}
        """
        nodes = self.repo.nodes.get_by_document(document_id)
        node_ids = [n.id for n in nodes]

        if not node_ids:
            return {"error": "Document not found or empty"}

        entities = (self.db.query(GraphEntity)
                    .filter(GraphEntity.node_id.in_(node_ids))
                    .all())

        result = {
            "monetary": [],
            "dates": [],
            "norm_refs": [],
            "clause_types": [],
            "contract_types": [],
        }

        for e in entities:
            entry = {
                "value": e.entity_value,
                "raw_text": e.raw_text,
                "node_id": e.node_id,
                "confidence": e.confidence,
            }

            if e.entity_type == 'monetary':
                entry["amount"] = e.amount
                entry["currency"] = e.currency
                result["monetary"].append(entry)
            elif e.entity_type == 'date_ref':
                entry["date"] = e.date_value.isoformat() if e.date_value else None
                entry["date_type"] = e.date_type
                result["dates"].append(entry)
            elif e.entity_type == 'norm_ref':
                entry["norm_code"] = e.norm_code
                entry["article"] = e.norm_article
                result["norm_refs"].append(entry)
            elif e.entity_type == 'clause_type':
                result["clause_types"].append(entry)
            elif e.entity_type == 'contract_type':
                result["contract_types"].append(entry)

        return result

    def find_norm_references(
        self,
        document_id: str,
        norm_code: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Найти все ссылки на НПА в документе.

        Args:
            document_id: ID документа
            norm_code: Фильтр по коду НПА (например, "ГК РФ")
        """
        nodes = self.repo.nodes.get_by_document(document_id)
        node_ids = [n.id for n in nodes]
        node_map = {n.id: n for n in nodes}

        q = (self.db.query(GraphEntity)
             .filter(
                 GraphEntity.node_id.in_(node_ids),
                 GraphEntity.entity_type == 'norm_ref',
             ))

        if norm_code:
            q = q.filter(GraphEntity.norm_code.ilike(f"%{norm_code}%"))

        entities = q.all()

        references = []
        for e in entities:
            node = node_map.get(e.node_id)
            references.append({
                "norm_code": e.norm_code,
                "article": e.norm_article,
                "part": e.norm_part,
                "raw_text": e.raw_text,
                "node_number": node.number if node else None,
                "node_text_preview": node.text[:100] if node else None,
            })

        # Группировка по НПА
        by_npa = Counter(e.norm_code for e in entities if e.norm_code)

        return {
            "references": references,
            "count": len(references),
            "by_npa": dict(by_npa.most_common()),
        }

    def pending_reviews(self, limit: int = 20) -> Dict[str, Any]:
        """Список кандидатов, ожидающих ревью."""
        candidates = self.repo.candidates.get_pending(limit=limit)

        return {
            "candidates": [
                {
                    "id": c.id,
                    "source_id": c.source_id,
                    "target_id": c.target_id,
                    "proposed_type": c.proposed_type,
                    "proposed_class": c.proposed_class,
                    "rationale": c.rationale,
                    "confidence": c.confidence,
                    "created_at": c.created_at.isoformat() if c.created_at else None,
                }
                for c in candidates
            ],
            "count": len(candidates),
        }

    def compare_nodes(
        self,
        node_id_a: str,
        node_id_b: str,
    ) -> Optional[Dict[str, Any]]:
        """
        Сравнить два узла: текст, сущности, ссылки.
        Полезно для сравнения пунктов из разных договоров.
        """
        node_a = self.repo.nodes.get_by_id(node_id_a)
        node_b = self.repo.nodes.get_by_id(node_id_b)

        if not node_a or not node_b:
            return None

        entities_a = self.repo.entities.get_by_node(node_id_a)
        entities_b = self.repo.entities.get_by_node(node_id_b)

        return {
            "node_a": {
                "id": node_a.id,
                "number": node_a.number,
                "type": node_a.node_type,
                "text": node_a.text,
                "document_id": node_a.document_id,
                "entities": [{"type": e.entity_type, "value": e.entity_value} for e in entities_a],
            },
            "node_b": {
                "id": node_b.id,
                "number": node_b.number,
                "type": node_b.node_type,
                "text": node_b.text,
                "document_id": node_b.document_id,
                "entities": [{"type": e.entity_type, "value": e.entity_value} for e in entities_b],
            },
            "same_type": node_a.node_type == node_b.node_type,
            "same_document": node_a.document_id == node_b.document_id,
        }

    # ──────────────────────────────────────────
    # Private
    # ──────────────────────────────────────────

    def _document_stats(self, document_id: str) -> Dict[str, Any]:
        doc = self.repo.documents.get_by_id(document_id)
        if not doc:
            return {"error": "Document not found"}

        nodes = self.repo.nodes.get_by_document(document_id)
        node_types = Counter(n.node_type for n in nodes)

        node_ids = [n.id for n in nodes]
        entities_count = (self.db.query(func.count(GraphEntity.id))
                          .filter(GraphEntity.node_id.in_(node_ids))
                          .scalar()) if node_ids else 0

        candidates_count = (self.db.query(func.count(CandidateEdge.id))
                            .filter(
                                CandidateEdge.source_id.in_(node_ids),
                                CandidateEdge.reviewed == False,
                            )
                            .scalar()) if node_ids else 0

        return {
            "document_id": doc.id,
            "title": doc.title,
            "layer": doc.layer,
            "status": doc.status,
            "nodes_count": doc.nodes_count,
            "edges_count": doc.edges_count,
            "entities_count": entities_count,
            "pending_candidates": candidates_count,
            "by_node_type": dict(node_types),
        }

    def _global_stats(self) -> Dict[str, Any]:
        """Глобальная статистика: отдаём из кеша, пересчитываем фоном.

        Синхронный расчёт остаётся запасным путём — он отрабатывает только на
        пустом кеше (свежая инсталляция), где граф мал и считается мгновенно.
        На больших графах кеш прогревается заранее и этот путь не используется.
        """
        _ensure_graph_stats_fresh()
        with _graph_stats_lock:
            cached = _graph_stats
        if cached is not None:
            return cached
        return _compute_global_stats(self.db)
