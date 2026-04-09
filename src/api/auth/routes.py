"""
Authentication API Routes

Provides REST API endpoints for:
- User registration and login
- Demo token generation and activation
- Admin user management
- Session management
- Analytics
"""

from fastapi import APIRouter, Depends, HTTPException, status, Header, Request, Cookie
from fastapi.responses import JSONResponse
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
import os
from sqlalchemy.orm import Session
from loguru import logger

from src.models import get_db, User
from src.services.auth_service import AuthService


# Cookie settings for refresh token
REFRESH_COOKIE_NAME = "refresh_token"
REFRESH_COOKIE_PATH = "/api/v1/auth"
REFRESH_COOKIE_HTTPONLY = True
REFRESH_COOKIE_SAMESITE = "lax"
REFRESH_COOKIE_SECURE = os.getenv("APP_ENV", os.getenv("ENVIRONMENT", "development")) == "production"
REFRESH_COOKIE_MAX_AGE = 30 * 24 * 3600  # 30 days

# CSRF: allowed origins for cookie-based endpoints (M1)
_ALLOWED_ORIGINS = {
    "http://localhost:3000",
    "http://localhost:8090",
}
# Trusted origin suffixes (e.g. ngrok tunnels)
_ALLOWED_ORIGIN_SUFFIXES = [
    ".ngrok-free.dev",
    ".ngrok.io",
]
# Extend from settings if available
try:
    from config.settings import settings as _settings
    if hasattr(_settings, 'allowed_origins'):
        _ALLOWED_ORIGINS.update(_settings.allowed_origins)
except Exception:
    pass


def _is_origin_allowed(origin: str) -> bool:
    """Check if origin is in allowed list or matches trusted suffix."""
    if origin in _ALLOWED_ORIGINS:
        return True
    from urllib.parse import urlparse
    parsed = urlparse(origin)
    hostname = parsed.hostname or ""
    return any(hostname.endswith(suffix) for suffix in _ALLOWED_ORIGIN_SUFFIXES)


def _check_csrf(request: Request) -> None:
    """
    CSRF protection for cookie-based auth endpoints (M1).

    Validates Origin header to prevent cross-site request forgery
    when refresh_token is sent via httpOnly cookie.
    Falls back to Referer header validation when Origin is absent.
    """
    origin = request.headers.get("origin")
    if origin:
        if not _is_origin_allowed(origin):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="CSRF: origin not allowed",
            )
        return

    # No Origin header — check Referer as fallback (some browsers omit Origin)
    referer = request.headers.get("referer")
    if referer:
        from urllib.parse import urlparse
        parsed = urlparse(referer)
        referer_origin = f"{parsed.scheme}://{parsed.netloc}"
        if not _is_origin_allowed(referer_origin):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="CSRF: referer not allowed",
            )
        return

    # No Origin and no Referer — allow (non-browser client like curl, Postman)


def _set_refresh_cookie(response: JSONResponse, refresh_token: str) -> None:
    """Set refresh_token as httpOnly cookie on the response."""
    response.set_cookie(
        key=REFRESH_COOKIE_NAME,
        value=refresh_token,
        httponly=REFRESH_COOKIE_HTTPONLY,
        secure=REFRESH_COOKIE_SECURE,
        samesite=REFRESH_COOKIE_SAMESITE,
        path=REFRESH_COOKIE_PATH,
        max_age=REFRESH_COOKIE_MAX_AGE,
    )


def _clear_refresh_cookie(response: JSONResponse) -> None:
    """Remove the refresh_token cookie."""
    response.delete_cookie(
        key=REFRESH_COOKIE_NAME,
        path=REFRESH_COOKIE_PATH,
        httponly=REFRESH_COOKIE_HTTPONLY,
        secure=REFRESH_COOKIE_SECURE,
        samesite=REFRESH_COOKIE_SAMESITE,
    )


# ==================== Pydantic Models ====================

class UserRegisterRequest(BaseModel):
    """User registration request"""
    email: EmailStr
    name: str = Field(..., min_length=2, max_length=255)
    password: str = Field(..., min_length=8)
    # SECURITY: role and subscription_tier are NOT accepted from client
    # New users always get junior_lawyer/demo. Only admin can change roles.


class UserLoginRequest(BaseModel):
    """User login request"""
    email: EmailStr
    password: str


