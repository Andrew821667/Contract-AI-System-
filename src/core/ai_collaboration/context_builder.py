"""
AI Context Builder — сборщик контекста для AI-сессии.

Собирает всю релевантную информацию о документе, findings, комментариях,
workflow state — для передачи в LLM. Реализует IContextBuilder.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session, selectinload, noload

from src.core.base import AIContext
from src.models.analyzer_models import ContractRecommendation, ContractRisk
from src.models.database import Contract, AnalysisResult

# Сколько текста договора уходит в промпт помощника. Хватает на типовой
# договор целиком; у длинного — начало, где предмет, цена, сроки и стороны.
DOCUMENT_TEXT_LIMIT = 24_000


def _plain_text(value: str) -> str:
    """XML/HTML разметку парсера — в читаемый текст с абзацами."""
    import html
    import re

    if "<" not in value:
        return re.sub(r"[ \t]+", " ", value).strip()
    text = re.sub(r"</(?:p|paragraph|clause|section|title|item|li|div|br)\s*>", "\n", value, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n\s*\n+", "\n", text)
    return text.strip()


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

        # Текст договора: без него помощник отвечал типовыми советами и
        # честно писал «в контексте нет текста договора» — на демо это
        # выглядело так, будто система не видит загруженный документ.
        document_text = self._load_document_text(contract)

        # Findings — риски и рекомендации последнего анализа, каждый со
        # своим названием и сутью: раньше сюда попадали только служебные
        # счётчики из AnalysisResult, и в промпте оставались пустые строки.
        findings: list[dict[str, Any]] = []
        if include_findings:
            findings = self._load_findings(document_id)

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
            document_text=document_text,
            document_metadata=doc_metadata,
            user_id=user_id,
            stage=stage,
            findings=findings,
            comments=comments,
            workflow_state=workflow_state,
            prior_actions=prior_actions,
        )

    def _load_document_text(self, contract: Contract) -> str | None:
        """Текст договора для промпта.

        parsed_text при загрузке хранится усечённым (10 000 знаков, для поиска
        основного договора), поэтому файл разбирается заново — парсер отдаёт
        XML, из него оставляем только текст.
        """
        text = ""
        if contract.file_path:
            try:
                from src.services.document_parser import DocumentParser

                text = DocumentParser().parse(contract.file_path) or ""
            except Exception as exc:  # noqa: BLE001 — помощник должен работать и без текста
                from loguru import logger

                logger.warning(f"AI context: не удалось разобрать файл договора {contract.id}: {exc}")
        if not text.strip():
            text = contract.parsed_text or ""
        text = _plain_text(text)
        if not text:
            return None
        if len(text) > DOCUMENT_TEXT_LIMIT:
            return text[:DOCUMENT_TEXT_LIMIT] + "\n…[текст договора обрезан для контекста]"
        return text

    def _load_findings(self, document_id: str) -> list[dict[str, Any]]:
        latest = (
            self.db.query(AnalysisResult)
            .filter(AnalysisResult.contract_id == document_id)
            .order_by(AnalysisResult.created_at.desc())
            .first()
        )
        if not latest:
            return []
        findings: list[dict[str, Any]] = []
        severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        risks = (
            self.db.query(ContractRisk)
            .filter(ContractRisk.analysis_id == latest.id)
            .all()
        )
        for risk in sorted(risks, key=lambda r: severity_order.get((r.severity or "").lower(), 9)):
            findings.append(
                {
                    "id": f"risk:{risk.id}",
                    "kind": "risk",
                    "severity": risk.severity,
                    "title": risk.title,
                    "description": risk.description,
                    "section": risk.section_name,
                }
            )
        recommendations = (
            self.db.query(ContractRecommendation)
            .filter(ContractRecommendation.analysis_id == latest.id)
            .all()
        )
        priority_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        for rec in sorted(recommendations, key=lambda r: priority_order.get((r.priority or "").lower(), 9)):
            findings.append(
                {
                    "id": f"recommendation:{rec.id}",
                    "kind": "recommendation",
                    "severity": rec.priority,
                    "title": rec.title,
                    "description": rec.description,
                }
            )
        return findings

    def _load_comments(self, document_id: str) -> list[dict[str, Any]]:
        """Загрузить комментарии к документу."""
        from src.core.collaboration.models import Comment

        comments = (
            self.db.query(Comment)
            .options(
                selectinload(Comment.mentions),
                noload(Comment.replies),
                noload(Comment.assignment),
            )
            .filter(Comment.document_id == document_id)
            .order_by(Comment.created_at.desc())
            .limit(30)
            .all()
        )
        return [
            {
                "id": c.id,
                "author_id": c.author_id,
                "content": c.content,
                "anchor_type": c.anchor_type,
                "anchor_id": c.anchor_id,
                "created_at": c.created_at.isoformat() if c.created_at else None,
            }
            for c in comments
        ]

    def _load_workflow_state(self, document_id: str) -> dict[str, Any]:
        """Загрузить состояние workflow."""
        from src.core.workflow.models import WorkflowExecution, WorkflowTask

        execution = (
            self.db.query(WorkflowExecution)
            .filter(WorkflowExecution.document_id == document_id)
            .order_by(WorkflowExecution.started_at.desc())
            .first()
        )
        if not execution:
            return {}

        tasks = (
            self.db.query(WorkflowTask)
            .filter(WorkflowTask.execution_id == execution.id)
            .order_by(WorkflowTask.step_order)
            .all()
        )
        return {
            "execution_id": execution.id,
            "status": execution.status,
            "current_step": execution.current_step,
            "tasks": [
                {"id": t.id, "name": t.step_name, "status": t.status, "assignee_id": t.assignee_id}
                for t in tasks
            ],
        }

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
