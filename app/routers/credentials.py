"""Agent credential routes."""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.models.checkout import Checkout
from app.models.policy import Policy
from app.models.secret import StoredKey
from app.models.service import Service
from app.models.token import AgentToken
from app.routers.dependencies import commit_session
from app.schemas.common import MessageResponse
from app.schemas.credentials import (
    ActiveCheckoutResponse,
    CheckoutRequest,
    CheckoutResponse,
    ReturnRequest,
    ServiceListResponse,
)
from app.services.auth import require_agent_token
from app.services.checkout import create_checkout, return_checkout

router = APIRouter(prefix="/v1/credentials", tags=["credentials"])


@router.post("/checkout", response_model=CheckoutResponse)
async def checkout_credentials(
    payload: CheckoutRequest,
    agent_token: AgentToken = Depends(require_agent_token),
    session: AsyncSession = Depends(get_session),
) -> CheckoutResponse:
    """Create a checkout and return a raw provider key."""
    checkout, api_key, service = await create_checkout(
        session,
        agent_token=agent_token,
        service_provider=payload.service,
        ttl_seconds=payload.ttl,
    )
    await commit_session(session)
    return CheckoutResponse(
        checkout_id=checkout.id,
        api_key=api_key,
        service=service,
        checked_out_at=checkout.checked_out_at,
        expires_at=checkout.expires_at,
        note=(
            "This is a raw provider key. Scope and spend are not enforced "
            "by Agent Key in vault mode."
        ),
    )


@router.post("/return", response_model=MessageResponse)
async def return_credentials(
    payload: ReturnRequest,
    agent_token: AgentToken = Depends(require_agent_token),
    session: AsyncSession = Depends(get_session),
) -> MessageResponse:
    """Return a checkout early."""
    checkout = await return_checkout(
        session, agent_token=agent_token, checkout_id=payload.checkout_id
    )
    await commit_session(session)
    return MessageResponse(message="Checkout returned", timestamp=checkout.returned_at)


@router.get("/active", response_model=list[ActiveCheckoutResponse])
async def list_active_checkouts(
    agent_token: AgentToken = Depends(require_agent_token),
    session: AsyncSession = Depends(get_session),
) -> list[ActiveCheckoutResponse]:
    """List active checkout records."""
    now = datetime.now(timezone.utc)
    result = await session.execute(
        select(Checkout).where(
            Checkout.agent_token_id == agent_token.id,
            Checkout.returned_at.is_(None),
            Checkout.revoked_at.is_(None),
            Checkout.expires_at > now,
        )
    )
    return [
        ActiveCheckoutResponse.model_validate(row) for row in result.scalars().all()
    ]


services_router = APIRouter(prefix="/v1", tags=["credentials"])


@services_router.get("/services", response_model=list[ServiceListResponse])
async def list_visible_services(
    agent_token: AgentToken = Depends(require_agent_token),
    session: AsyncSession = Depends(get_session),
) -> list[ServiceListResponse]:
    """List services visible to the agent."""
    result = await session.execute(
        select(Service)
        .join(Policy, Policy.service_id == Service.id)
        .join(StoredKey, StoredKey.service_id == Service.id)
        .where(
            Policy.org_id == agent_token.org_id,
            Policy.enabled.is_(True),
            Policy.revoked_at.is_(None),
            StoredKey.org_id == agent_token.org_id,
            StoredKey.revoked_at.is_(None),
            (Policy.agent_token_id == agent_token.id)
            | (Policy.agent_token_id.is_(None)),
        )
        .distinct()
        .order_by(Service.provider.asc())
    )
    return [ServiceListResponse.model_validate(row) for row in result.scalars().all()]
