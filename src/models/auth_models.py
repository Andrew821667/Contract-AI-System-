"""
Enhanced Authentication Models for Contract-AI-System

Includes:
- Extended User model with security features
- DemoToken for link-based demo access
- UserSession for JWT session management
- AuditLog for compliance and security tracking
"""

from datetime import datetime, timedelta
from typing import Optional
from sqlalchemy import (
    Boolean, Column, String, Text, Integer, Float,
    DateTime, ForeignKey, CheckConstraint, UniqueConstraint, JSON, Index
)
from sqlalchemy.orm import relationship
from .database import Base, generate_uuid


class User(Base):
    """Extended user model with comprehensive security features"""
    __tablename__ = "users"
    __table_args__ = {"extend_existing": True}

    # Core fields
    id = Column(String(36), primary_key=True, default=generate_uuid)
    email = Column(String(255), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=False)
    role = Column(String(50), nullable=False, index=True)  # admin, senior_lawyer, lawyer, junior_lawyer, demo

    # Security
    password_hash = Column(String(255))  # bcrypt hash
    email_verified = Column(Boolean, default=False, index=True)
    verification_token = Column(String(255), unique=True, index=True)
    reset_token = Column(String(255), unique=True)
    reset_token_expires = Column(DateTime)

    # Two-Factor Authentication (2FA)
    two_factor_enabled = Column(Boolean, default=False)
    two_factor_secret = Column(String(255))  # TOTP secret
    backup_codes = Column(JSON)  # Array of backup codes

    # Status and subscription
    active = Column(Boolean, default=True, index=True)
    subscription_tier = Column(String(50), default='demo', index=True)  # demo, basic, pro, enterprise
    subscription_expires = Column(DateTime)
    subscription_auto_renew = Column(Boolean, default=False)

    # Demo access
    is_demo = Column(Boolean, default=False, index=True)
    demo_expires = Column(DateTime)
    demo_token = Column(String(255), unique=True, index=True)

    # Usage metrics (for rate limiting)
    contracts_today = Column(Integer, default=0)
    llm_requests_today = Column(Integer, default=0)
    last_reset_date = Column(DateTime, default=datetime.utcnow)

    # Audit and tracking
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_login = Column(DateTime, index=True)
    last_ip = Column(String(45))
    login_count = Column(Integer, default=0)

    # Failed login tracking (security)
    failed_login_attempts = Column(Integer, default=0)
    locked_until = Column(DateTime)  # Account lock after too many failed attempts

    # Preferences
    preferences = Column(JSON)  # User preferences (language, theme, etc.)
    notification_settings = Column(JSON)  # Email, push notifications settings

    # Relationships
    sessions = relationship("UserSession", back_populates="user", cascade="all, delete-orphan")
    audit_logs = relationship("AuditLog", back_populates="user", cascade="all, delete-orphan")
    created_demo_tokens = relationship("DemoToken", foreign_keys="DemoToken.created_by", back_populates="creator")
    used_demo_token_rel = relationship("DemoToken", foreign_keys="DemoToken.used_by_user_id", back_populates="used_by_user")

    # From original model
    templates = relationship("Template", back_populates="creator")
    assigned_tasks = relationship("ReviewTask", foreign_keys="ReviewTask.assigned_to", back_populates="assignee")
    export_logs = relationship("ExportLog", back_populates="user")

    __table_args__ = (
        CheckConstraint(
            role.in_(['admin', 'senior_lawyer', 'lawyer', 'junior_lawyer', 'demo']),
            name='check_user_role'
        ),
        CheckConstraint(
            subscription_tier.in_(['demo', 'basic', 'pro', 'enterprise']),
            name='check_subscription_tier'
        ),
        Index('idx_user_email_active', 'email', 'active'),
        Index('idx_user_demo_expires', 'is_demo', 'demo_expires'),
    )

    def __repr__(self):
        return f"<User(id={self.id}, email={self.email}, role={self.role}, tier={self.subscription_tier})>"

    def is_active(self) -> bool:
        """Check if user account is active"""
        if not self.active:
            return False
        if self.locked_until and self.locked_until > datetime.utcnow():
            return False
        if self.is_demo and self.demo_expires and self.demo_expires < datetime.utcnow():
            return False
        if self.subscription_expires and self.subscription_expires < datetime.utcnow():
            return False
        return True

    def reset_daily_limits(self):
        """Reset daily usage limits"""
        today = datetime.utcnow().date()
        if not self.last_reset_date or self.last_reset_date.date() < today:
            self.contracts_today = 0
            self.llm_requests_today = 0
            self.last_reset_date = datetime.utcnow()


