# -*- coding: utf-8 -*-
"""
API v2 — Comments

Комментарии к документам: создание, список, ответы, резолв, назначение.
"""
from typing import List, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from src.api.dependencies import get_current_user
from src.api.v2.dependencies import verify_document_access
from src.models.database import get_db
from src.models.auth_models import User
from src.core.collaboration.models import Comment
from src.core.collaboration.service import CommentService
from src.core.collaboration.schemas import CommentCreate, CommentRead

router = APIRouter(tags=["Comments"])


def _get_comment_with_access(
    comment_id: str, user: User, db: Session,
) -> Comment:
    """Загрузить комментарий и проверить доступ к его документу."""
    comment = db.query(Comment).filter(Comment.id == comment_id).first()
    if not comment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Комментарий {comment_id} не найден",
        )
    verify_document_access(comment.document_id, user, db)
    return comment


# ── Request bodies ──────────────────────────────


class ReplyBody(BaseModel):
    content: str = Field(..., min_length=1, max_length=5000)


class AssignBody(BaseModel):
    assignee_id: str


# ──────────────────────────────────────────────
# POST /documents/{document_id}/comments
# ──────────────────────────────────────────────
@router.post(
    "/documents/{document_id}/comments",
    response_model=CommentRead,
    status_code=status.HTTP_201_CREATED,
    summary="Создать комментарий",
)
async def create_comment(
    document_id: str,
    body: CommentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CommentRead:
    """Создать комментарий к документу."""
    # IDOR fix: проверяем доступ к документу
    verify_document_access(document_id, current_user, db)

    svc = CommentService(db)
    comment = svc.create_comment(
        document_id=document_id,
        author_id=str(current_user.id),
        content=body.content,
        anchor_type=body.anchor_type,
        anchor_id=body.anchor_id,
        parent_comment_id=body.parent_comment_id,
    )
    db.commit()
    db.refresh(comment)
    return CommentRead.model_validate(comment)


# ──────────────────────────────────────────────
# GET /documents/{document_id}/comments
# ──────────────────────────────────────────────
@router.get(
    "/documents/{document_id}/comments",
    response_model=List[CommentRead],
    summary="Список комментариев документа",
)
async def list_comments(
    document_id: str,
    anchor_type: Literal["document", "section", "clause", "finding"] | None = Query(None, description="Фильтр по типу якоря"),
    include_resolved: bool = Query(False, description="Включить закрытые комментарии"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> List[CommentRead]:
    """Получить комментарии к документу с опциональной фильтрацией."""
    # IDOR fix: проверяем доступ к документу
    verify_document_access(document_id, current_user, db)

    svc = CommentService(db)
    comments = svc.get_document_comments(
        document_id=document_id,
        anchor_type=anchor_type,
        include_resolved=include_resolved,
    )
    return [CommentRead.model_validate(c) for c in comments]


# ──────────────────────────────────────────────
# POST /comments/{comment_id}/reply
# ──────────────────────────────────────────────
@router.post(
    "/comments/{comment_id}/reply",
    response_model=CommentRead,
    status_code=status.HTTP_201_CREATED,
    summary="Ответить на комментарий",
)
async def reply_to_comment(
    comment_id: str,
    body: ReplyBody,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CommentRead:
    """Ответить на существующий комментарий."""
    _get_comment_with_access(comment_id, current_user, db)
    svc = CommentService(db)
    try:
        comment = svc.reply(
            parent_comment_id=comment_id,
            author_id=str(current_user.id),
            content=body.content,
        )
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Комментарий не найден",
        )
    db.commit()
    db.refresh(comment)
    return CommentRead.model_validate(comment)


# ──────────────────────────────────────────────
# POST /comments/{comment_id}/resolve
# ──────────────────────────────────────────────
@router.post(
    "/comments/{comment_id}/resolve",
    response_model=CommentRead,
    summary="Закрыть комментарий",
)
async def resolve_comment(
    comment_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CommentRead:
    """Закрыть (resolve) комментарий."""
    _get_comment_with_access(comment_id, current_user, db)
    svc = CommentService(db)
    comment = svc.resolve_comment(
        comment_id=comment_id,
        user_id=str(current_user.id),
    )
    if not comment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Комментарий {comment_id} не найден",
        )
    db.commit()
    db.refresh(comment)
    return CommentRead.model_validate(comment)


# ──────────────────────────────────────────────
# POST /comments/{comment_id}/assign
# ──────────────────────────────────────────────
@router.post(
    "/comments/{comment_id}/assign",
    status_code=status.HTTP_200_OK,
    summary="Назначить ответственного",
)
async def assign_comment(
    comment_id: str,
    body: AssignBody,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Назначить ответственного за комментарий."""
    _get_comment_with_access(comment_id, current_user, db)
    svc = CommentService(db)
    try:
        assignment = svc.assign_comment(
            comment_id=comment_id,
            assignee_id=body.assignee_id,
        )
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ошибка назначения комментария",
        )
    db.commit()
    return {
        "comment_id": comment_id,
        "assignee_id": body.assignee_id,
        "assignment_id": str(assignment.id),
        "status": "назначено",
    }
