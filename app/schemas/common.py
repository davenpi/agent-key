"""Common schema primitives."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class APIModel(BaseModel):
    """Base API model with attribute validation enabled."""

    model_config = ConfigDict(from_attributes=True)


class TokenResponse(APIModel):
    """Return a generated token exactly once."""

    id: UUID
    token: str
    name: str


class MessageResponse(APIModel):
    """Simple message response."""

    message: str
    timestamp: datetime | None = None
