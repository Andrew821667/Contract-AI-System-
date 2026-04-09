# -*- coding: utf-8 -*-
"""
Shared API Dependencies

Single source of truth for get_current_user and require_admin.
All route modules MUST import from here instead of defining their own.
"""
import hashlib
import time
from typing import Optional, Tuple

from fastapi import Depends, Header, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from loguru import logger
from sqlalchemy.orm import Session

from src.models.database import get_db
from src.models.auth_models import User, UserSession
from src.services.auth_service import AuthService


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


# ── Auth verification cache ─────────────────────────────────────────────
# Caches verified (token_hash → user_id) for 30 seconds to avoid
# 3 DB queries per request (verify_token + session check + user fetch).
# Uses Redis if available, falls back to in-memory LRU.

_AUTH_CACHE_TTL = 30  # seconds
_AUTH_CACHE_MAX = 512  # max entries for in-memory fallback

_redis_client = None
_redis_checked = False


def _get_redis():
    """Lazy-init Redis client for auth cache."""
    global _redis_client, _redis_checked
    if _redis_checked:
        return _redis_client
    _redis_checked = True
    try:
        import redis
        from config.settings import settings
        _redis_client = redis.Redis.from_url(
            settings.redis_url, decode_responses=True, socket_connect_timeout=1
        )
        _redis_client.ping()
        logger.info("Auth cache: using Redis backend")
    except Exception:
        _redis_client = None
        logger.info("Auth cache: using in-memory fallback")
    return _redis_client


# In-memory fallback: {token_hash: (user_id, expires_at)}
_mem_cache: dict[str, Tuple[str, float]] = {}


def _cache_get(token_hash: str) -> Optional[str]:
    """Get cached user_id for token hash. Returns None on miss/expired."""
    r = _get_redis()
    if r:
        try:
            return r.get(f"auth:{token_hash}")
        except Exception:
            pass
    # In-memory fallback
    entry = _mem_cache.get(token_hash)
    if entry and entry[1] > time.time():
        return entry[0]
    return None


def _cache_set(token_hash: str, user_id: str) -> None:
    """Cache verified token → user_id."""
    r = _get_redis()
    if r:
        try:
            r.setex(f"auth:{token_hash}", _AUTH_CACHE_TTL, user_id)
            return
        except Exception:
            pass
    # In-memory fallback with bounded size
    if len(_mem_cache) >= _AUTH_CACHE_MAX:
        # Evict oldest quarter
        now = time.time()
        expired = [k for k, v in _mem_cache.items() if v[1] <= now]
        for k in expired:
            del _mem_cache[k]
        if len(_mem_cache) >= _AUTH_CACHE_MAX:
            # Still full — remove first 25%
            keys = list(_mem_cache.keys())[:_AUTH_CACHE_MAX // 4]
            for k in keys:
                del _mem_cache[k]
    _mem_cache[token_hash] = (user_id, time.time() + _AUTH_CACHE_TTL)


def _cache_invalidate(token_hash: str) -> None:
    """Remove cached entry (on logout/revoke)."""
    r = _get_redis()
    if r:
        try:
            r.delete(f"auth:{token_hash}")
        except Exception:
            pass
    _mem_cache.pop(token_hash, None)


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
) -> User:
    """
    Get current authenticated user from JWT token.

    This is the ONLY canonical implementation.
    Do NOT duplicate this in route modules.

    Performance: verified tokens are cached for 30 seconds (Redis or in-memory)
    to avoid 3 DB queries per request.
    """
    # Check cache first
    token_hash = hashlib.sha256(token.encode()).hexdigest()[:32]
    cached_user_id = _cache_get(token_hash)

    if cached_user_id:
        # Cache hit — only 1 DB query (fetch user) instead of 3
        user = db.query(User).filter(User.id == cached_user_id).first()
        if user and user.is_active() and user.email_verified:
            return user
        # User changed state — invalidate cache and fall through
        _cache_invalidate(token_hash)

    # Cache miss — full verification (3 DB queries)
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

    # Cache successful verification
    _cache_set(token_hash, str(user.id))

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


async def get_optional_org_id(
    x_organization_id: Optional[str] = Header(None),
) -> Optional[str]:
    """
    Extract optional org context from X-Organization-Id header.
    Returns None if header is absent (personal mode).
    """
    return x_organization_id


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
