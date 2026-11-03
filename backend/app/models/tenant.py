"""Tenant model — represents a customer workspace / organisation."""
import uuid
from datetime import datetime, timezone
from enum import Enum

from sqlalchemy import String, DateTime, Enum as SAEnum, Text, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..extensions import db


class TenantStatus(str, Enum):
    ACTIVE = "active"
    SUSPENDED = "suspended"
    DELETED = "deleted"


class Tenant(db.Model):
    """A customer workspace.

    Every tenant-owned record in the system carries a tenant_id FK to
    this table. All tenant-scoped queries must derive tenant context from
    the authenticated user's active membership — never from a
    client-supplied tenant_id alone.
    """

    __tablename__ = "tenants"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    timezone: Mapped[str] = mapped_column(String(64), default="UTC", nullable=False)
    status: Mapped[TenantStatus] = mapped_column(
        SAEnum(TenantStatus, name="tenant_status"), default=TenantStatus.ACTIVE, nullable=False
    )
    # Brand settings
    brand_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    brand_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    brand_voice: Mapped[str | None] = mapped_column(Text, nullable=True)
    logo_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    website_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)

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
        "TenantMembership", back_populates="tenant", lazy="dynamic"
    )
    invitations: Mapped[list["Invitation"]] = relationship(  # noqa: F821
        "Invitation", back_populates="tenant", lazy="dynamic"
    )
    subscription: Mapped["Subscription | None"] = relationship(  # noqa: F821
        "Subscription", back_populates="tenant", uselist=False
    )

    def __repr__(self) -> str:
        return f"<Tenant {self.slug}>"