class DemoTokenGenerateRequest(BaseModel):
    """Demo token generation request"""
    max_contracts: int = Field(default=3, ge=1, le=10)
    max_llm_requests: int = Field(default=10, ge=1, le=100)
    expires_in_hours: int = Field(default=24, ge=1, le=168)
    campaign: Optional[str] = None
    source: str = "admin_panel"


class DemoActivateRequest(BaseModel):
    """Demo token activation request"""
    token: str
    email: EmailStr
    name: str = Field(..., min_length=2, max_length=255)


class VerifyEmailRequest(BaseModel):
    """Email verification request"""
    token: str


class ResendVerificationRequest(BaseModel):
    """Resend verification email request"""
    email: EmailStr


class RefreshTokenRequest(BaseModel):
    """Refresh token request (body is optional — refresh_token may come from httpOnly cookie)"""
    refresh_token: Optional[str] = None


class ChangePasswordRequest(BaseModel):
    """Change password request"""
    current_password: str
    new_password: str = Field(..., min_length=8)


class CreateUserRequest(BaseModel):
    """Admin: Create user request"""
    email: EmailStr
    name: str = Field(..., min_length=2, max_length=255)
    role: str = Field(..., pattern="^(admin|senior_lawyer|lawyer|junior_lawyer|demo)$")
    subscription_tier: str = Field(default="demo", pattern="^(demo|basic|pro|enterprise)$")


class UpdateRoleRequest(BaseModel):
    """Admin: Update role request"""
    role: str = Field(..., pattern="^(admin|senior_lawyer|lawyer|junior_lawyer|demo)$")
    subscription_tier: Optional[str] = Field(None, pattern="^(demo|basic|pro|enterprise)$")


# ==================== Dependencies (from shared module) ====================

from src.api.dependencies import get_current_user, require_admin  # noqa: E402


def get_client_ip(request: Request) -> Optional[str]:
    """Extract client IP, trusting X-Forwarded-For only from internal proxies."""
    direct_ip = request.client.host if request.client else None
    if direct_ip and direct_ip.startswith(("172.", "10.", "192.168.", "127.")):
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()
    return direct_ip


# ==================== Router Setup ====================

router = APIRouter(tags=["authentication"])


# ==================== Public Endpoints ====================

@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register(
    request_data: UserRegisterRequest,
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Register new user

    Creates a new user account with DEMO role by default.
    Sends email verification link (if email service configured).

    **Flow:**
    1. Validates email uniqueness
    2. Hashes password (bcrypt)
    3. Creates user with specified role
    4. Sends verification email
    5. Returns JWT tokens

    **Rate Limit:** 5 requests per minute per IP

    **Example:**
    ```json
    {
        "email": "user@example.com",
        "name": "John Doe",
        "password": "SecurePass123"
    }
    ```

    **Returns:**
    ```json
    {
        "user_id": "uuid",
        "email": "user@example.com",
        "access_token": "jwt_token",
        "message": "Registration successful. Please verify your email."
    }
    ```
    """
    auth_service = AuthService(db)

    user, error = auth_service.register_user(
        email=request_data.email,
        name=request_data.name,
        password=request_data.password,
        role="junior_lawyer",          # SECURITY: hardcoded, never from client
        subscription_tier="demo",      # SECURITY: hardcoded, never from client
        send_verification=False        # MVP: skip email verification, auto-login
    )

    if error:
        # SECURITY: uniform response to prevent account enumeration.
        if "already" in (error or "").lower() or "exist" in (error or "").lower():
            return JSONResponse(
                status_code=status.HTTP_200_OK,
                content={"message": "Если указанный email свободен, на него будет отправлено письмо для подтверждения."}
            )
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=error)

    # Log registration from IP
    ip_address = get_client_ip(request)
    user_agent = request.headers.get("User-Agent")

    auth_service.log_action(
        user_id=user.id,
        action="registration_completed",
        status="success",
        ip_address=ip_address
    )

    # Create tokens and session (same pattern as login)
    access_token = auth_service.create_access_token(user.id)
    refresh_token = auth_service.create_refresh_token(user.id)

    from src.models.auth_models import UserSession
    from datetime import timedelta, timezone

    session = UserSession(
        user_id=user.id,
        access_token=access_token,
        refresh_token=refresh_token,
        ip_address=ip_address,
        user_agent=user_agent,
        expires_at=datetime.now(timezone.utc) + timedelta(days=auth_service.REFRESH_TOKEN_EXPIRE_DAYS)
    )
    db.add(session)
    db.commit()

    login_data = {
        "user": {
            "id": user.id,
            "email": user.email,
            "name": user.name,
            "role": user.role,
            "subscription_tier": user.subscription_tier
        },
        "access_token": access_token,
        "token_type": "Bearer",
        "expires_in": auth_service.ACCESS_TOKEN_EXPIRE_MINUTES * 60
    }

    response = JSONResponse(status_code=status.HTTP_201_CREATED, content=login_data)
    _set_refresh_cookie(response, refresh_token)
    return response


@router.get("/quota")
async def get_quota(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Получить оставшуюся квоту текущего пользователя.

    Возвращает использованные и максимальные лимиты по договорам и AI-запросам.
    """
    # Reset daily limits if needed
    current_user.reset_daily_limits()
    db.commit()

    tier_limits = User.TIER_LIMITS.get(
        current_user.subscription_tier,
        User.TIER_LIMITS['demo']
    )

    return {
        "contracts_used": current_user.contracts_today or 0,
        "contracts_limit": tier_limits['max_contracts_per_day'],
        "llm_used": current_user.llm_requests_today or 0,
        "llm_limit": tier_limits['max_llm_requests_per_day'],
        "subscription_tier": current_user.subscription_tier,
    }


@router.post("/verify-email")
async def verify_email(
    request_data: VerifyEmailRequest,
    db: Session = Depends(get_db)
):
    """
    Подтвердить email по токену из письма.

    Принимает токен верификации, проверяет срок действия,
    отмечает email как подтверждённый.

    **Пример:**
    ```json
    {"token": "abc123..."}
    ```
    """
    auth_service = AuthService(db)

    success, error = auth_service.verify_email(request_data.token)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error
        )

    return {"message": "Email успешно подтверждён. Теперь вы можете войти в систему."}


