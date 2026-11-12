"""Media asset model — uploaded and AI-generated image assets."""
import uuid
from datetime import datetime, timezone
from enum import Enum

from sqlalchemy import String, Integer, DateTime, ForeignKey, Text, JSON, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..extensions import db


class MediaSourceType(str, Enum):
    UPLOADED = "uploaded"
    AI_GENERATED = "ai_generated"
    STOCK = "stock"
    VIDEO_GENERATED = "video_generated"


class MediaAsset(db.Model):
    """Media asset stored in object storage or local media disk."""

    __tablename__ = "media_assets"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    created_by: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    storage_key: Mapped[str] = mapped_column(String(512), nullable=False)
    storage_url: Mapped[str] = mapped_column(String(2048), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(100), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    height: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source_type: Mapped[MediaSourceType] = mapped_column(
        SAEnum(MediaSourceType, name="media_source_type"),
        default=MediaSourceType.UPLOADED,
        nullable=False,
    )
    rights_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    labels_json: Mapped[list | None] = mapped_column(JSON, default=list, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False, index=True
    )

    # Relationships
    tenant: Mapped["Tenant"] = relationship("Tenant")  # noqa: F821
    creator: Mapped["User | None"] = relationship("User")  # noqa: F821
    post_attachments: Mapped[list["PostMedia"]] = relationship(  # noqa: F821
        "PostMedia", back_populates="media_asset", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<MediaAsset {self.original_filename} ({self.mime_type})>"

