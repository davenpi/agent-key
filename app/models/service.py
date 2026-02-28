"""Provider service model."""

import uuid

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.mixins import TimestampMixin, uuid_column


class Service(TimestampMixin, Base):
    """Supported provider definition."""

    __tablename__ = "services"

    id: Mapped[uuid.UUID] = uuid_column()
    provider: Mapped[str] = mapped_column(String(100), unique=True)
    name: Mapped[str] = mapped_column(String(255))
    base_url: Mapped[str] = mapped_column(String(512))

    stored_keys = relationship("StoredKey", back_populates="service")
    policies = relationship("Policy", back_populates="service")
