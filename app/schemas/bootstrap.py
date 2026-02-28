"""Bootstrap request and response schemas."""

from pydantic import BaseModel, Field

from app.schemas.common import TokenResponse


class BootstrapRequest(BaseModel):
    """Create an initial organization and admin token."""

    organization_name: str = Field(min_length=1, max_length=255)
    admin_token_name: str = Field(default="default-admin", min_length=1, max_length=255)


class BootstrapResponse(BaseModel):
    """Bootstrap response payload."""

    organization_id: str
    admin_token: TokenResponse
