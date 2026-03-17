"""
AI Collaborator Service — основной сервис AI-сессий.

Создаёт сессии, обрабатывает сообщения, координирует LLM-вызовы,
парсит действия из ответов, управляет lifecycle сессии.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from loguru import logger
from sqlalchemy.orm import Session

from src.core.base import AIContext
from src.core.interfaces import IAuditLogger, ILLMRouter
from .action_parser import AIActionParserService
from .context_builder import AIContextBuilderService
from .models import AIAction, AIAuditRecord, AIConversationTurn, AISession


class AICollaboratorService:
    """Основной сервис AI-коллаборации."""

    def __init__(
        self,
        db: Session,
        llm_router: ILLMRouter,
        context_builder: AIContextBuilderService,
        action_parser: AIActionParserService,
        audit_logger: IAuditLogger,
    ) -> None:
        self.db = db
        self.llm_router = llm_router
        self.context_builder = context_builder
        self.action_parser = action_parser
        self.audit_logger = audit_logger

    async def create_session(
        self,
        document_id: str,
        user_id: str,
        stage: str = "intake",
        organization_id: str | None = None,
    ) -> AISession:
        """Создать AI-сессию для документа."""
        session = AISession(
            document_id=document_id,
            user_id=user_id,
            organization_id=organization_id,
            stage=stage,
            status="active",
        )
        self.db.add(session)
        self.db.flush()

        # Audit
        await self.audit_logger.log(
            actor=f"user:{user_id}",
            action="session.create",
            target=document_id,
            payload={"stage": stage, "session_id": session.id},
            result="success",
            session_id=session.id,
        )

        logger.info(f"AI session created: {session.id} (doc={document_id}, stage={stage})")
        return session

    async def send_message(
        self,
        session_id: str,
        user_message: str,
        user_id: str,
    ) -> dict[str, Any]:
        """
        Отправить сообщение в AI-сессию.

        Returns:
            {"turn": AIConversationTurn, "actions": [AIAction, ...]}
        """
        session = self.db.query(AISession).filter(AISession.id == session_id).first()
        if not session:
            raise ValueError(f"Сессия {session_id} не найдена")
        if session.status != "active":
            raise ValueError(f"Сессия {session_id} не активна (status={session.status})")

        # 1. Сохранить сообщение пользователя
        user_turn = AIConversationTurn(
            session_id=session_id,
            role="user",
            content=user_message,
        )
        self.db.add(user_turn)
        self.db.flush()

        # 2. Собрать контекст
        ai_context: AIContext = await self.context_builder.build(
            document_id=session.document_id,
            user_id=user_id,
            stage=session.stage,
        )

        # 3. Выбрать LLM
        llm_profile = await self.llm_router.route(
            task_type=f"collaboration.{session.stage}",
            sensitivity="normal",
        )

        # 4. Собрать историю диалога
        history = (
            self.db.query(AIConversationTurn)
            .filter(AIConversationTurn.session_id == session_id)
            .order_by(AIConversationTurn.created_at)
            .all()
        )

        # 5. Вызвать LLM (абстрактно — конкретная реализация через adapter)
        llm_response = await self._call_llm(
            history=history,
            context=ai_context,
            llm_profile=llm_profile,
        )

        # 6. Сохранить ответ
        assistant_turn = AIConversationTurn(
            session_id=session_id,
            role="assistant",
            content=llm_response["content"],
            model_used=llm_profile.model,
            tokens_input=llm_response.get("tokens_input", 0),
            tokens_output=llm_response.get("tokens_output", 0),
        )
        self.db.add(assistant_turn)

        # 7. Парсить actions из ответа
        actions = self.action_parser.parse_actions(session_id, llm_response["content"])

        # 8. Обновить метрики сессии
        session.total_turns += 2  # user + assistant
        session.total_actions += len(actions)
        session.total_tokens_used += llm_response.get("tokens_input", 0) + llm_response.get("tokens_output", 0)
        session.updated_at = datetime.now(timezone.utc)

        self.db.flush()

        # 9. Audit
        self._record_audit(session, "llm_call", {
            "model": llm_profile.model,
            "tokens_input": llm_response.get("tokens_input", 0),
            "tokens_output": llm_response.get("tokens_output", 0),
            "actions_parsed": len(actions),
        })

        return {
            "turn": assistant_turn,
            "actions": actions,
        }

    async def close_session(self, session_id: str, user_id: str) -> AISession | None:
        """Закрыть AI-сессию."""
        session = self.db.query(AISession).filter(AISession.id == session_id).first()
        if not session:
            return None

        session.status = "closed"
        session.closed_at = datetime.now(timezone.utc)
        self.db.flush()

        await self.audit_logger.log(
            actor=f"user:{user_id}",
            action="session.close",
            target=session.document_id,
            payload={"session_id": session_id},
            result="success",
            session_id=session_id,
        )

        return session

    async def get_session_history(self, session_id: str) -> list[AIConversationTurn]:
        """Получить историю диалога сессии."""
        return (
            self.db.query(AIConversationTurn)
            .filter(AIConversationTurn.session_id == session_id)
            .order_by(AIConversationTurn.created_at)
            .all()
        )

    async def _call_llm(
        self,
        history: list[AIConversationTurn],
        context: AIContext,
        llm_profile: Any,
    ) -> dict[str, Any]:
        """
        Вызов LLM через self.llm_router (LLMRouterAdapter).

        Собирает system prompt из AIContext, формирует messages из истории,
        вызывает LLM и возвращает результат.
        """
        system_prompt = self._build_system_prompt(context)
        messages = [{"role": t.role, "content": t.content} for t in history]

        result = await self.llm_router.call(messages, llm_profile, system_prompt=system_prompt)
        return result

    def _build_system_prompt(self, context: AIContext) -> str:
        """
        Построить системный промпт из AIContext.

        Включает: метаданные документа, стадию, роль пользователя,
        топ-5 findings, состояние workflow, инструкцию по формату actions.
        """
        parts: list[str] = []

        # Метаданные документа
        parts.append("# Контекст документа")
        parts.append(f"- Document ID: {context.document_id}")
        if context.document_type:
            parts.append(f"- Тип документа: {context.document_type}")
        if context.document_metadata:
            meta_items = ", ".join(f"{k}: {v}" for k, v in context.document_metadata.items())
            parts.append(f"- Метаданные: {meta_items}")

        # Стадия и роль
        parts.append(f"\n# Стадия: {context.stage}")
        if context.user_role:
            parts.append(f"# Роль пользователя: {context.user_role}")

        # Findings (топ 5)
        if context.findings:
            parts.append("\n# Findings (топ 5)")
            for finding in context.findings[:5]:
                severity = finding.get("severity", "info")
                title = finding.get("title", finding.get("description", "—"))
                parts.append(f"- [{severity}] {title}")

        # Workflow state
        if context.workflow_state:
            parts.append("\n# Состояние workflow")
            for key, value in context.workflow_state.items():
                parts.append(f"- {key}: {value}")

        # Инструкция по actions
        parts.append("\n# Формат действий")
        parts.append(
            "Если нужно предложить действие, выведи его в блоке:\n"
            "```action\n"
            '{"action_type": "<тип>", "target_entity_type": "finding|clause|document", '
            '"target_entity_id": "<id>", "payload": {...}, "rationale": "<причина>", "confidence": 0.85}\n'
            "```\n"
            "Доступные action_type: explain_finding, suggest_clause, modify_clause, "
            "create_comment_draft, suggest_risk_mitigation, create_summary, "
            "compare_versions, translate_clause, answer_question, "
            "draft_negotiation_response, analyze_risks, extract_clauses, "
            "search_knowledge, generate_contract"
        )

        # Язык
        parts.append("\n# Язык\nОтвечай на русском языке.")

        return "\n".join(parts)

    def _record_audit(self, session: AISession, event_type: str, details: dict[str, Any]) -> None:
        record = AIAuditRecord(
            session_id=session.id,
            actor=f"user:{session.user_id}",
            event_type=event_type,
            details=details,
        )
        self.db.add(record)
        self.db.flush()
