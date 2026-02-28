"""Audit event model."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.mixins import uuid_column


class AuditLog(Base):
    """Append-only audit entry."""

    __tablename__ = "audit_logs"

    id: Mapped[uuid.UUID] = uuid_column()
    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"))
    agent_token_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("agent_tokens.id"), nullable=True
    )
    action: Mapped[str] = mapped_column(String(100))
    resource_type: Mapped[str] = mapped_column(String(100))
    resource_id: Mapped[str] = mapped_column(String(255))
    event_metadata: Mapped[dict[str, str | int | float | None]] = mapped_column(JSON)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