@router.post("/resend-verification")
async def resend_verification(
    request_data: ResendVerificationRequest,
    db: Session = Depends(get_db)
):
    """
    Повторно отправить письмо для подтверждения email.

    Создаёт новый токен верификации (старые инвалидируются).
    Для защиты от перебора всегда возвращает одинаковый ответ.

    **Пример:**
    ```json
    {"email": "user@example.com"}
    ```
    """
    auth_service = AuthService(db)

    # Единообразный ответ для защиты от перебора email
    uniform_response = {
        "message": "Если указанный email зарегистрирован и не подтверждён, на него будет отправлено письмо."
    }

    user = db.query(User).filter(User.email == request_data.email).first()

    if not user or user.email_verified:
        return uniform_response

    # Создать новый токен верификации
    verification = auth_service.create_email_verification(user.id, user.email)
    db.commit()

    # Попробовать отправить email (не блокируем при ошибке)
    try:
        from src.services.email_service import email_service
        await email_service.send_verification_email(
            to_email=user.email,
            verification_token=verification.token,
            user_name=user.name
        )
    except Exception as e:
        logger.warning(f"Не удалось отправить verification email: {e}")

    return uniform_response


@router.post("/login")
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    request: Request = None,
    db: Session = Depends(get_db)
):
    """
    Login user with email and password

    **Flow:**
    1. Validates credentials
    2. Checks account status (not locked, email verified)
    3. Creates JWT session
    4. Returns access & refresh tokens

    **Security:**
    - Passwords hashed with bcrypt
    - Account locked after 5 failed attempts (30 min)
    - All attempts logged

    **Rate Limit:** 10 requests per minute per IP

    **Example:**
    ```
    POST /api/v1/auth/login
    Content-Type: application/x-www-form-urlencoded

    username=user@example.com&password=SecurePass123
    ```

    **Returns:**
    ```json
    {
        "user": {
            "id": "uuid",
            "email": "user@example.com",
            "name": "John Doe",
            "role": "lawyer"
        },
        "access_token": "jwt_access_token",
        "refresh_token": "jwt_refresh_token",
        "token_type": "Bearer",
        "expires_in": 3600
    }
    ```
    """
    auth_service = AuthService(db)

    ip_address = get_client_ip(request) if request else None
    user_agent = request.headers.get("User-Agent") if request else None

    login_data, error = auth_service.login_user(
        email=form_data.username,
        password=form_data.password,
        ip_address=ip_address,
        user_agent=user_agent
    )

    if error:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=error,
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Set refresh_token as httpOnly cookie, remove from response body
    refresh_token_value = login_data.pop("refresh_token", None)
    response = JSONResponse(content=login_data)
    if refresh_token_value:
        _set_refresh_cookie(response, refresh_token_value)
    return response


