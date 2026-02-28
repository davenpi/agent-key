"""Stored secret model."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, LargeBinary, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.mixins import TimestampMixin, uuid_column


class StoredKey(TimestampMixin, Base):
    """Encrypted provider API key."""

    __tablename__ = "stored_keys"

    id: Mapped[uuid.UUID] = uuid_column()
    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id"))
    service_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("services.id"))
    label: Mapped[str] = mapped_column(String(255))
    encrypted_secret: Mapped[bytes] = mapped_column(LargeBinary)
    wrapped_data_key: Mapped[bytes] = mapped_column(LargeBinary)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    organization = relationship("Organization", back_populates="stored_keys")
    service = relationship("Service", back_populates="stored_keys")
    checkouts = relationship("Checkout", back_populates="stored_key")
