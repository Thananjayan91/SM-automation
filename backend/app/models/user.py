"""User model — platform-level identity."""
import uuid
from datetime import datetime, timezone

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, VerificationError, InvalidHashError
from flask_login import UserMixin
from sqlalchemy import String, Boolean, DateTime, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..extensions import db

_ph = PasswordHasher()


class User(UserMixin, db.Model):
    """Represents a platform user account.

    A single user may belong to multiple tenants via TenantMembership.
    Authentication is handled at the platform level; authorization is
    always evaluated in the context of a specific tenant.
    """

    __tablename__ = "users"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_platform_admin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    email_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    memberships: Mapped[list["TenantMembership"]] = relationship(  # noqa: F821
        "TenantMembership", back_populates="user", lazy="dynamic"
    )
    sessions: Mapped[list["UserSession"]] = relationship(  # noqa: F821
        "UserSession", back_populates="user", lazy="dynamic"
    )

    def set_password(self, password: str) -> None:
        """Hash and store password using Argon2id."""
        self.password_hash = _ph.hash(password)

    def check_password(self, password: str) -> bool:
        """Verify a plaintext password against the stored hash.

        Returns True if the password matches, False otherwise.
        Never raises exceptions to callers.
        """
        try:
            _ph.verify(self.password_hash, password)
            # Rehash if parameters have changed
            if _ph.check_needs_rehash(self.password_hash):
                self.password_hash = _ph.hash(password)
            return True
        except (VerifyMismatchError, VerificationError, InvalidHashError):
            return False

    def get_id(self) -> str:
        """Return user ID as string for Flask-Login."""
        return self.id

    def __repr__(self) -> str:
        return f"<User {self.email}>"
