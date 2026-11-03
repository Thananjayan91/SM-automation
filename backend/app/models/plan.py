"""Plan model — subscription tiers and feature limits."""
import uuid
from datetime import datetime, timezone
from enum import Enum

from sqlalchemy import String, DateTime, Integer, Boolean, Text, Numeric
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..extensions import db


class PlanTier(str, Enum):
    FREE = "free"
    STARTER = "starter"
    PRO = "pro"
    ENTERPRISE = "enterprise"


class Plan(db.Model):
    """A subscription tier defining feature limits.

    Limits are stored in the database — never hardcoded in templates.
    """

    __tablename__ = "plans"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    tier: Mapped[PlanTier] = mapped_column(
        SAEnum(PlanTier, name="plan_tier"), unique=True, nullable=False
    )
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Pricing (in smallest currency unit, e.g. cents)
    price_monthly_cents: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    price_yearly_cents: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Feature limits (-1 means unlimited)
    max_social_accounts: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    max_team_members: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    max_ai_generations_per_month: Mapped[int] = mapped_column(Integer, default=20, nullable=False)
    max_image_generations_per_month: Mapped[int] = mapped_column(Integer, default=5, nullable=False)
    audit_history_days: Mapped[int] = mapped_column(Integer, default=7, nullable=False)

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
    subscriptions: Mapped[list["Subscription"]] = relationship(  # noqa: F821
        "Subscription", back_populates="plan", lazy="dynamic"
    )

    def __repr__(self) -> str:
        return f"<Plan {self.tier}>"
