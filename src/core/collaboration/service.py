"""
Collaboration — CommentService.

Создание комментариев, ответов, упоминаний, назначений.
"""

from __future__ import annotations

from datetime import datetime
import re
from typing import Any

from loguru import logger
from sqlalchemy.orm import Session

from .models import Comment, CommentAssignment, CommentThread, Mention


# Паттерн @username в комментарии
_MENTION_RE = re.compile(r"@(\S+)")


class CommentService:
    """Сервис комментариев."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def create_comment(
        self,
        document_id: str,
        author_id: str,
        content: str,
        anchor_type: str = "document",
        anchor_id: str | None = None,
        parent_comment_id: str | None = None,
        is_ai_generated: bool = False,
    ) -> Comment:
        """Создать комментарий."""
        comment = Comment(
            document_id=document_id,
            author_id=author_id,
            content=content,
            anchor_type=anchor_type,
            anchor_id=anchor_id,
            parent_comment_id=parent_comment_id,
            is_ai_generated=is_ai_generated,
            status="active",
        )
        self.db.add(comment)
        self.db.flush()

        # Если корневой комментарий — создаём thread
        if not parent_comment_id:
            thread = CommentThread(
                document_id=document_id,
                root_comment_id=comment.id,
                status="open",
            )
            self.db.add(thread)

        # Парсим @mentions
        self._process_mentions(comment)

        self.db.flush()
        logger.info(f"Comment created: {comment.id} (doc={document_id}, anchor={anchor_type})")
        return comment

    def reply(self, parent_comment_id: str, author_id: str, content: str) -> Comment:
        """Ответить на комментарий."""
        parent = self.db.query(Comment).filter(Comment.id == parent_comment_id).first()
        if not parent:
            raise ValueError(f"Комментарий {parent_comment_id} не найден")

        return self.create_comment(
            document_id=parent.document_id,
            author_id=author_id,
            content=content,
            anchor_type=parent.anchor_type,
            anchor_id=parent.anchor_id,
            parent_comment_id=parent_comment_id,
        )

    def resolve_comment(self, comment_id: str, user_id: str) -> Comment | None:
        """Закрыть комментарий (resolve)."""
        comment = self.db.query(Comment).filter(Comment.id == comment_id).first()
        if not comment:
            return None

        comment.status = "resolved"
        comment.updated_at = datetime.utcnow()

        # Закрыть thread если есть
        thread = self.db.query(CommentThread).filter(
            CommentThread.root_comment_id == comment_id
        ).first()
        if thread:
            thread.status = "resolved"
            thread.resolved_by = user_id
            thread.resolved_at = datetime.utcnow()

        self.db.flush()
        return comment

    def assign_comment(self, comment_id: str, assignee_id: str) -> CommentAssignment:
        """Назначить комментарий на ответственного."""
        assignment = CommentAssignment(
            comment_id=comment_id,
            assignee_id=assignee_id,
            status="pending",
        )
        self.db.add(assignment)
        self.db.flush()
        return assignment

    def get_document_comments(
        self,
        document_id: str,
        anchor_type: str | None = None,
        include_resolved: bool = False,
    ) -> list[Comment]:
        """Комментарии к документу."""
        query = self.db.query(Comment).filter(Comment.document_id == document_id)
        if anchor_type:
            query = query.filter(Comment.anchor_type == anchor_type)
        if not include_resolved:
            query = query.filter(Comment.status == "active")
        return query.order_by(Comment.created_at).all()

    def _process_mentions(self, comment: Comment) -> None:
        """Извлечь @mentions из текста и создать записи."""
        matches = _MENTION_RE.findall(comment.content)
        # Дедупликация
        seen: set[str] = set()
        for username in matches:
            if username in seen:
                continue
            seen.add(username)
            # TODO: resolve username → user_id через lookup
            # Пока создаём mention с username как user_id placeholder
            mention = Mention(
                comment_id=comment.id,
                user_id=username,  # Будет заменён на реальный user_id при lookup
                notified=False,
            )
            self.db.add(mention)
