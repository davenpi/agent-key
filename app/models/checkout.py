"""Checkout model."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.mixins import TimestampMixin, uuid_column


class Checkout(TimestampMixin, Base):
    """Time-bound checkout record."""

    __tablename__ = "checkouts"

    id: Mapped[uuid.UUID] = uuid_column()
    agent_token_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("agent_tokens.id"))
    stored_key_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("stored_keys.id"))
    policy_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("policies.id"))
    checked_out_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    returned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    agent_token = relationship("AgentToken", back_populates="checkouts")
    stored_key = relationship("StoredKey", back_populates="checkouts")
    policy = relationship("Policy", back_populates="checkouts")
