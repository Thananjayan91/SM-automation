"""Authentication service.

Handles user registration, login, logout, password reset and session
management. All password operations use Argon2id via the User model.
"""
import hashlib
import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

import structlog
from flask import request
from sqlalchemy.exc import IntegrityError

from ..extensions import db
from ..models.user import User
from ..models.session import UserSession
from ..models.audit_log import AuditLog

logger = structlog.get_logger(__name__)

# Password reset token TTL
PASSWORD_RESET_TTL_HOURS = 2


def _hash_token(token: str) -> str:
    """Hash a token for safe storage using SHA-256."""
    return hashlib.sha256(token.encode()).hexdigest()


def register_user(
    email: str,
    password: str,
    name: str,
) -> tuple[Optional[User], Optional[str]]:
    """Register a new user account.

    Args:
        email: User's email address (must be unique).
        password: Plaintext password (will be hashed).
        name: Display name.

    Returns:
        Tuple of (user, error_message). error_message is None on success.
    """
    email = email.lower().strip()

    # Check for existing user
    existing = User.query.filter_by(email=email).first()
    if existing:
        return None, "An account with this email address already exists."

    user = User(email=email, name=name.strip())
    user.set_password(password)

    db.session.add(user)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return None, "An account with this email address already exists."

    _create_audit_log(
        action="user.registered",
        user_id=user.id,
        details={"email": email},
    )

    logger.info("user_registered", user_id=user.id, email=email)
    return user, None


def authenticate_user(email: str, password: str) -> Optional[User]:
    """Verify credentials and return the User on success.

    Returns None if credentials are invalid or account is inactive.
    Does NOT create a session — call create_web_session() after.
    """
    email = email.lower().strip()
    user = User.query.filter_by(email=email).first()

    if not user:
        _dummy_check(password)
        return None

    if not user.check_password(password):
        _create_audit_log(
            action="auth.login_failed",
            user_id=user.id,
            details={"reason": "invalid_password"},
        )
        return None

    if not user.is_active:
        return None

    return user


def _dummy_check(password: str) -> None:
    """Perform a dummy check to mitigate timing-based user enumeration."""
    import argon2
    ph = argon2.PasswordHasher()
    try:
        ph.verify("$argon2id$v=19$m=65536,t=3,p=4$dummy", password)
    except Exception:
        pass


def create_web_session(user: User) -> None:
    """Record a web session audit log entry."""
    _create_audit_log(
        action="auth.login",
        user_id=user.id,
        details={"method": "web"},
    )
    logger.info("user_logged_in", user_id=user.id)


def logout_user_session(user: User) -> None:
    """Record a logout event."""
    _create_audit_log(
        action="auth.logout",
        user_id=user.id,
    )
    logger.info("user_logged_out", user_id=user.id)


def generate_password_reset_token(email: str) -> Optional[str]:
    """Generate a password-reset token for a given email.

    Returns the raw token to be sent in an email, or None if no
    active account exists for that email. Always behaves consistently
    externally to prevent user enumeration.
    """
    email = email.lower().strip()
    user = User.query.filter_by(email=email, is_active=True).first()

    if not user:
        return None

    raw_token = secrets.token_urlsafe(48)
    token_hash = _hash_token(raw_token)

    session = UserSession(
        user_id=user.id,
        token_hash=f"pwd_reset:{token_hash}",
        expires_at=datetime.now(timezone.utc) + timedelta(hours=PASSWORD_RESET_TTL_HOURS),
        user_agent=request.headers.get("User-Agent") if request else None,
        ip_address=request.remote_addr if request else None,
    )
    db.session.add(session)
    db.session.commit()

    _create_audit_log(
        action="auth.password_reset_requested",
        user_id=user.id,
        details={"email": email},
    )

    return raw_token


def consume_password_reset_token(token: str, new_password: str) -> tuple[bool, Optional[str]]:
    """Validate a password-reset token and update the password.

    Returns (success, error_message).
    """
    token_hash = f"pwd_reset:{_hash_token(token)}"
    session = UserSession.query.filter_by(token_hash=token_hash).first()

    if not session or not session.is_valid:
        return False, "This reset link is invalid or has expired."

    user = db.session.get(User, session.user_id)
    if not user or not user.is_active:
        return False, "Account not found."

    user.set_password(new_password)
    session.revoke()
    db.session.commit()

    _create_audit_log(
        action="auth.password_reset_completed",
        user_id=user.id,
    )

    return True, None


def _create_audit_log(
    action: str,
    user_id: Optional[str] = None,
    tenant_id: Optional[str] = None,
    details: Optional[dict] = None,
) -> None:
    """Create an immutable audit log entry."""
    try:
        log = AuditLog(
            tenant_id=tenant_id,
            user_id=user_id,
            action=action,
            ip_address=request.remote_addr if request else None,
            user_agent=request.headers.get("User-Agent") if request else None,
            details_json=details,
        )
        db.session.add(log)
        db.session.flush()
    except Exception as exc:
        logger.warning("audit_log_failed", action=action, error=str(exc))
