# -*- coding: utf-8 -*-
"""
Graph-RAG Write Tools

Инструменты записи для AI-агента:
- graph_ingest — загрузить документ в граф
- graph_update_node — обновить текст узла (с версионированием)
- graph_archive_node — архивировать узел (soft delete)
- graph_propose_edge — предложить связь (CandidateEdge, не verified!)
- graph_review_candidate — провести ревью кандидата (для юриста)
"""
from __future__ import annotations

import logging
from typing import Any, Optional, Dict

from sqlalchemy.orm import Session

from ..repository import GraphRepository
from ..pipeline import GraphRAGPipeline, IngestionResult
from ..enums import EdgeClass, ExtractedBy

logger = logging.getLogger(__name__)


class GraphWriteTools:
    """
    Write tools для графа.
    КРИТИЧЕСКИ ВАЖНО: LLM не создаёт verified edges напрямую.
    Аналитические связи — только через CandidateEdge.
    """

    def __init__(self, db: Session):
        self.db = db
        self.repo = GraphRepository(db)
        self.pipeline = GraphRAGPipeline(db)

    def ingest_file(
        self,
        file_path: str,
        layer: str = "contract",
        contract_id: Optional[str] = None,
        legal_document_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Загрузить документ в граф.

        Args:
            file_path: Путь к файлу (DOCX, PDF, TXT, HTML)
            layer: Тип документа (contract, npa)
            contract_id: ID связанного Contract (если есть)
            legal_document_id: ID связанного LegalDocument (если есть)

        Returns:
            {document_id, nodes_count, edges_count, entities_count, errors}
        """
        result = self.pipeline.ingest_file(
            file_path=file_path,
            layer=layer,
            contract_id=contract_id,
            legal_document_id=legal_document_id,
        )
        return self._ingestion_to_dict(result)

    def ingest_text(
        self,
        text: str,
        title: str,
        layer: str = "contract",
        contract_id: Optional[str] = None,
        legal_document_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Загрузить текст документа в граф.

        Args:
            text: Текст документа
            title: Название
            layer: Тип (contract, npa)
        """
        result = self.pipeline.ingest_text(
            text=text,
            title=title,
            layer=layer,
            contract_id=contract_id,
            legal_document_id=legal_document_id,
        )
        return self._ingestion_to_dict(result)

    def update_node_text(
        self,
        node_id: str,
        new_text: str,
        reason: str,
        user_id: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Обновить текст узла с созданием новой версии.

        Args:
            node_id: ID узла
            new_text: Новый текст
            reason: Причина изменения
            user_id: ID пользователя (если вручную)

        Returns:
            {node_id, version, old_text_preview, new_text_preview}
        """
        changed_by = "user" if user_id else "agent"
        node = self.repo.nodes.update_text(
            node_id=node_id,
            new_text=new_text,
            reason=reason,
            changed_by=changed_by,
            user_id=user_id,
        )
        if not node:
            return None

        self.repo.commit()

        versions = self.repo.nodes.get_history(node_id)
        return {
            "node_id": node.id,
            "version": len(versions),
            "new_text_preview": new_text[:200],
            "reason": reason,
        }

    def archive_node(
        self,
        node_id: str,
        reason: str,
        user_id: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Архивировать узел (soft delete).
        Физическое удаление ЗАПРЕЩЕНО.

        Args:
            node_id: ID узла
            reason: Причина архивации (обязательно!)
        """
        actor = "user" if user_id else "agent"
        node = self.repo.nodes.archive(
            node_id=node_id,
            reason=reason,
            actor=actor,
            user_id=user_id,
        )
        if not node:
            return None

        self.repo.commit()

        return {
            "node_id": node.id,
            "archived": True,
            "reason": reason,
        }

    def propose_edge(
        self,
        source_id: str,
        target_id: str,
        proposed_type: str,
        proposed_class: str,
        rationale: str,
        evidence: Optional[str] = None,
        confidence: float = 0.5,
    ) -> Dict[str, Any]:
        """
        Предложить связь между узлами (CandidateEdge).

        ВАЖНО: LLM НЕ создаёт verified edges.
        Связь создаётся как кандидат и требует ревью юриста.

        Args:
            source_id: ID узла-источника
            target_id: ID узла-цели
            proposed_type: Тип связи (similar_to_clause, potential_conflict_with_npa...)
            proposed_class: Класс (analytical, risk_signal)
            rationale: Обоснование (ОБЯЗАТЕЛЬНО)
            evidence: Цитата из текста
            confidence: Уверенность (0.0-1.0)
        """
        # Валидация: только analytical и risk_signal
        if proposed_class not in ('analytical', 'risk_signal'):
            return {
                "error": "LLM может предлагать только analytical или risk_signal связи. "
                         "Structural и fact создаются парсером."
            }

        candidate = self.repo.candidates.create(
            source_id=source_id,
            target_id=target_id,
            proposed_type=proposed_type,
            proposed_class=proposed_class,
            rationale=rationale,
            evidence=evidence,
            confidence=min(max(confidence, 0.0), 1.0),
            requires_review=True,
        )

        self.repo.commit()

        return {
            "candidate_id": candidate.id,
            "status": "pending_review",
            "message": "Связь предложена. Требуется ревью юриста.",
        }

    def review_candidate(
        self,
        candidate_id: str,
        result: str,
        reviewer_id: str,
        comment: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Провести ревью кандидата на связь.

        Args:
            candidate_id: ID кандидата
            result: accepted | rejected | modified
            reviewer_id: ID ревьюера (юриста)
            comment: Комментарий
        """
        candidate, edge = self.repo.candidates.review(
            candidate_id=candidate_id,
            result=result,
            reviewer_id=reviewer_id,
            comment=comment,
        )

        if not candidate:
            return {"error": "Candidate not found"}

        self.repo.commit()

        response = {
            "candidate_id": candidate_id,
            "review_result": result,
        }
        if edge:
            response["created_edge_id"] = edge.id
            response["message"] = "Связь принята и создана как verified edge."
        elif result == "rejected":
            response["message"] = "Связь отклонена."

        return response

    @staticmethod
    def _ingestion_to_dict(result: IngestionResult) -> Dict[str, Any]:
        return {
            "document_id": result.document.id if result.document else None,
            "title": result.document.title if result.document else None,
            "nodes_count": result.nodes_count,
            "edges_count": result.edges_count,
            "entities_count": result.entities_count,
            "fact_edges_count": result.fact_edges_count,
            "errors": result.parse_errors,
            "warnings": result.extraction_warnings,
        }
