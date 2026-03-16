"""
AI Context Builder — сборщик контекста для AI-сессии.

Собирает всю релевантную информацию о документе, findings, комментариях,
workflow state — для передачи в LLM. Реализует IContextBuilder.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from src.core.base import AIContext
from src.models.database import Contract, AnalysisResult


class AIContextBuilderService:
    """Сборщик контекста для AI."""

    def __init__(self, db: Session) -> None:
        self.db = db

    async def build(
        self,
        document_id: str,
        user_id: str,
        stage: str,
        include_findings: bool = True,
        include_comments: bool = True,
        include_workflow: bool = True,
        include_prior_actions: bool = True,
    ) -> AIContext:
        """Собрать контекст для AI-сессии."""

        # Базовая информация о документе
        contract = self.db.query(Contract).filter(Contract.id == document_id).first()
        if not contract:
            return AIContext(
                document_id=document_id,
                user_id=user_id,
                stage=stage,
            )

        doc_metadata: dict[str, Any] = {
            "file_name": contract.file_name,
            "contract_type": contract.contract_type,
            "status": contract.status,
            "risk_level": contract.risk_level,
        }

        # Findings (результаты анализа)
        findings: list[dict[str, Any]] = []
        if include_findings:
            results = (
                self.db.query(AnalysisResult)
                .filter(AnalysisResult.contract_id == document_id)
                .order_by(AnalysisResult.created_at.desc())
                .limit(5)
                .all()
            )
            for r in results:
                finding: dict[str, Any] = {"id": r.id, "version": r.version}
                if r.compliance_issues:
                    finding["compliance_issues"] = r.compliance_issues
                if r.legal_issues:
                    finding["legal_issues"] = r.legal_issues
                if r.risks_by_category:
                    finding["risks_by_category"] = r.risks_by_category
                if r.recommendations:
                    finding["recommendations"] = r.recommendations
                findings.append(finding)

        # Комментарии (из collaboration модуля — пока пустой список)
        comments: list[dict[str, Any]] = []
        if include_comments:
            comments = self._load_comments(document_id)

        # Workflow state
        workflow_state: dict[str, Any] = {}
        if include_workflow:
            workflow_state = self._load_workflow_state(document_id)

        # Prior AI actions
        prior_actions: list[dict[str, Any]] = []
        if include_prior_actions:
            prior_actions = self._load_prior_actions(document_id, user_id)

        return AIContext(
            document_id=document_id,
            document_type=contract.document_type,
            document_metadata=doc_metadata,
            user_id=user_id,
            stage=stage,
            findings=findings,
            comments=comments,
            workflow_state=workflow_state,
            prior_actions=prior_actions,
        )

    def _load_comments(self, document_id: str) -> list[dict[str, Any]]:
        """Загрузить комментарии к документу (когда модуль collaboration будет готов)."""
        # TODO: подключить Comment модель из collaboration
        from .models import AIAction, AISession

        # Пока: загружаем AI-actions типа create_comment_draft как «комментарии»
        sessions = (
            self.db.query(AISession)
            .filter(AISession.document_id == document_id)
            .all()
        )
        session_ids = [s.id for s in sessions]
        if not session_ids:
            return []

        actions = (
            self.db.query(AIAction)
            .filter(
                AIAction.session_id.in_(session_ids),
                AIAction.action_type == "create_comment_draft",
                AIAction.execution_status == "executed",
            )
            .order_by(AIAction.created_at.desc())
            .limit(20)
            .all()
        )

        return [
            {
                "id": a.id,
                "type": a.action_type,
                "payload": a.payload,
                "created_at": a.created_at.isoformat() if a.created_at else None,
            }
            for a in actions
        ]

    def _load_workflow_state(self, document_id: str) -> dict[str, Any]:
        """Загрузить состояние workflow (когда модуль workflow будет готов)."""
        # TODO: подключить WorkflowExecution из workflow модуля
        return {}

    def _load_prior_actions(self, document_id: str, user_id: str) -> list[dict[str, Any]]:
        """Загрузить предыдущие AI-действия для контекста."""
        from .models import AIAction, AISession

        sessions = (
            self.db.query(AISession)
            .filter(
                AISession.document_id == document_id,
                AISession.user_id == user_id,
            )
            .all()
        )
        session_ids = [s.id for s in sessions]
        if not session_ids:
            return []

        actions = (
            self.db.query(AIAction)
            .filter(AIAction.session_id.in_(session_ids))
            .order_by(AIAction.created_at.desc())
            .limit(30)
            .all()
        )

        return [
            {
                "id": a.id,
                "type": a.action_type,
                "status": a.execution_status,
                "confidence": a.confidence,
                "created_at": a.created_at.isoformat() if a.created_at else None,
            }
            for a in actions
        ]
