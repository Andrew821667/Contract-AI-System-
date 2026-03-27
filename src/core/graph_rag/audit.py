# -*- coding: utf-8 -*-
"""
Graph-RAG Audit

Вспомогательные функции для работы с audit log графа.
Основная логика аудита встроена в repository.py (_audit).
Этот модуль предоставляет удобный интерфейс для чтения логов.
"""
from __future__ import annotations

from datetime import datetime, timezone, timedelta
from typing import List, Optional, Dict, Any

from sqlalchemy import func, desc
from sqlalchemy.orm import Session

from .models import RAGAuditLog
from .enums import AuditAction


class GraphAuditService:
    """
    Сервис для чтения и анализа audit log графа.

    Использование:
        audit = GraphAuditService(db)
        logs = audit.get_entity_history("graph_node", node_id)
        recent = audit.get_recent(hours=24)
    """

    def __init__(self, db: Session):
        self.db = db

    def get_entity_history(
        self,
        entity_type: str,
        entity_id: str,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """
        История изменений конкретной сущности.

        Args:
            entity_type: graph_node, graph_edge, candidate_edge, graph_document
            entity_id: ID сущности
        """
        logs = (self.db.query(RAGAuditLog)
                .filter(
                    RAGAuditLog.entity_type == entity_type,
                    RAGAuditLog.entity_id == entity_id,
                )
                .order_by(desc(RAGAuditLog.created_at))
                .limit(limit)
                .all())

        return [self._log_to_dict(log) for log in logs]

    def get_recent(
        self,
        hours: int = 24,
        actions: Optional[List[str]] = None,
        actor: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """
        Недавние записи аудита.

        Args:
            hours: За последние N часов
            actions: Фильтр по типам действий
            actor: Фильтр по актору (user, agent, system, parser)
        """
        since = datetime.now(timezone.utc) - timedelta(hours=hours)

        q = (self.db.query(RAGAuditLog)
             .filter(RAGAuditLog.created_at >= since))

        if actions:
            q = q.filter(RAGAuditLog.action.in_(actions))
        if actor:
            q = q.filter(RAGAuditLog.actor == actor)

        logs = q.order_by(desc(RAGAuditLog.created_at)).limit(limit).all()

        return [self._log_to_dict(log) for log in logs]

    def get_stats(self, hours: int = 24) -> Dict[str, Any]:
        """Статистика аудита за период."""
        since = datetime.now(timezone.utc) - timedelta(hours=hours)

        total = (self.db.query(func.count(RAGAuditLog.id))
                 .filter(RAGAuditLog.created_at >= since)
                 .scalar())

        by_action = dict(
            self.db.query(RAGAuditLog.action, func.count(RAGAuditLog.id))
            .filter(RAGAuditLog.created_at >= since)
            .group_by(RAGAuditLog.action)
            .all()
        )

        by_actor = dict(
            self.db.query(RAGAuditLog.actor, func.count(RAGAuditLog.id))
            .filter(RAGAuditLog.created_at >= since)
            .group_by(RAGAuditLog.actor)
            .all()
        )

        return {
            "period_hours": hours,
            "total": total,
            "by_action": by_action,
            "by_actor": by_actor,
        }

    @staticmethod
    def _log_to_dict(log: RAGAuditLog) -> Dict[str, Any]:
        return {
            "id": log.id,
            "action": log.action,
            "entity_type": log.entity_type,
            "entity_id": log.entity_id,
            "actor": log.actor,
            "user_id": log.user_id,
            "changes": log.changes,
            "reason": log.reason,
            "context": log.context,
            "created_at": log.created_at.isoformat() if log.created_at else None,
        }
