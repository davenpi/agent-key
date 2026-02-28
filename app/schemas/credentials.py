"""Agent-facing credential schemas."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.common import APIModel


class CheckoutRequest(BaseModel):
    """Checkout request payload."""

    service: str = Field(min_length=1, max_length=100)
    ttl: int | None = Field(default=None, ge=60)


class CheckoutResponse(APIModel):
    """Checkout response payload."""

    checkout_id: UUID
    api_key: str
    service: str
    checked_out_at: datetime
    expires_at: datetime
    note: str


class ReturnRequest(BaseModel):
    """Early return payload."""

    checkout_id: UUID


class ActiveCheckoutResponse(APIModel):
    """Active checkout listing item."""

    id: UUID
    stored_key_id: UUID
    policy_id: UUID
    checked_out_at: datetime
    expires_at: datetime
    returned_at: datetime | None
    revoked_at: datetime | None


class ServiceListResponse(APIModel):
    """Visible service item."""

    provider: str
    name: str
    base_url: str
