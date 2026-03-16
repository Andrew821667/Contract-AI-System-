"""Collaboration — Pydantic schemas для API."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class CommentCreate(BaseModel):
    document_id: str
    content: str = Field(..., min_length=1, max_length=5000)
    anchor_type: str = "document"
    anchor_id: str | None = None
    parent_comment_id: str | None = None


class CommentRead(BaseModel):
    id: str
    document_id: str
    author_id: str | None
    content: str
    anchor_type: str
    anchor_id: str | None
    is_ai_generated: bool
    parent_comment_id: str | None
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}


class CommentThreadRead(BaseModel):
    id: str
    document_id: str
    root_comment_id: str
    status: str
    resolved_by: str | None
    resolved_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}
