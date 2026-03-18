# -*- coding: utf-8 -*-
"""
Shared API Dependencies

Single source of truth for get_current_user and require_admin.
All route modules MUST import from here instead of defining their own.
"""
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from src.models.database import get_db
from src.models.auth_models import User, UserSession
from src.services.auth_service import AuthService


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
) -> User:
    """
    Get current authenticated user from JWT token.

    This is the ONLY canonical implementation.
    Do NOT duplicate this in route modules.
    """
    auth_service = AuthService(db)

    payload = auth_service.verify_token(token, token_type="access")
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id = payload.get("user_id")

    # Check token revocation: verify session is not revoked
    session = db.query(UserSession).filter(
        UserSession.user_id == user_id,
        UserSession.access_token == token,
        UserSession.revoked == False
    ).first()
    if not session:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session revoked or invalid",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = db.query(User).filter(User.id == user_id).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found"
        )

    if not user.is_active():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is not active"
        )

    # Check email verification
    if not user.email_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Email not verified"
        )

    return user


async def require_admin(current_user: User = Depends(get_current_user)) -> User:
    """Require admin role"""
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    return current_user


async def require_senior_or_admin(current_user: User = Depends(get_current_user)) -> User:
    """Require senior_lawyer or admin role"""
    if current_user.role not in ("admin", "senior_lawyer"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Senior lawyer or admin access required"
        )
    return current_user


def require_permission(permission: str):
    """
    Factory for RBAC permission checks (L5).

    Usage:
        @router.get("/contracts", dependencies=[Depends(require_permission("contract.read"))])
        async def list_contracts(...): ...
    """
    async def _check(
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db),
    ) -> User:
        from src.core.enterprise.rbac import RBACService
        rbac = RBACService(db)
        if not rbac.has_permission(str(current_user.id), permission):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission required: {permission}",
            )
        return current_user
    return _check
