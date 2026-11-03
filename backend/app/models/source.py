"""Source model — content sources submitted for AI generation."""
import uuid
from datetime import datetime, timezone
from enum import Enum

from sqlalchemy import String, DateTime, ForeignKey, Text, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..extensions import db


class SourceType(str, Enum):
    URL = "url"
    MANUAL = "manual"
    IMAGE_UPLOAD = "image_upload"


class SourceStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    READY = "ready"
    FAILED = "failed"


class Source(db.Model):
    """User-submitted source material for a story/post.

    Treated as untrusted external content. URLs undergo SSRF validation.
    """

    __tablename__ = "sources"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    created_by: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    source_type: Mapped[SourceType] = mapped_column(
        SAEnum(SourceType, name="source_type"), nullable=False
    )
    source_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    raw_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    headline: Mapped[str | None] = mapped_column(String(512), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    tone_instruction: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[SourceStatus] = mapped_column(
        SAEnum(SourceStatus, name="source_status"), default=SourceStatus.PENDING, nullable=False
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

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
    creator: Mapped["User | None"] = relationship("User")  # noqa: F821
    posts: Mapped[list["Post"]] = relationship("Post", back_populates="source", lazy="dynamic")  # noqa: F821

    def __repr__(self) -> str:
        return f"<Source {self.id} type={self.source_type} status={self.status}>"