class UserSession(Base):
    """User sessions with JWT tokens"""
    __tablename__ = "user_sessions"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(36), ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)

    # Tokens
    access_token = Column(String(500), unique=True, nullable=False, index=True)
    refresh_token = Column(String(500), unique=True, nullable=False, index=True)
    token_type = Column(String(20), default='Bearer')

    # Session metadata
    ip_address = Column(String(45))
    user_agent = Column(Text)
    device_info = Column(JSON)  # Browser, OS, device type

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    expires_at = Column(DateTime, nullable=False, index=True)
    last_activity = Column(DateTime, default=datetime.utcnow)

    # Status
    revoked = Column(Boolean, default=False, index=True)
    revoked_at = Column(DateTime)
    revoke_reason = Column(String(255))

    # Relationships
    user = relationship("User", back_populates="sessions")

    __table_args__ = (
        Index('idx_session_user_active', 'user_id', 'revoked', 'expires_at'),
    )

    def __repr__(self):
        return f"<UserSession(id={self.id}, user_id={self.user_id}, expires={self.expires_at})>"

    def is_valid(self) -> bool:
        """Check if session is still valid"""
        if self.revoked:
            return False
        if self.expires_at < datetime.utcnow():
            return False
        return True


class DemoToken(Base):
    """Tokens for demo access via links"""
    __tablename__ = "demo_tokens"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    token = Column(String(255), unique=True, nullable=False, index=True)

    # Demo access configuration
    max_contracts = Column(Integer, default=3)
    max_llm_requests = Column(Integer, default=10)
    max_file_size_mb = Column(Integer, default=5)
    expires_in_hours = Column(Integer, default=24)

    # Features enabled for demo
    features = Column(JSON)  # List of enabled features

    # Usage tracking
    used = Column(Boolean, default=False, index=True)
    used_by_user_id = Column(String(36), ForeignKey('users.id'))
    used_at = Column(DateTime)
    uses_count = Column(Integer, default=0)  # For multi-use tokens
    max_uses = Column(Integer, default=1)  # How many times token can be used

    # Metadata
    created_by = Column(String(36), ForeignKey('users.id'), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    expires_at = Column(DateTime, nullable=False, index=True)

    # Marketing tracking
    source = Column(String(50), index=True)  # 'website', 'admin_panel', 'api', 'landing_page'
    campaign = Column(String(100), index=True)  # UTM campaign
    medium = Column(String(50))  # UTM medium
    referrer = Column(String(255))  # HTTP referrer

    # Notes
    notes = Column(Text)  # Admin notes about this token

    # Relationships
    creator = relationship("User", foreign_keys=[created_by], back_populates="created_demo_tokens")
    used_by_user = relationship("User", foreign_keys=[used_by_user_id], back_populates="used_demo_token_rel")

    __table_args__ = (
        Index('idx_demo_token_valid', 'token', 'used', 'expires_at'),
        Index('idx_demo_source_campaign', 'source', 'campaign'),
    )

    def __repr__(self):
        return f"<DemoToken(id={self.id}, token={self.token[:10]}..., used={self.used})>"

    def is_valid(self) -> bool:
        """Check if demo token is still valid"""
        if self.expires_at < datetime.utcnow():
            return False
        if self.used and self.uses_count >= self.max_uses:
            return False
        return True

    def can_use(self) -> bool:
        """Check if token can be used"""
        return self.is_valid() and (not self.used or self.uses_count < self.max_uses)


class AuditLog(Base):
    """Audit log for security and compliance"""
    __tablename__ = "audit_logs"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(36), ForeignKey('users.id', ondelete='SET NULL'), index=True)

    # Action details
    action = Column(String(100), nullable=False, index=True)  # login, logout, contract_upload, user_created, etc.
    resource_type = Column(String(50), index=True)  # contract, user, template, disagreement
    resource_id = Column(String(36), index=True)

    # Status
    status = Column(String(20), index=True)  # success, failed, pending
    error_message = Column(Text)

    # Additional details
    details = Column(JSON)  # Extra context about the action

    # Request metadata
    ip_address = Column(String(45), index=True)
    user_agent = Column(Text)
    request_method = Column(String(10))  # GET, POST, PUT, DELETE
    request_path = Column(String(500))

    # Timing
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    duration_ms = Column(Integer)  # Action duration in milliseconds

    # Severity (for filtering critical events)
    severity = Column(String(20), index=True)  # info, warning, error, critical

    # Relationships
    user = relationship("User", back_populates="audit_logs")

    __table_args__ = (
        Index('idx_audit_user_action', 'user_id', 'action', 'created_at'),
        Index('idx_audit_resource', 'resource_type', 'resource_id'),
        Index('idx_audit_severity_date', 'severity', 'created_at'),
    )

    def __repr__(self):
        return f"<AuditLog(id={self.id}, action={self.action}, user_id={self.user_id}, status={self.status})>"


