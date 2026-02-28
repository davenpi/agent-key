"""Checkout policy model."""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.mixins import TimestampMixin, uuid_column


class Policy(TimestampMixin, Base):
    """Rules for key checkout."""

    __tablename__ = "policies"

    id: Mapped[uuid.UUID] = uuid_column()
    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"))
    agent_token_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("agent_tokens.id"), nullable=True
    )
    service_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("services.id"))
    max_checkouts_per_window: Mapped[int] = mapped_column(Integer, default=100)
    checkout_window: Mapped[str] = mapped_column(String(50), default="daily")
    max_active_checkouts: Mapped[int] = mapped_column(Integer, default=1)
    max_ttl_seconds: Mapped[int] = mapped_column(Integer, default=3600)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    organization = relationship("Organization", back_populates="policies")
    service = relationship("Service", back_populates="policies")
    checkouts = relationship("Checkout", back_populates="policy")
