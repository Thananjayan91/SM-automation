"""Research models and background generation job tracking."""
import uuid
from datetime import datetime, timezone
from enum import Enum

from sqlalchemy import String, Integer, DateTime, ForeignKey, Text, JSON, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..extensions import db


class JobStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    SUCCESS = "success"
    FAILED = "failed"
    RETRYING = "retrying"


class JobStep(str, Enum):
    EXTRACTING = "extracting_source"
    RESEARCHING = "researching"
    WRITING = "generating_caption"
    IMAGE_GENERATION = "generating_image"
    COMPLETED = "completed"
    FAILED = "failed"


class ResearchRun(db.Model):
    """A research session extracting external citations and synthesizing a story."""

    __tablename__ = "research_runs"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    source_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("sources.id", ondelete="CASCADE"), nullable=False, index=True
    )
    provider: Mapped[str] = mapped_column(String(100), default="mock", nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="success", nullable=False)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    result_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(100), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )

    # Relationships
    tenant: Mapped["Tenant"] = relationship("Tenant")  # noqa: F821
    source: Mapped["Source"] = relationship("Source")  # noqa: F821
    citations: Mapped[list["ResearchCitation"]] = relationship(
        "ResearchCitation", back_populates="run", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<ResearchRun {self.id} provider={self.provider} status={self.status}>"


class ResearchCitation(db.Model):
    """External supporting source, fact, or citation."""

    __tablename__ = "research_citations"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    research_run_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("research_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    title: Mapped[str | None] = mapped_column(String(512), nullable=True)
    published_at: Mapped[str | None] = mapped_column(String(128), nullable=True)
    excerpt: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )

    # Relationships
    run: Mapped["ResearchRun"] = relationship("ResearchRun", back_populates="citations")


class GenerationJob(db.Model):
    """Asynchronous generation pipeline tracking."""

    __tablename__ = "generation_jobs"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    source_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("sources.id", ondelete="SET NULL"), nullable=True
    )
    post_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("posts.id", ondelete="SET NULL"), nullable=True
    )
    status: Mapped[JobStatus] = mapped_column(
        SAEnum(JobStatus, name="generation_job_status"), default=JobStatus.PENDING, nullable=False, index=True
    )
    current_step: Mapped[JobStep] = mapped_column(
        SAEnum(JobStep, name="generation_job_step"), default=JobStep.EXTRACTING, nullable=False
    )
    progress_pct: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    attempt_count: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    max_attempts: Mapped[int] = mapped_column(Integer, default=3, nullable=False)

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
    user: Mapped["User | None"] = relationship("User")  # noqa: F821
    source: Mapped["Source | None"] = relationship("Source")  # noqa: F821
    post: Mapped["Post | None"] = relationship("Post")  # noqa: F821

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "tenant_id": self.tenant_id,
            "status": self.status.value,
            "current_step": self.current_step.value,
            "progress_pct": self.progress_pct,
            "post_id": self.post_id,
            "source_id": self.source_id,
            "error_code": self.error_code,
            "error_message": self.error_message,
            "attempt_count": self.attempt_count,
            "max_attempts": self.max_attempts,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }

