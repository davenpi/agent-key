"""Checkout orchestration."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.checkout import Checkout
from app.models.token import AgentToken
from app.services.audit import log_event
from app.services.policy import resolve_checkout_policy
from app.services.vault import decrypt_stored_key


async def create_checkout(
    session: AsyncSession,
    *,
    agent_token: AgentToken,
    service_provider: str,
    ttl_seconds: int | None,
) -> tuple[Checkout, str, str]:
    """Create a checkout and return decrypted key material.

    Parameters
    ----------
    session : AsyncSession
        Active database session.
    agent_token : AgentToken
        Authenticated agent token.
    service_provider : str
        Target service provider.
    ttl_seconds : int | None
        Requested TTL.

    Returns
    -------
    tuple[Checkout, str, str]
        Checkout row, decrypted API key, and provider name.
    """
    ttl = ttl_seconds or get_settings().default_checkout_ttl_seconds
    policy, stored_key, service = await resolve_checkout_policy(
        session,
        agent_token=agent_token,
        service_provider=service_provider,
        requested_ttl=ttl,
    )

    now = datetime.now(timezone.utc)
    checkout = Checkout(
        agent_token_id=agent_token.id,
        stored_key_id=stored_key.id,
        policy_id=policy.id,
        checked_out_at=now,
        expires_at=now + timedelta(seconds=ttl),
    )
    session.add(checkout)
    await session.flush()

    api_key = await decrypt_stored_key(session, stored_key.id)
    await log_event(
        session,
        org_id=agent_token.org_id,
        agent_token_id=agent_token.id,
        action="key_checked_out",
        resource_type="checkout",
        resource_id=str(checkout.id),
        metadata={"service": service.provider, "ttl_seconds": ttl},
    )
    return checkout, api_key, service.provider


async def return_checkout(
    session: AsyncSession,
    *,
    agent_token: AgentToken,
    checkout_id: UUID,
) -> Checkout:
    """Return a checkout early.

    Parameters
    ----------
    session : AsyncSession
        Active database session.
    agent_token : AgentToken
        Authenticated agent token.
    checkout_id : UUID
        Checkout identifier.

    Returns
    -------
    Checkout
        Updated checkout row.
    """
    checkout = await session.get(Checkout, checkout_id)
    if checkout is None or checkout.agent_token_id != agent_token.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Checkout not found",
        )
    if checkout.revoked_at is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Checkout has been revoked",
        )
    now = datetime.now(timezone.utc)
    expires = checkout.expires_at
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    if expires <= now:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Checkout has expired",
        )
    if checkout.returned_at is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Checkout already returned",
        )
    checkout.returned_at = now
    await session.flush()
    await log_event(
        session,
        org_id=agent_token.org_id,
        agent_token_id=agent_token.id,
        action="key_returned",
        resource_type="checkout",
        resource_id=str(checkout.id),
        metadata={},
    )
    return checkout


async def revoke_checkout(
    session: AsyncSession, checkout_id: UUID, org_id: UUID
) -> Checkout:
    """Revoke a checkout record.

    Parameters
    ----------
    session : AsyncSession
        Active database session.
    checkout_id : UUID
        Checkout identifier.
    org_id : UUID
        Owning organization identifier.

    Returns
    -------
    Checkout
        Updated checkout row.
    """
    result = await session.execute(
        select(Checkout)
        .join(AgentToken, AgentToken.id == Checkout.agent_token_id)
        .where(Checkout.id == checkout_id, AgentToken.org_id == org_id)
    )
    checkout = result.scalar_one_or_none()
    if checkout is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Checkout not found",
        )
    if checkout.revoked_at is None:
        checkout.revoked_at = datetime.now(timezone.utc)
        await session.flush()
        await log_event(
            session,
            org_id=org_id,
            agent_token_id=checkout.agent_token_id,
            action="checkout_revoked",
            resource_type="checkout",
            resource_id=str(checkout.id),
            metadata={},
        )
    return checkout
