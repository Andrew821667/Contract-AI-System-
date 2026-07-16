"""
Authentication Service

Handles all authentication operations:
- Password hashing (bcrypt)
- JWT token generation and validation
- User registration and login
- Demo token management
- Session management
- Audit logging
"""

import hashlib
import secrets
import uuid
import bcrypt
import jwt
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any, List, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_

from src.models.auth_models import (
    User, UserSession, DemoToken, AuditLog,
    PasswordResetRequest, EmailVerification, LoginAttempt,
    ensure_aware,
)
from config.settings import settings


class AuthService:
    """Authentication service with comprehensive security features"""

    # JWT-секрет — ТОЛЬКО из settings (детерминир. в dev, обязателен в prod).
    # Раньше при пустом ключе был per-process `secrets.token_urlsafe(32)` → каждый
    # gunicorn-воркер подписывал СВОИМ ключом → токен валиден лишь на «своём»
    # воркере → случайные 401 под нагрузкой. settings гарантирует непустой ключ.
    JWT_SECRET = settings.secret_key
    JWT_ALGORITHM = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES = 60  # 1 hour
    REFRESH_TOKEN_EXPIRE_DAYS = 30  # 30 days

    # Security settings
    MAX_LOGIN_ATTEMPTS = 5
    ACCOUNT_LOCK_DURATION_MINUTES = 30
    PASSWORD_MIN_LENGTH = 8

    def __init__(self, db: Session):
        self.db = db

    # ==================== Password Management ====================

    @staticmethod
    def hash_password(password: str) -> str:
        """
        Hash password using bcrypt

        Args:
            password: Plain text password

        Returns:
            Hashed password string
        """
        salt = bcrypt.gensalt(rounds=12)
        password_hash = bcrypt.hashpw(password.encode('utf-8'), salt)
        return password_hash.decode('utf-8')

    @staticmethod
    def verify_password(password: str, password_hash: str) -> bool:
        """
        Verify password against hash

        Args:
            password: Plain text password
            password_hash: Hashed password from database

        Returns:
            True if password matches, False otherwise
        """
        try:
            return bcrypt.checkpw(
                password.encode('utf-8'),
                password_hash.encode('utf-8')
            )
        except (ValueError, TypeError):
            return False

    @staticmethod
    def validate_password_strength(password: str) -> Tuple[bool, Optional[str]]:
        """
        Validate password strength

        Returns:
            (is_valid, error_message)
        """
        if len(password) < AuthService.PASSWORD_MIN_LENGTH:
            return False, f"Password must be at least {AuthService.PASSWORD_MIN_LENGTH} characters"

        if not any(c.isupper() for c in password):
            return False, "Password must contain at least one uppercase letter"

        if not any(c.islower() for c in password):
            return False, "Password must contain at least one lowercase letter"

        if not any(c.isdigit() for c in password):
            return False, "Password must contain at least one digit"

        return True, None

    # ==================== JWT Token Management ====================

    # Claims that cannot be overridden via additional_claims
    _RESERVED_CLAIMS = {"user_id", "type", "exp", "iat", "jti", "iss", "aud"}

    @staticmethod
    def _hash_token(token: str) -> str:
        """SHA-256 hash of a token for safe storage in DB."""
        return hashlib.sha256(token.encode()).hexdigest()

    def create_access_token(self, user_id: str, additional_claims: Optional[Dict] = None) -> str:
        """
        Create JWT access token with jti, iss, aud claims.

        Args:
            user_id: User ID
            additional_claims: Optional additional claims (reserved keys are filtered)

        Returns:
            JWT token string
        """
        now = datetime.now(timezone.utc)
        payload = {
            "user_id": user_id,
            "type": "access",
            "jti": str(uuid.uuid4()),
            "iss": "contract-ai-system",
            "aud": "contract-ai-system",
            "exp": now + timedelta(minutes=self.ACCESS_TOKEN_EXPIRE_MINUTES),
            "iat": now,
        }

        if additional_claims:
            # Whitelist: prevent overwriting system fields
            safe = {k: v for k, v in additional_claims.items() if k not in self._RESERVED_CLAIMS}
            payload.update(safe)

        return jwt.encode(payload, self.JWT_SECRET, algorithm=self.JWT_ALGORITHM)

    def create_refresh_token(self, user_id: str) -> str:
        """Create JWT refresh token with jti, iss, aud claims."""
        now = datetime.now(timezone.utc)
        payload = {
            "user_id": user_id,
            "type": "refresh",
            "jti": str(uuid.uuid4()),
            "iss": "contract-ai-system",
            "aud": "contract-ai-system",
            "exp": now + timedelta(days=self.REFRESH_TOKEN_EXPIRE_DAYS),
            "iat": now,
        }

        return jwt.encode(payload, self.JWT_SECRET, algorithm=self.JWT_ALGORITHM)

    def verify_token(self, token: str, token_type: str = "access") -> Optional[Dict[str, Any]]:
        """
        Verify and decode JWT token (validates iss/aud claims).

        Args:
            token: JWT token string
            token_type: Expected token type ('access' or 'refresh')

        Returns:
            Decoded payload if valid, None otherwise
        """
        try:
            payload = jwt.decode(
                token,
                self.JWT_SECRET,
                algorithms=[self.JWT_ALGORITHM],
                issuer="contract-ai-system",
                audience="contract-ai-system",
            )

            if payload.get("type") != token_type:
                return None

            return payload

        except jwt.ExpiredSignatureError:
            return None
        except jwt.InvalidTokenError:
            return None

    # ==================== Email Verification ====================

    def create_email_verification(self, user_id: str, email: str) -> EmailVerification:
        """
        Создать запись верификации email с безопасным токеном.

        Инвалидирует все предыдущие неиспользованные токены для этого пользователя.

        Args:
            user_id: ID пользователя
            email: Email для верификации

        Returns:
            EmailVerification объект с токеном
        """
        # Инвалидировать старые неиспользованные верификации
        self.db.query(EmailVerification).filter(
            EmailVerification.user_id == user_id,
            EmailVerification.verified == False
        ).delete()

        token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(token.encode()).hexdigest()

        verification = EmailVerification(
            user_id=user_id,
            email=email,
            token=token_hash,
            expires_at=datetime.now(timezone.utc) + timedelta(hours=24)
        )
        self.db.add(verification)
        self.db.flush()

        from loguru import logger
        logger.info(f"[EMAIL VERIFICATION] Token created for {email} (id: {verification.id})")

        # Store unhashed token on the object so the caller can send it to the user,
        # but only the hash is persisted in the database.
        verification._raw_token = token

        return verification

    def verify_email(self, token: str) -> Tuple[bool, Optional[str]]:
        """
        Подтвердить email по токену верификации.

        Args:
            token: Токен верификации из ссылки

        Returns:
            (success, error_message)
        """
        token_hash = hashlib.sha256(token.encode()).hexdigest()

        verification = self.db.query(EmailVerification).filter(
            EmailVerification.token == token_hash
        ).first()

        if not verification:
            return False, "Неверный токен верификации"

        if verification.verified:
            return False, "Email уже подтверждён"

        if verification.expires_at < datetime.now(timezone.utc):
            return False, "Срок действия токена истёк. Запросите новое письмо."

        # Отметить верификацию как использованную
        verification.verified = True
        verification.verified_at = datetime.now(timezone.utc)

        # Подтвердить email пользователя
        user = self.db.query(User).filter(User.id == verification.user_id).first()
        if not user:
            return False, "Пользователь не найден"

        user.email_verified = True
        user.verification_token = None  # Очистить токен из модели User

        # Записать в аудит
        self.log_action(
            user_id=user.id,
            action="email_verified",
            status="success",
            details={"email": verification.email}
        )

        self.db.commit()
        return True, None

    # ==================== User Registration ====================

    def register_user(
        self,
        email: str,
        name: str,
        password: str,
        role: str = "junior_lawyer",
        subscription_tier: str = "demo",
        send_verification: bool = True
    ) -> Tuple[Optional[User], Optional[str]]:
        """
        Register new user

        Args:
            email: User email
            name: User name
            password: Plain text password
            role: User role
            subscription_tier: Subscription tier
            send_verification: Send email verification

        Returns:
            (User object, error message if failed)
        """
        # Check if email already exists
        existing = self.db.query(User).filter(User.email == email).first()
        if existing:
            return None, "Email already registered"

        # Validate password strength
        is_valid, error = self.validate_password_strength(password)
        if not is_valid:
            return None, error

        # Hash password
        password_hash = self.hash_password(password)

        # Create user
        user = User(
            email=email,
            name=name,
            password_hash=password_hash,
            role=role,
            subscription_tier=subscription_tier,
            email_verified=not send_verification,  # Skip verification for demo
            active=True
        )

        self.db.add(user)
        self.db.flush()

        # Create email verification record
        if send_verification:
            self.create_email_verification(user.id, email)

        # Log registration
        self.log_action(
            user_id=user.id,
            action="user_registered",
            status="success",
            details={"role": role, "tier": subscription_tier}
        )

        self.db.commit()

        return user, None

    # ==================== User Login ====================

    def login_user(
        self,
        email: str,
        password: str,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
        """
        Login user and create session

        Args:
            email: User email
            password: Plain text password
            ip_address: Client IP address
            user_agent: User agent string

        Returns:
            (login_data dict, error message if failed)
        """
        # Find user
        user = self.db.query(User).filter(User.email == email).first()

        if not user:
            self._record_login_attempt(email, False, ip_address, user_agent, "user_not_found")
            return None, "Invalid email or password"

        # Check if account is locked (ensure_aware: locked_until из БД naive —
        # см. User.is_active; иначе сравнение с aware-now падает TypeError → 500)
        _locked_until = ensure_aware(user.locked_until)
        if _locked_until and _locked_until > datetime.now(timezone.utc):
            time_left = int((_locked_until - datetime.now(timezone.utc)).total_seconds() / 60)
            return None, f"Account is locked. Try again in {time_left} minutes."

        # Verify password
        if not self.verify_password(password, user.password_hash):
            # Atomic increment to prevent race condition with concurrent login attempts
            self.db.query(User).filter(User.id == user.id).update(
                {User.failed_login_attempts: User.failed_login_attempts + 1}
            )
            self.db.commit()
            # Re-read to get actual count after atomic update
            self.db.refresh(user)

            # Lock account after max attempts
            if user.failed_login_attempts >= self.MAX_LOGIN_ATTEMPTS:
                user.locked_until = datetime.now(timezone.utc) + timedelta(
                    minutes=self.ACCOUNT_LOCK_DURATION_MINUTES
                )
                self.db.commit()

                self._record_login_attempt(email, False, ip_address, user_agent, "account_locked")

                return None, "Account locked due to too many failed attempts"

            self._record_login_attempt(email, False, ip_address, user_agent, "wrong_password")

            return None, "Invalid email or password"

        # Check if email is verified
        if not user.email_verified:
            self._record_login_attempt(email, False, ip_address, user_agent, "email_not_verified")
            return None, "Please verify your email address first"

        # Check if account is active
        if not user.is_active():
            self._record_login_attempt(email, False, ip_address, user_agent, "account_inactive")
            return None, "Account is not active"

        # Reset failed attempts on successful login
        user.failed_login_attempts = 0
        user.locked_until = None

        # Update last login
        user.last_login = datetime.now(timezone.utc)
        user.last_ip = ip_address
        user.login_count += 1

        # Reset daily limits if needed
        user.reset_daily_limits()

        # Create tokens
        access_token = self.create_access_token(user.id)
        refresh_token = self.create_refresh_token(user.id)

        # Create session
        session = UserSession(
            user_id=user.id,
            access_token_hash=self._hash_token(access_token),
            refresh_token=refresh_token,
            ip_address=ip_address,
            user_agent=user_agent,
            expires_at=datetime.now(timezone.utc) + timedelta(days=self.REFRESH_TOKEN_EXPIRE_DAYS)
        )

        self.db.add(session)

        # Log successful login
        self.log_action(
            user_id=user.id,
            action="login",
            status="success",
            ip_address=ip_address,
            user_agent=user_agent
        )

        self._record_login_attempt(email, True, ip_address, user_agent)

        self.db.commit()

        return {
            "user": {
                "id": user.id,
                "email": user.email,
                "name": user.name,
                "role": user.role,
                "subscription_tier": user.subscription_tier
            },
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "Bearer",
            "expires_in": self.ACCESS_TOKEN_EXPIRE_MINUTES * 60
        }, None

    def _record_login_attempt(
        self,
        email: str,
        success: bool,
        ip_address: Optional[str],
        user_agent: Optional[str],
        failure_reason: Optional[str] = None
    ):
        """Record login attempt for security tracking"""
        attempt = LoginAttempt(
            email=email,
            success=success,
            ip_address=ip_address,
            user_agent=user_agent,
            failure_reason=failure_reason
        )
        self.db.add(attempt)

    # ==================== Demo Token Management ====================

    def generate_demo_token(
        self,
        created_by_user_id: str,
        max_contracts: int = 3,
        max_llm_requests: int = 10,
        expires_in_hours: int = 24,
        campaign: Optional[str] = None,
        source: str = "admin_api",
        recipient_email: Optional[str] = None,
        commit: bool = True,
    ) -> DemoToken:
        """
        Generate demo access token

        Args:
            created_by_user_id: ID of admin who created token
            max_contracts: Max contracts for demo user
            max_llm_requests: Max LLM requests for demo user
            expires_in_hours: Token expiration in hours
            campaign: Marketing campaign name
            source: Token source
            recipient_email: Email allowed to activate this token
            commit: Commit immediately or leave transaction to caller

        Returns:
            DemoToken object
        """
        token = secrets.token_urlsafe(32)

        demo_token = DemoToken(
            token=token,
            recipient_email=recipient_email.strip().lower() if recipient_email else None,
            max_contracts=max_contracts,
            max_llm_requests=max_llm_requests,
            expires_in_hours=expires_in_hours,
            expires_at=datetime.now(timezone.utc) + timedelta(hours=expires_in_hours),
            created_by=created_by_user_id,
            source=source,
            campaign=campaign
        )

        self.db.add(demo_token)
        self.db.flush()

        # Log action
        self.log_action(
            user_id=created_by_user_id,
            action="demo_token_created",
            resource_type="demo_token",
            resource_id=demo_token.id,
            status="success",
            details={
                "max_contracts": max_contracts,
                "expires_in_hours": expires_in_hours,
                "campaign": campaign
            }
        )

        if commit:
            self.db.commit()

        return demo_token

    def activate_demo_token(
        self,
        token: str,
        email: str,
        name: str,
        ip_address: Optional[str] = None
    ) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
        """
        Activate demo access using token

        Args:
            token: Demo token string
            email: User email
            name: User name
            ip_address: Client IP

        Returns:
            (activation_data dict, error message if failed)
        """
        # Find and validate token with pessimistic lock to prevent race condition
        demo_token = self.db.query(DemoToken).filter(
            DemoToken.token == token
        ).with_for_update().first()

        if not demo_token:
            return None, "Invalid demo token"

        if not demo_token.can_use():
            return None, "Demo token has expired or has been used"

        normalized_email = email.strip().lower()
        if demo_token.recipient_email and normalized_email != demo_token.recipient_email.lower():
            return None, "Эта демо-ссылка предназначена для другого email"

        # Check if email already registered
        existing = self.db.query(User).filter(func.lower(User.email) == normalized_email).first()
        if existing:
            return None, "Email already registered. Please login instead."

        # Create demo user
        user = User(
            email=normalized_email,
            name=name,
            role='demo',
            subscription_tier='demo',
            is_demo=True,
            demo_expires=demo_token.expires_at,
            demo_token=token,
            email_verified=True,  # Skip verification for demo
            active=True,
            contracts_today=0,
            llm_requests_today=0,
            llm_requests_total=0,
        )

        self.db.add(user)
        self.db.flush()

        # Mark token as used
        demo_token.used = True
        demo_token.used_by_user_id = user.id
        demo_token.used_at = datetime.now(timezone.utc)
        demo_token.uses_count += 1

        # Create access token
        access_token = self.create_access_token(user.id)
        refresh_token = self.create_refresh_token(user.id)

        # Create session
        session = UserSession(
            user_id=user.id,
            access_token_hash=self._hash_token(access_token),
            refresh_token=refresh_token,
            ip_address=ip_address,
            expires_at=demo_token.expires_at
        )

        self.db.add(session)

        # Log activation
        self.log_action(
            user_id=user.id,
            action="demo_activated",
            resource_type="demo_token",
            resource_id=demo_token.id,
            status="success",
            ip_address=ip_address,
            details={"token": token[:10] + "..."}
        )

        self.db.commit()

        return {
            "user": {
                "id": user.id,
                "email": user.email,
                "name": user.name,
                "role": user.role,
                "is_demo": True,
                "demo_expires": user.demo_expires.isoformat()
            },
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "Bearer",
            "expires_at": demo_token.expires_at.isoformat()
        }, None

    # ==================== Session Management ====================

    def refresh_session(self, refresh_token: str) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
        """
        Refresh access token using refresh token (rotation).

        Implements one-time use refresh tokens:
        - Old session is revoked, new session is created
        - If a revoked refresh token is reused, ALL user sessions are
          revoked (token theft detection)

        Args:
            refresh_token: Refresh token string

        Returns:
            (new_tokens dict, error message if failed)
        """
        # Verify refresh token (signature, expiry, iss, aud)
        payload = self.verify_token(refresh_token, token_type="refresh")
        if not payload:
            return None, "Недействительный или просроченный refresh-токен"

        user_id = payload.get("user_id")

        # Find session by refresh token
        session = self.db.query(UserSession).filter(
            UserSession.refresh_token == refresh_token,
            UserSession.user_id == user_id
        ).first()

        if not session:
            return None, "Сессия не найдена"

        # --- Token theft detection ---
        # If the refresh token has already been revoked, someone is reusing
        # a token that was already rotated. Revoke ALL sessions for this user.
        if session.revoked:
            self.db.query(UserSession).filter(
                UserSession.user_id == user_id,
                UserSession.revoked == False
            ).update({
                "revoked": True,
                "revoked_at": datetime.now(timezone.utc),
                "revoke_reason": "refresh_token_reuse_detected"
            })

            self.log_action(
                user_id=user_id,
                action="refresh_token_reuse_detected",
                status="failed",
                severity="critical",
                details={"revoked_session_id": session.id}
            )

            self.db.commit()
            return None, "Обнаружено повторное использование токена. Все сессии отозваны. Войдите заново."

        # Check session validity (expiry)
        if not session.is_valid():
            return None, "Сессия истекла или недействительна"

        # --- Revoke old session ---
        session.revoked = True
        session.revoked_at = datetime.now(timezone.utc)
        session.revoke_reason = "refresh_token_rotation"

        # --- Find user for response ---
        user = self.db.query(User).filter(User.id == user_id).first()
        if not user or not user.is_active():
            self.db.commit()
            return None, "Пользователь не найден или неактивен"

        # --- Create new tokens ---
        new_access_token = self.create_access_token(user_id)
        new_refresh_token = self.create_refresh_token(user_id)

        # --- Create new session ---
        new_session = UserSession(
            user_id=user_id,
            access_token_hash=self._hash_token(new_access_token),
            refresh_token=new_refresh_token,
            ip_address=session.ip_address,
            user_agent=session.user_agent,
            expires_at=datetime.now(timezone.utc) + timedelta(days=self.REFRESH_TOKEN_EXPIRE_DAYS)
        )
        self.db.add(new_session)

        self.log_action(
            user_id=user_id,
            action="token_refreshed",
            status="success",
            details={"old_session_id": session.id, "new_session_id": new_session.id}
        )

        self.db.commit()

        return {
            "user": {
                "id": user.id,
                "email": user.email,
                "name": user.name,
                "role": user.role,
                "subscription_tier": user.subscription_tier
            },
            "access_token": new_access_token,
            "refresh_token": new_refresh_token,
            "token_type": "Bearer",
            "expires_in": self.ACCESS_TOKEN_EXPIRE_MINUTES * 60
        }, None

    def logout_user(self, access_token: str) -> bool:
        """
        Logout user by revoking session

        Args:
            access_token: Access token to revoke

        Returns:
            True if successful
        """
        session = self.db.query(UserSession).filter(
            UserSession.access_token_hash == self._hash_token(access_token)
        ).first()

        if session:
            session.revoked = True
            session.revoked_at = datetime.now(timezone.utc)
            session.revoke_reason = "user_logout"

            # Log logout
            self.log_action(
                user_id=session.user_id,
                action="logout",
                status="success"
            )

            self.db.commit()
            return True

        return False

    # ==================== Audit Logging ====================

    def log_action(
        self,
        user_id: Optional[str],
        action: str,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        status: str = "success",
        error_message: Optional[str] = None,
        details: Optional[Dict] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        severity: str = "info"
    ):
        """
        Log action to audit log

        Args:
            user_id: User ID
            action: Action name
            resource_type: Resource type (contract, user, etc.)
            resource_id: Resource ID
            status: Action status (success, failed, pending)
            error_message: Error message if failed
            details: Additional details (JSON)
            ip_address: Client IP
            user_agent: User agent
            severity: Log severity (info, warning, error, critical)
        """
        log = AuditLog(
            user_id=user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            status=status,
            error_message=error_message,
            details=details,
            ip_address=ip_address,
            user_agent=user_agent,
            severity=severity
        )

        self.db.add(log)

    # ==================== User Management (Admin) ====================

    def create_user_as_admin(
        self,
        email: str,
        name: str,
        role: str,
        subscription_tier: str = "demo",
        admin_user_id: str = None
    ) -> Tuple[Optional[User], Optional[str], Optional[str]]:
        """
        Create user as admin (generates temporary password)

        Returns:
            (User object, temporary_password, error message)
        """
        # Check if email exists
        existing = self.db.query(User).filter(User.email == email).first()
        if existing:
            return None, None, "Email already registered"

        # Generate temporary password
        temp_password = secrets.token_urlsafe(12)
        password_hash = self.hash_password(temp_password)

        # Create user
        user = User(
            email=email,
            name=name,
            role=role,
            subscription_tier=subscription_tier,
            password_hash=password_hash,
            email_verified=False,  # Will verify on first login/password change
            active=True
        )

        self.db.add(user)
        self.db.flush()

        # Log action
        if admin_user_id:
            self.log_action(
                user_id=admin_user_id,
                action="user_created_by_admin",
                resource_type="user",
                resource_id=user.id,
                status="success",
                details={"email": email, "role": role}
            )

        self.db.commit()

        return user, temp_password, None

    def update_user_role(
        self,
        user_id: str,
        new_role: str,
        admin_user_id: str,
        subscription_tier: Optional[str] = None
    ) -> Tuple[bool, Optional[str]]:
        """
        Update user role (admin only)

        Returns:
            (success, error message)
        """
        user = self.db.query(User).filter(User.id == user_id).first()
        if not user:
            return False, "User not found"

        old_role = user.role
        user.role = new_role

        if subscription_tier:
            user.subscription_tier = subscription_tier

        # Log action
        self.log_action(
            user_id=admin_user_id,
            action="user_role_changed",
            resource_type="user",
            resource_id=user_id,
            status="success",
            details={
                "old_role": old_role,
                "new_role": new_role,
                "subscription_tier": subscription_tier
            }
        )

        self.db.commit()

        return True, None

    def list_users(
        self,
        page: int = 1,
        limit: int = 50,
        role: Optional[str] = None,
        search: Optional[str] = None,
        is_demo: Optional[bool] = None
    ) -> Dict[str, Any]:
        """
        List users with filtering and pagination

        Returns:
            Dict with users list and pagination info
        """
        query = self.db.query(User)

        if role:
            query = query.filter(User.role == role)

        if is_demo is not None:
            query = query.filter(User.is_demo == is_demo)

        if search:
            # Escape SQL LIKE wildcards to prevent pattern injection
            safe_search = search.replace('%', r'\%').replace('_', r'\_')
            query = query.filter(
                or_(
                    User.email.ilike(f"%{safe_search}%", escape='\\'),
                    User.name.ilike(f"%{safe_search}%", escape='\\')
                )
            )

        total = query.count()
        users = query.order_by(User.created_at.desc()).offset((page - 1) * limit).limit(limit).all()

        return {
            "total": total,
            "page": page,
            "limit": limit,
            "pages": (total + limit - 1) // limit,
            "users": [
                {
                    "id": u.id,
                    "email": u.email,
                    "name": u.name,
                    "role": u.role,
                    "subscription_tier": u.subscription_tier,
                    "active": u.active,
                    "is_demo": u.is_demo,
                    "email_verified": u.email_verified,
                    "created_at": u.created_at.isoformat(),
                    "last_login": u.last_login.isoformat() if u.last_login else None,
                    "login_count": u.login_count
                }
                for u in users
            ]
        }

    # ==================== Analytics ====================

    def get_analytics(self) -> Dict[str, Any]:
        """Get system analytics"""

        total_users = self.db.query(User).count()
        active_users = self.db.query(User).filter(User.active == True).count()
        demo_users = self.db.query(User).filter(User.is_demo == True).count()

        # Users by role
        users_by_role = dict(
            self.db.query(User.role, func.count(User.id))
            .group_by(User.role)
            .all()
        )

        # Active last week
        week_ago = datetime.now(timezone.utc) - timedelta(days=7)
        active_last_week = self.db.query(User).filter(
            User.last_login >= week_ago
        ).count()

        # Demo conversions (demo users who became paid)
        demo_converted = self.db.query(User).filter(
            and_(
                User.is_demo == False,
                User.subscription_tier != 'demo'
            )
        ).count()

        return {
            "total_users": total_users,
            "active_users": active_users,
            "demo_users": demo_users,
            "users_by_role": users_by_role,
            "active_last_week": active_last_week,
            "demo_converted": demo_converted,
            "conversion_rate": (demo_converted / demo_users * 100) if demo_users > 0 else 0
        }

    # ==================== Password Reset ====================

    def request_password_reset(
        self,
        email: str,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> Tuple[Optional[str], Optional[str]]:
        """
        Create a password reset request.

        Generates a secure token, stores its SHA-256 hash in the database,
        and returns the raw (unhashed) token so it can be sent to the user.

        Args:
            email: User email
            ip_address: Client IP address
            user_agent: User agent string

        Returns:
            (raw_token or None, error_message or None)
        """
        user = self.db.query(User).filter(User.email == email).first()
        if not user:
            # Return success-like response to prevent email enumeration
            return None, None

        # Invalidate any existing unused reset requests for this user
        self.db.query(PasswordResetRequest).filter(
            PasswordResetRequest.user_id == user.id,
            PasswordResetRequest.used == False
        ).delete()

        # Generate token and store only the hash
        token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(token.encode()).hexdigest()

        reset_request = PasswordResetRequest(
            user_id=user.id,
            token=token_hash,
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
            ip_address=ip_address,
            user_agent=user_agent
        )
        self.db.add(reset_request)

        self.log_action(
            user_id=user.id,
            action="password_reset_requested",
            status="success",
            ip_address=ip_address,
            user_agent=user_agent
        )

        self.db.commit()

        # Return the raw token — caller sends it to the user via email
        return token, None

    def reset_password(
        self,
        token: str,
        new_password: str,
        ip_address: Optional[str] = None
    ) -> Tuple[bool, Optional[str]]:
        """
        Reset password using a reset token.

        Hashes the incoming token and compares with the stored hash.

        Args:
            token: Raw reset token (as received by the user)
            new_password: New password

        Returns:
            (success, error_message)
        """
        # Hash the incoming token to compare with stored hash
        token_hash = hashlib.sha256(token.encode()).hexdigest()

        reset_request = self.db.query(PasswordResetRequest).filter(
            PasswordResetRequest.token == token_hash
        ).first()

        if not reset_request:
            return False, "Неверный или просроченный токен сброса пароля"

        if not reset_request.is_valid():
            return False, "Токен сброса пароля истёк или уже использован"

        # Validate new password strength
        is_valid, error = self.validate_password_strength(new_password)
        if not is_valid:
            return False, error

        # Find user
        user = self.db.query(User).filter(User.id == reset_request.user_id).first()
        if not user:
            return False, "Пользователь не найден"

        # Update password
        user.password_hash = self.hash_password(new_password)

        # Mark reset request as used
        reset_request.used = True
        reset_request.used_at = datetime.now(timezone.utc)

        # Reset failed login attempts and unlock account
        user.failed_login_attempts = 0
        user.locked_until = None

        # Revoke all existing sessions (force re-login with new password)
        self.db.query(UserSession).filter(
            UserSession.user_id == user.id,
            UserSession.revoked == False
        ).update({
            "revoked": True,
            "revoked_at": datetime.now(timezone.utc),
            "revoke_reason": "password_reset"
        })

        self.log_action(
            user_id=user.id,
            action="password_reset_completed",
            status="success",
            ip_address=ip_address
        )

        self.db.commit()

        return True, None