class PasswordResetRequest(Base):
    """Password reset requests tracking"""
    __tablename__ = "password_reset_requests"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(36), ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)

    token = Column(String(255), unique=True, nullable=False, index=True)
    expires_at = Column(DateTime, nullable=False, index=True)

    used = Column(Boolean, default=False, index=True)
    used_at = Column(DateTime)

    ip_address = Column(String(45))
    user_agent = Column(Text)

    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index('idx_reset_token_valid', 'token', 'used', 'expires_at'),
    )

    def __repr__(self):
        return f"<PasswordResetRequest(id={self.id}, user_id={self.user_id}, used={self.used})>"

    def is_valid(self) -> bool:
        """Check if reset request is still valid"""
        if self.used:
            return False
        if self.expires_at < datetime.utcnow():
            return False
        return True


class EmailVerification(Base):
    """Email verification tracking"""
    __tablename__ = "email_verifications"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(36), ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)

    email = Column(String(255), nullable=False)
    token = Column(String(255), unique=True, nullable=False, index=True)
    expires_at = Column(DateTime, nullable=False, index=True)

    verified = Column(Boolean, default=False, index=True)
    verified_at = Column(DateTime)

    ip_address = Column(String(45))
    user_agent = Column(Text)

    created_at = Column(DateTime, default=datetime.utcnow)
    resent_count = Column(Integer, default=0)  # Track how many times verification was resent

    __table_args__ = (
        Index('idx_verification_token_valid', 'token', 'verified', 'expires_at'),
    )

    def __repr__(self):
        return f"<EmailVerification(id={self.id}, email={self.email}, verified={self.verified})>"

    def is_valid(self) -> bool:
        """Check if verification is still valid"""
        if self.verified:
            return False
        if self.expires_at < datetime.utcnow():
            return False
        return True


class LoginAttempt(Base):
    """Failed login attempts tracking (for security)"""
    __tablename__ = "login_attempts"

    id = Column(String(36), primary_key=True, default=generate_uuid)

    email = Column(String(255), nullable=False, index=True)
    success = Column(Boolean, default=False, index=True)

    ip_address = Column(String(45), index=True)
    user_agent = Column(Text)

    failure_reason = Column(String(255))  # wrong_password, account_locked, email_not_verified

    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    __table_args__ = (
        Index('idx_login_email_time', 'email', 'created_at'),
        Index('idx_login_ip_time', 'ip_address', 'created_at'),
    )

    def __repr__(self):
        return f"<LoginAttempt(id={self.id}, email={self.email}, success={self.success})>"
