"""SocialAccount model — connected social platforms (Facebook, Instagram, Threads, TikTok)."""
import uuid
from datetime import datetime, timezone
from enum import Enum

from sqlalchemy import String, DateTime, ForeignKey, Text, JSON, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..extensions import db
from .post import Platform


class SocialAccountStatus(str, Enum):
    CONNECTED = "connected"
    EXPIRED = "expired"
    DISCONNECTED = "disconnected"
    ERROR = "error"


class SocialAccount(db.Model):
    """Connected Facebook Page, Instagram account, Threads, or TikTok profile."""

    __tablename__ = "social_accounts"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    platform: Mapped[Platform] = mapped_column(
        SAEnum(Platform, name="platform"), nullable=False
    )
    platform_account_id: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    account_handle: Mapped[str | None] = mapped_column(String(255), nullable=True)
    avatar_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    encrypted_access_token: Mapped[str | None] = mapped_column(Text, nullable=True)
    token_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    permissions_json: Mapped[list | None] = mapped_column(JSON, nullable=True)

    status: Mapped[SocialAccountStatus] = mapped_column(
        SAEnum(SocialAccountStatus, name="social_account_status"),
        default=SocialAccountStatus.CONNECTED,
        nullable=False,
    )
    connected_by: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

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
    tenant: Mapped["Tenant"] = relationship("Tenant")  # noqa: F821
    connected_user: Mapped["User | None"] = relationship("User")  # noqa: F821

    def set_access_token(self, raw_token: str | None) -> None:
        """Encrypt and store access token."""
        from ..services.security_service import encrypt_credential
        self.encrypted_access_token = encrypt_credential(raw_token) if raw_token else None

    def get_access_token(self) -> str | None:
        """Decrypt and return raw access token for API calls."""
        from ..services.security_service import decrypt_credential
        return decrypt_credential(self.encrypted_access_token) if self.encrypted_access_token else None

    def is_token_expired(self) -> bool:
        """Check if token is expired."""
        if not self.token_expires_at:
            return False
        return self.token_expires_at <= datetime.now(timezone.utc)

    def __repr__(self) -> str:
        return f"<SocialAccount {self.platform}:{self.display_name} ({self.status})>"

