"""Organization model."""

import uuid

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.mixins import TimestampMixin, uuid_column


class Organization(TimestampMixin, Base):
    """Owning organization."""

    __tablename__ = "organizations"

    id: Mapped[uuid.UUID] = uuid_column()
    name: Mapped[str] = mapped_column(String(255), unique=True)

    admin_tokens = relationship("AdminToken", back_populates="organization")
    agent_tokens = relationship("AgentToken", back_populates="organization")
    policies = relationship("Policy", back_populates="organization")
    stored_keys = relationship("StoredKey", back_populates="organization")