@router.post("/demo-activate")
async def activate_demo(
    request_data: DemoActivateRequest,
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Activate demo access using token from link

    **Flow:**
    1. User clicks demo link (e.g., from website)
    2. Enters email and name
    3. System creates DEMO account automatically
    4. User gets instant access (no password required for demo period)

    **Example Link:**
    ```
    https://contract-ai.example.com/demo?token=abc123xyz
    ```

    **Request:**
    ```json
    {
        "token": "abc123xyz",
        "email": "demo@example.com",
        "name": "Demo User"
    }
    ```

    **Returns:**
    ```json
    {
        "user": {
            "id": "uuid",
            "email": "demo@example.com",
            "name": "Demo User",
            "role": "demo",
            "is_demo": true,
            "demo_expires": "2025-01-16T10:00:00"
        },
        "access_token": "jwt_token",
        "refresh_token": "jwt_refresh_token",
        "expires_at": "2025-01-16T10:00:00"
    }
    ```
    """
    auth_service = AuthService(db)

    ip_address = get_client_ip(request)

    activation_data, error = auth_service.activate_demo_token(
        token=request_data.token,
        email=request_data.email,
        name=request_data.name,
        ip_address=ip_address
    )

    if error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=error)

    # Set refresh_token as httpOnly cookie, remove from response body
    refresh_token_value = activation_data.pop("refresh_token", None)
    response = JSONResponse(content=activation_data)
    if refresh_token_value:
        _set_refresh_cookie(response, refresh_token_value)
    return response


@router.post("/refresh")
async def refresh_token(
    request: Request,
    request_data: RefreshTokenRequest = None,
    db: Session = Depends(get_db)
):
    """
    Refresh access token using refresh token

    **Flow:**
    1. Client sends refresh token (via httpOnly cookie or body for backward compat)
    2. Server validates refresh token
    3. Issues new access + refresh tokens (refresh in httpOnly cookie)
    4. Old tokens are revoked

    **Use When:**
    - Access token expired (401 error)
    - Before expiration (proactive refresh)
    - On page reload (cookie sent automatically)

    **Returns:**
    ```json
    {
        "access_token": "new_access_token",
        "token_type": "Bearer",
        "expires_in": 3600
    }
    ```
    """
    _check_csrf(request)

    # Get refresh token: prefer httpOnly cookie, fallback to body
    token = request.cookies.get(REFRESH_COOKIE_NAME)
    if not token and request_data:
        token = request_data.refresh_token

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token не предоставлен"
        )

    auth_service = AuthService(db)

    new_tokens, error = auth_service.refresh_session(token)

    if error:
        # Clear the stale cookie on failure
        resp = JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"detail": error}
        )
        _clear_refresh_cookie(resp)
        return resp

    # Set new refresh_token as httpOnly cookie, remove from response body
    new_refresh_token = new_tokens.pop("refresh_token", None)
    response = JSONResponse(content=new_tokens)
    if new_refresh_token:
        _set_refresh_cookie(response, new_refresh_token)
    return response


@router.post("/logout")
async def logout(
    request: Request,
    current_user: User = Depends(get_current_user),
    authorization: str = Header(None),
    db: Session = Depends(get_db)
):
    """
    Logout user (revoke session)

    **Flow:**
    1. Extracts access token from Authorization header
    2. Revokes session in database
    3. Logs logout action

    **Headers:**
    ```
    Authorization: Bearer {access_token}
    ```

    **Returns:**
    ```json
    {
        "message": "Logged out successfully"
    }
    ```
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid authorization header"
        )

    access_token = authorization.replace("Bearer ", "")

    auth_service = AuthService(db)
    success = auth_service.logout_user(access_token)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Logout failed"
        )

    # Clear refresh_token cookie
    response = JSONResponse(content={"message": "Logged out successfully"})
    _clear_refresh_cookie(response)
    return response


# ==================== Protected Endpoints ====================

