"""Post models — posts, immutable versions, media associations, and target destinations."""
import hashlib
import uuid
from datetime import datetime, timezone
from enum import Enum

from sqlalchemy import String, Integer, DateTime, ForeignKey, Text, JSON, Boolean, Enum as SAEnum, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..extensions import db


class PostStatus(str, Enum):
    DRAFT = "draft"
    GENERATING = "generating"
    READY_FOR_REVIEW = "ready_for_review"
    APPROVED = "approved"
    PUBLISHING = "publishing"
    PUBLISHED = "published"
    PARTIALLY_PUBLISHED = "partially_published"
    FAILED = "failed"
    CANCELLED = "cancelled"
    ARCHIVED = "archived"


class Platform(str, Enum):
    FACEBOOK = "facebook"
    INSTAGRAM = "instagram"
    THREADS = "threads"
    TIKTOK = "tiktok"


class PostTargetStatus(str, Enum):
    PENDING = "pending"
    QUEUED = "queued"
    PUBLISHING = "publishing"
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"


class Post(db.Model):
    """A social media post with versioning and multi-platform destinations."""

    __tablename__ = "posts"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    source_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("sources.id", ondelete="SET NULL"), nullable=True
    )
    created_by: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    approved_by: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    caption: Mapped[str | None] = mapped_column(Text, nullable=True)
    hashtags_json: Mapped[list | None] = mapped_column(JSON, default=list, nullable=True)
    first_comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    first_comment_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    status: Mapped[PostStatus] = mapped_column(
        SAEnum(PostStatus, name="post_status"), default=PostStatus.DRAFT, nullable=False, index=True
    )
    content_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    scheduled_for: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False, index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    tenant: Mapped["Tenant"] = relationship("Tenant")  # noqa: F821
    source: Mapped["Source | None"] = relationship("Source", back_populates="posts")  # noqa: F821
    creator: Mapped["User | None"] = relationship("User", foreign_keys=[created_by])  # noqa: F821
    approver: Mapped["User | None"] = relationship("User", foreign_keys=[approved_by])  # noqa: F821
    media_links: Mapped[list["PostMedia"]] = relationship(
        "PostMedia", back_populates="post", order_by="PostMedia.position", cascade="all, delete-orphan"
    )
    versions: Mapped[list["PostVersion"]] = relationship(
        "PostVersion", back_populates="post", order_by="desc(PostVersion.version_number)", cascade="all, delete-orphan"
    )
    targets: Mapped[list["PostTarget"]] = relationship(
        "PostTarget", back_populates="post", cascade="all, delete-orphan"
    )
    approvals: Mapped[list["Approval"]] = relationship(
        "Approval", back_populates="post", cascade="all, delete-orphan"
    )

    def compute_content_hash(self) -> str:
        """Generate SHA-256 hash of caption and hashtags to guarantee version integrity."""
        raw = f"{self.caption or ''}|{' '.join(self.hashtags_json or [])}|{self.first_comment or ''}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def __repr__(self) -> str:
        return f"<Post {self.id} status={self.status} v={self.content_version}>"


class PostVersion(db.Model):
    """Immutable snapshot of post content at each edit/approval."""

    __tablename__ = "post_versions"
    __table_args__ = (
        UniqueConstraint("post_id", "version_number", name="uq_post_version_number"),
    )

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    post_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("posts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    caption: Mapped[str | None] = mapped_column(Text, nullable=True)
    hashtags_json: Mapped[list | None] = mapped_column(JSON, default=list, nullable=True)
    first_comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )

    # Relationships
    post: Mapped["Post"] = relationship("Post", back_populates="versions")
    approvals: Mapped[list["Approval"]] = relationship("Approval", back_populates="version")


class PostMedia(db.Model):
    """Ordered association between a Post and a MediaAsset."""

    __tablename__ = "post_media"
    __table_args__ = (
        UniqueConstraint("post_id", "media_asset_id", name="uq_post_media_asset"),
    )

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    post_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("posts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    media_asset_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("media_assets.id", ondelete="CASCADE"), nullable=False, index=True
    )
    position: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Relationships
    post: Mapped["Post"] = relationship("Post", back_populates="media_links")
    media_asset: Mapped["MediaAsset"] = relationship("MediaAsset", back_populates="post_attachments")  # noqa: F821


class PostTarget(db.Model):
    """A destination social account targeted by a post."""

    __tablename__ = "post_targets"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    post_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("posts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    social_account_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("social_accounts.id", ondelete="CASCADE"), nullable=True
    )
    platform: Mapped[Platform] = mapped_column(
        SAEnum(Platform, name="platform"), nullable=False
    )
    status: Mapped[PostTargetStatus] = mapped_column(
        SAEnum(PostTargetStatus, name="post_target_status"),
        default=PostTargetStatus.PENDING,
        nullable=False,
    )
    platform_post_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    post: Mapped["Post"] = relationship("Post", back_populates="targets")
    social_account: Mapped["SocialAccount | None"] = relationship("SocialAccount")  # noqa: F821


class Approval(db.Model):
    """Formal sign-off of an immutable PostVersion."""

    __tablename__ = "approvals"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    post_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("posts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    post_version_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("post_versions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    approved_by: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    approved_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    post: Mapped["Post"] = relationship("Post", back_populates="approvals")
    version: Mapped["PostVersion"] = relationship("PostVersion", back_populates="approvals")
    approver: Mapped["User"] = relationship("User")  # noqa: F821

