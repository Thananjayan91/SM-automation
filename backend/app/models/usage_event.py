"""UsageEvent model — auditable record of billable operations."""
import uuid
from datetime import datetime, timezone
from enum import Enum

from sqlalchemy import String, DateTime, ForeignKey, Integer, Numeric, Text, JSON
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from ..extensions import db


class UsageEventType(str, Enum):
    AI_TEXT_GENERATION = "ai_text_generation"
    IMAGE_GENERATION = "image_generation"
    PUBLISHING = "publishing"
    RESEARCH = "research"


class UsageEvent(db.Model):
    """Records each billable AI or publishing operation by tenant.

    These records are the source of truth for usage-based limits and
    cost estimation. Every provider call must create a UsageEvent.
    """

    __tablename__ = "usage_events"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    tenant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    event_type: Mapped[UsageEventType] = mapped_column(
        SAEnum(UsageEventType, name="usage_event_type"), nullable=False, index=True
    )
    provider: Mapped[str | None] = mapped_column(String(100), nullable=True)
    model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    # Tokens/units used
    input_units: Mapped[int | None] = mapped_column(Integer, nullable=True)
    output_units: Mapped[int | None] = mapped_column(Integer, nullable=True)
    image_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Cost estimation
    estimated_cost_cents: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Status
    status: Mapped[str] = mapped_column(String(50), default="success", nullable=False)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Related entity IDs (optional context)
    related_entity_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    related_entity_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    # Extra metadata
    metadata_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False, index=True
    )

    def __repr__(self) -> str:
        return f"<UsageEvent {self.event_type} tenant={self.tenant_id}>"