@router.get("/me")
async def get_current_user_info(
    current_user: User = Depends(get_current_user)
):
    """
    Get current authenticated user information

    **Requires:** Valid JWT access token

    **Headers:**
    ```
    Authorization: Bearer {access_token}
    ```

    **Returns:**
    ```json
    {
        "id": "uuid",
        "email": "user@example.com",
        "name": "John Doe",
        "role": "lawyer",
        "subscription_tier": "pro",
        "is_demo": false,
        "email_verified": true,
        "created_at": "2025-01-01T00:00:00",
        "last_login": "2025-01-15T10:00:00",
        "contracts_today": 5,
        "llm_requests_today": 25
    }
    ```
    """
    return {
        "id": current_user.id,
        "email": current_user.email,
        "name": current_user.name,
        "role": current_user.role,
        "subscription_tier": current_user.subscription_tier,
        "is_demo": current_user.is_demo,
        "email_verified": current_user.email_verified,
        "two_factor_enabled": current_user.two_factor_enabled,
        "active": current_user.active,
        "created_at": current_user.created_at.isoformat() if current_user.created_at else None,
        "last_login": current_user.last_login.isoformat() if current_user.last_login else None,
        "login_count": current_user.login_count,
        "contracts_today": current_user.contracts_today,
        "llm_requests_today": current_user.llm_requests_today,
        "demo_expires": current_user.demo_expires.isoformat() if current_user.demo_expires else None
    }


