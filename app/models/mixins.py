"""Shared model helpers."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Uuid
from sqlalchemy.orm import Mapped, mapped_column


class TimestampMixin:
    """Common timestamp columns."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


def uuid_column() -> Mapped[uuid.UUID]:
    """Return a UUID primary-key column.

    Returns
    -------
    Mapped[uuid.UUID]
        SQLAlchemy mapped UUID column.
    """
    return mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
