"""
Collaboration — SQLAlchemy модели.

Comment — комментарий к документу/секции/клаузе/finding.
CommentThread — тред (корневой комментарий + ответы).
Mention — упоминание пользователя в комментарии.
CommentAssignment — назначение комментария на ответственного.
"""

from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from src.models.database import Base, generate_uuid


class Comment(Base):
    """Комментарий к документу."""

    __tablename__ = "comments"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    document_id = Column(String(36), ForeignKey("contracts.id", ondelete="CASCADE"), nullable=False, index=True)
    author_id = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)

    content = Column(Text, nullable=False)

    # Привязка к элементу документа
    anchor_type = Column(String(30), nullable=False, default="document")  # document|section|clause|finding
    anchor_id = Column(String(36), nullable=True)  # ID секции/клаузы/finding
    anchor_version = Column(String(20), nullable=True)  # Версия документа на момент комментария

    # AI-generated?
    is_ai_generated = Column(Boolean, default=False, index=True)

    # Threading
    parent_comment_id = Column(String(36), ForeignKey("comments.id", ondelete="SET NULL"), nullable=True, index=True)

    status = Column(String(20), nullable=False, default="active")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    replies = relationship("Comment", backref="parent", remote_side="Comment.id", cascade="all")
    mentions = relationship("Mention", back_populates="comment", cascade="all, delete-orphan")
    assignment = relationship("CommentAssignment", back_populates="comment", uselist=False, cascade="all, delete-orphan")

    __table_args__ = (
        CheckConstraint(
            anchor_type.in_(["document", "section", "clause", "finding"]),
            name="check_comment_anchor_type",
        ),
        CheckConstraint(
            status.in_(["active", "resolved", "deleted"]),
            name="check_comment_status",
        ),
        Index("idx_comment_doc_anchor", "document_id", "anchor_type", "anchor_id"),
        Index("idx_comment_doc_status", "document_id", "status"),
    )

    def __repr__(self) -> str:
        return f"<Comment(id={self.id}, doc={self.document_id}, anchor={self.anchor_type})>"


class CommentThread(Base):
    """Тред — группа комментариев от корневого."""

    __tablename__ = "comment_threads"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    document_id = Column(String(36), ForeignKey("contracts.id", ondelete="CASCADE"), nullable=False, index=True)
    root_comment_id = Column(String(36), ForeignKey("comments.id", ondelete="CASCADE"), unique=True, nullable=False)

    status = Column(String(20), nullable=False, default="open")  # open | resolved
    resolved_by = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    resolved_at = Column(DateTime, nullable=True)

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        CheckConstraint(status.in_(["open", "resolved"]), name="check_thread_status"),
        Index("idx_thread_doc_status", "document_id", "status"),
    )

    def __repr__(self) -> str:
        return f"<CommentThread(id={self.id}, root={self.root_comment_id}, status={self.status})>"


class Mention(Base):
    """Упоминание пользователя в комментарии."""

    __tablename__ = "mentions"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    comment_id = Column(String(36), ForeignKey("comments.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    notified = Column(Boolean, default=False)

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    # Relationships
    comment = relationship("Comment", back_populates="mentions")

    __table_args__ = (
        Index("idx_mention_user_notified", "user_id", "notified"),
    )

    def __repr__(self) -> str:
        return f"<Mention(comment={self.comment_id}, user={self.user_id})>"


class CommentAssignment(Base):
    """Назначение комментария на ответственного."""

    __tablename__ = "comment_assignments"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    comment_id = Column(String(36), ForeignKey("comments.id", ondelete="CASCADE"), unique=True, nullable=False)
    assignee_id = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    status = Column(String(20), nullable=False, default="pending")  # pending | in_progress | done

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    completed_at = Column(DateTime, nullable=True)

    # Relationships
    comment = relationship("Comment", back_populates="assignment")

    __table_args__ = (
        CheckConstraint(status.in_(["pending", "in_progress", "done"]), name="check_assignment_status"),
        Index("idx_assignment_assignee_status", "assignee_id", "status"),
    )

    def __repr__(self) -> str:
        return f"<CommentAssignment(comment={self.comment_id}, assignee={self.assignee_id})>"