@router.post("/change-password")
async def change_password(
    request_data: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Change current user's password.

    Requires:
    - current_password: Must match existing password
    - new_password: At least 8 characters
    """
    auth_service = AuthService(db)

    # Verify current password
    if not auth_service.verify_password(request_data.current_password, current_user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Неверный текущий пароль"
        )

    # Validate new password strength
    is_strong, strength_error = auth_service.validate_password_strength(request_data.new_password)
    if not is_strong:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=strength_error
        )

    # Update password
    current_user.password_hash = auth_service.hash_password(request_data.new_password)

    # Revoke all other sessions (force re-login)
    from src.models.auth_models import UserSession
    db.query(UserSession).filter(
        UserSession.user_id == current_user.id,
        UserSession.revoked == False
    ).update({"revoked": True})

    db.commit()

    logger.info(f"Password changed for user {current_user.email}, all sessions revoked")

    return {"message": "Пароль успешно изменён. Все сессии завершены, войдите заново."}


# ==================== Admin Endpoints ====================

@router.post("/admin/demo-link", dependencies=[Depends(require_admin)])
async def generate_demo_link(
    request_data: DemoTokenGenerateRequest,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    Generate demo access link (Admin only)

    **Requires:** Admin role

    **Flow:**
    1. Admin creates demo token with parameters
    2. System generates unique link
    3. Link can be shared on website/marketing materials
    4. Anyone with link can activate demo access

    **Example:**
    ```json
    {
        "max_contracts": 3,
        "max_llm_requests": 10,
        "expires_in_hours": 24,
        "campaign": "website_header_cta"
    }
    ```

    **Returns:**
    ```json
    {
        "token": "abc123xyz...",
        "url": "https://contract-ai.example.com/demo?token=abc123xyz",
        "expires_at": "2025-01-16T10:00:00",
        "max_contracts": 3,
        "max_llm_requests": 10
    }
    ```
    """
    auth_service = AuthService(db)

    demo_token = auth_service.generate_demo_token(
        created_by_user_id=current_user.id,
        max_contracts=request_data.max_contracts,
        max_llm_requests=request_data.max_llm_requests,
        expires_in_hours=request_data.expires_in_hours,
        campaign=request_data.campaign,
        source=request_data.source
    )

    # Generate URL (you can customize domain here)
    demo_url = f"https://contract-ai.example.com/demo?token={demo_token.token}"

    return {
        "token": demo_token.token,
        "url": demo_url,
        "expires_at": demo_token.expires_at.isoformat(),
        "max_contracts": demo_token.max_contracts,
        "max_llm_requests": demo_token.max_llm_requests,
        "created_by": current_user.email
    }


@router.post("/admin/users", dependencies=[Depends(require_admin)])
async def create_user_as_admin(
    request_data: CreateUserRequest,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    Create user as admin

    **Requires:** Admin role

    **Flow:**
    1. Admin creates user with specified role
    2. System generates temporary password
    3. Invitation email sent to user
    4. User must change password on first login

    **Example:**
    ```json
    {
        "email": "newuser@example.com",
        "name": "New User",
        "role": "lawyer",
        "subscription_tier": "pro"
    }
    ```

    **Returns:**
    ```json
    {
        "user_id": "uuid",
        "email": "newuser@example.com",
        "temp_password": "TempPass123xyz",
        "message": "User created. Invitation email sent."
    }
    ```
    """
    auth_service = AuthService(db)

    user, temp_password, error = auth_service.create_user_as_admin(
        email=request_data.email,
        name=request_data.name,
        role=request_data.role,
        subscription_tier=request_data.subscription_tier,
        admin_user_id=current_user.id
    )

    if error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=error)

    # Send invitation email with temp_password
    email_sent = False
    try:
        from html import escape
        from src.services.email_service import email_service

        safe_name = escape(user.name)
        safe_email = escape(user.email)
        safe_role = escape(user.role)
        safe_password = escape(temp_password)

        html = f"""
        <html>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
            <div style="max-width: 600px; margin: 0 auto; padding: 20px; border: 1px solid #ddd; border-radius: 10px;">
                <h2 style="color: #3B82F6;">Добро пожаловать в Contract AI System!</h2>
                <p>Здравствуйте, {safe_name}!</p>
                <p>Для вас создан аккаунт в системе автоматизации работы с договорами.</p>
                <div style="background: #f8f9fa; padding: 15px; border-radius: 5px; margin: 20px 0;">
                    <p><strong>Email:</strong> {safe_email}</p>
                    <p><strong>Временный пароль:</strong> <code style="background: #e9ecef; padding: 2px 6px; border-radius: 3px;">{safe_password}</code></p>
                    <p><strong>Роль:</strong> {safe_role}</p>
                </div>
                <p>⚠️ <strong>Важно:</strong> Пожалуйста, измените временный пароль после первого входа в систему.</p>
                <p style="margin-top: 30px; font-size: 12px; color: #666;">
                    С уважением,<br>Команда Contract AI System
                </p>
            </div>
        </body>
        </html>
        """

        success, err = await email_service.send_email(
            to_email=user.email,
            subject="Приглашение в Contract AI System",
            html_content=html,
        )
        email_sent = success
        if success:
            logger.info(f"Invitation email sent to {user.email}")

    except Exception as e:
        logger.warning(f"Failed to send invitation email: {e}")

    result = {
        "user_id": user.id,
        "email": user.email,
        "name": user.name,
        "email_sent": email_sent,
        "message": "User created successfully.",
    }
    # Only include temp_password in response if email was NOT sent
    if not email_sent:
        result["temp_password"] = temp_password
        result["message"] = "User created. Email not sent — temporary password included in response."

    return result


@router.patch("/admin/users/{user_id}/role", dependencies=[Depends(require_admin)])
async def update_user_role(
    user_id: str,
    request_data: UpdateRoleRequest,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    Update user role and subscription tier (Admin only)

    **Requires:** Admin role

    **Example:**
    ```json
    {
        "role": "senior_lawyer",
        "subscription_tier": "pro"
    }
    ```

    **Returns:**
    ```json
    {
        "message": "Role updated successfully",
        "user_id": "uuid",
        "new_role": "senior_lawyer",
        "new_tier": "pro"
    }
    ```
    """
    auth_service = AuthService(db)

    success, error = auth_service.update_user_role(
        user_id=user_id,
        new_role=request_data.role,
        admin_user_id=current_user.id,
        subscription_tier=request_data.subscription_tier
    )

    if error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=error)

    return {
        "message": "Role updated successfully",
        "user_id": user_id,
        "new_role": request_data.role,
        "new_tier": request_data.subscription_tier
    }


@router.get("/admin/users", dependencies=[Depends(require_admin)])
async def list_users(
    page: int = 1,
    limit: int = 50,
    role: Optional[str] = None,
    search: Optional[str] = None,
    is_demo: Optional[bool] = None,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    List all users with filtering and pagination (Admin only)

    **Requires:** Admin role

    **Query Parameters:**
    - `page`: Page number (default: 1)
    - `limit`: Items per page (default: 50, max: 100)
    - `role`: Filter by role (admin, senior_lawyer, lawyer, junior_lawyer, demo)
    - `search`: Search in email or name
    - `is_demo`: Filter demo users (true/false)

    **Example:**
    ```
    GET /api/v1/auth/admin/users?page=1&limit=20&role=lawyer&search=john
    ```

    **Returns:**
    ```json
    {
        "total": 150,
        "page": 1,
        "limit": 20,
        "pages": 8,
        "users": [
            {
                "id": "uuid",
                "email": "user@example.com",
                "name": "John Doe",
                "role": "lawyer",
                "subscription_tier": "pro",
                "active": true,
                "is_demo": false,
                "created_at": "2025-01-01T00:00:00",
                "last_login": "2025-01-15T10:00:00"
            }
        ]
    }
    ```
    """
    if limit > 100:
        limit = 100

    auth_service = AuthService(db)

    result = auth_service.list_users(
        page=page,
        limit=limit,
        role=role,
        search=search,
        is_demo=is_demo
    )

    return result


@router.get("/admin/analytics", dependencies=[Depends(require_admin)])
async def get_analytics(
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    Get system analytics (Admin only)

    **Requires:** Admin role

    **Returns:**
    ```json
    {
        "total_users": 250,
        "active_users": 180,
        "demo_users": 50,
        "users_by_role": {
            "admin": 5,
            "senior_lawyer": 20,
            "lawyer": 100,
            "junior_lawyer": 75,
            "demo": 50
        },
        "active_last_week": 120,
        "demo_converted": 30,
        "conversion_rate": 60.0
    }
    ```
    """
    auth_service = AuthService(db)
    analytics = auth_service.get_analytics()

    return analytics


# ─── SSO — Bridge Token Exchange ─────────────────────────────

BRIDGE_SECRET = os.getenv("BRIDGE_SECRET", "")


class SSOTokenRequest(BaseModel):
    """Запрос на обмен platform-токена на JWT Contract-AI-System."""
    platform_token: str = Field(description="Shared secret от Legal AI Platform")
    user_email: EmailStr = Field(description="Email пользователя")
    user_name: str = Field(default="", description="Имя пользователя")
    org_id: str = Field(default="", description="ID организации")
    role: str = Field(default="demo", description="Роль пользователя")


class SSOTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: str
    user_email: str
    user_name: str
    redirect_url: str = Field(default="", description="URL для редиректа в кабинет")


@router.post("/sso-token", response_model=SSOTokenResponse)
async def sso_token_exchange(
    request: SSOTokenRequest,
    db: Session = Depends(get_db)
):
    """
    SSO Token Exchange — обмен platform-токена на JWT.

    Используется Legal AI Platform для бесшовного входа пользователей
    в Contract-AI-System без отдельной регистрации/логина.

    **Flow:**
    1. Legal AI Platform авторизует пользователя на своей стороне
    2. Отправляет сюда platform_token (shared secret) + данные пользователя
    3. Contract-AI-System валидирует secret, создаёт/находит пользователя
    4. Возвращает JWT-токен для доступа к API Contract-AI-System
    """
    # Валидация bridge secret
    if not BRIDGE_SECRET:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="SSO not configured (BRIDGE_SECRET not set)"
        )

    if request.platform_token != BRIDGE_SECRET:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid platform token"
        )

    # Найти или создать пользователя
    user = db.query(User).filter(User.email == request.user_email).first()

    if not user:
        import uuid
        # Маппинг ролей platform → contract-ai
        role_map = {
            "admin": "admin",
            "lawyer": "lawyer",
            "senior_lawyer": "senior_lawyer",
            "user": "demo",
            "demo": "demo",
        }
        mapped_role = role_map.get(request.role, "demo")

        user = User(
            id=str(uuid.uuid4()),
            email=request.user_email,
            name=request.user_name or request.user_email.split("@")[0],
            role=mapped_role,
            hashed_password="sso_bridge_user",  # Не может войти по паролю
            is_active=True,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        logger.info(f"SSO: created user {request.user_email} (role={mapped_role})")
    else:
        # Обновляем имя если пришло новое
        if request.user_name and request.user_name != user.name:
            user.name = request.user_name
            db.commit()

    # Генерируем JWT
    auth_service = AuthService(db)
    access_token = auth_service.create_access_token(
        user_id=user.id,
        additional_claims={"source": "sso_bridge", "org_id": request.org_id}
    )

    # URL для редиректа (фронтенд Contract-AI-System)
    ngrok_url = os.getenv("NGROK_URL", "")
    base_url = ngrok_url if ngrok_url else "http://localhost:8090"
    redirect_url = f"{base_url}/auth/sso?token={access_token}"

    return SSOTokenResponse(
        access_token=access_token,
        user_id=user.id,
        user_email=user.email,
        user_name=user.name,
        redirect_url=redirect_url,
    )
