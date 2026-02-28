"""Admin-facing schemas."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.common import APIModel


class AgentCreateRequest(BaseModel):
    """Create an agent token."""

    name: str = Field(min_length=1, max_length=255)


class ServiceUpsertRequest(BaseModel):
    """Create a supported provider service."""

    provider: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=255)
    base_url: str = Field(min_length=1, max_length=512)


class StoredKeyCreateRequest(BaseModel):
    """Store an encrypted provider key."""

    service_id: UUID
    label: str = Field(min_length=1, max_length=255)
    api_key: str = Field(min_length=1)


class PolicyCreateRequest(BaseModel):
    """Create or update a checkout policy."""

    service_id: UUID
    agent_token_id: UUID | None = None
    max_checkouts_per_window: int = Field(default=100, ge=1)
    checkout_window: str = Field(default="daily", pattern="^(daily|hourly)$")
    max_active_checkouts: int = Field(default=1, ge=1)
    max_ttl_seconds: int = Field(default=3600, ge=60)
    enabled: bool = True


class ServiceResponse(APIModel):
    """Service metadata."""

    id: UUID
    provider: str
    name: str
    base_url: str


class StoredKeyResponse(APIModel):
    """Stored key metadata."""

    id: UUID
    service_id: UUID
    label: str
    created_at: datetime
    revoked_at: datetime | None


class PolicyResponse(APIModel):
    """Policy metadata."""

    id: UUID
    service_id: UUID
    agent_token_id: UUID | None
    max_checkouts_per_window: int
    checkout_window: str
    max_active_checkouts: int
    max_ttl_seconds: int
    enabled: bool


class AuditResponse(APIModel):
    """Audit log event."""

    id: UUID
    action: str
    resource_type: str
    resource_id: str
    event_metadata: dict[str, str | int | float | None]
    timestamp: datetime


class CheckoutAdminResponse(APIModel):
    """Checkout metadata for admin views."""

    id: UUID
    agent_token_id: UUID
    stored_key_id: UUID
    policy_id: UUID
    checked_out_at: datetime
    expires_at: datetime
    returned_at: datetime | None
    revoked_at: datetime | None


class AdminTokenCreateRequest(BaseModel):
    """Create another admin token."""

    name: str = Field(min_length=1, max_length=255)
