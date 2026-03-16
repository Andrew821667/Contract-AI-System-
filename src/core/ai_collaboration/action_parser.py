"""
AI Action Parser — парсинг действий из ответа LLM.

LLM возвращает текст с возможными действиями (structured output).
ActionParser извлекает их и создаёт AIAction записи.
"""

from __future__ import annotations

import json
import re
from typing import Any

from loguru import logger
from sqlalchemy.orm import Session

from .models import AIAction


# Паттерн для structured action blocks в ответе LLM
# Формат: ```action\n{...json...}\n```
_ACTION_BLOCK_RE = re.compile(
    r"```action\s*\n(.*?)\n```",
    re.DOTALL,
)


class AIActionParserService:
    """Парсер действий из LLM-ответа."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def parse_actions(self, session_id: str, llm_response: str) -> list[AIAction]:
        """
        Извлечь действия из текста ответа LLM.

        LLM должен возвращать действия в формате:
        ```action
        {
            "action_type": "suggest_clause",
            "target_entity_type": "clause",
            "target_entity_id": "...",
            "payload": {...},
            "rationale": "...",
            "confidence": 0.85
        }
        ```
        """
        blocks = _ACTION_BLOCK_RE.findall(llm_response)
        actions: list[AIAction] = []

        for block in blocks:
            try:
                data = json.loads(block)
                action = self._create_action(session_id, data)
                if action:
                    actions.append(action)
            except json.JSONDecodeError as e:
                logger.warning(f"Не удалось распарсить action block: {e}")
                continue

        return actions

    def create_action_directly(
        self,
        session_id: str,
        action_type: str,
        payload: dict[str, Any] | None = None,
        rationale: str | None = None,
        confidence: float = 0.0,
        target_entity_type: str | None = None,
        target_entity_id: str | None = None,
        approval_required: bool = True,
    ) -> AIAction:
        """Создать действие программно (не из LLM-ответа)."""
        action = AIAction(
            session_id=session_id,
            action_type=action_type,
            target_entity_type=target_entity_type,
            target_entity_id=target_entity_id,
            payload=payload,
            rationale=rationale,
            confidence=confidence,
            approval_required=approval_required,
            execution_status="pending",
        )
        self.db.add(action)
        self.db.flush()
        return action

    def _create_action(self, session_id: str, data: dict[str, Any]) -> AIAction | None:
        """Создать AIAction из распарсенного JSON."""
        action_type = data.get("action_type")
        if not action_type:
            logger.warning("Action block без action_type — пропускаем")
            return None

        confidence = float(data.get("confidence", 0.0))
        # Определяем, нужно ли одобрение
        always_approve_types = {
            "modify_clause", "generate_contract", "assign_reviewer",
            "change_workflow_status", "send_notification",
        }
        if action_type in always_approve_types:
            approval_required = True
        else:
            # Auto-approve если confidence >= 0.9
            approval_required = confidence < 0.9

        action = AIAction(
            session_id=session_id,
            action_type=action_type,
            target_entity_type=data.get("target_entity_type"),
            target_entity_id=data.get("target_entity_id"),
            payload=data.get("payload"),
            rationale=data.get("rationale"),
            confidence=confidence,
            approval_required=approval_required,
            execution_status="pending",
        )
        self.db.add(action)
        self.db.flush()

        logger.info(f"Parsed AI action: {action_type} (conf={confidence}, approval={'required' if approval_required else 'auto'})")
        return action
