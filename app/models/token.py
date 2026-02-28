"""Authentication token models."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.mixins import TimestampMixin, uuid_column


class AdminToken(TimestampMixin, Base):
    """Organization-scoped admin token."""

    __tablename__ = "admin_tokens"
    __table_args__ = (
        Index("ix_admin_tokens_lookup", "token_lookup"),
        UniqueConstraint("org_id", "name", name="uq_admin_tokens_org_name"),
    )

    id: Mapped[uuid.UUID] = uuid_column()
    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"))
    name: Mapped[str] = mapped_column(String(255))
    token_hash: Mapped[str] = mapped_column(String(512))
    token_lookup: Mapped[str] = mapped_column(String(64))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    organization = relationship("Organization", back_populates="admin_tokens")


class AgentToken(TimestampMixin, Base):
    """Organization-scoped agent token."""

    __tablename__ = "agent_tokens"
    __table_args__ = (
        Index("ix_agent_tokens_lookup", "token_lookup"),
        UniqueConstraint("org_id", "name", name="uq_agent_tokens_org_name"),
    )

    id: Mapped[uuid.UUID] = uuid_column()
    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"))
    name: Mapped[str] = mapped_column(String(255))
    token_hash: Mapped[str] = mapped_column(String(512))
    token_lookup: Mapped[str] = mapped_column(String(64))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    organization = relationship("Organization", back_populates="agent_tokens")
    checkouts = relationship("Checkout", back_populates="agent_token")
