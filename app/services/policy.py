"""Policy evaluation."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.checkout import Checkout
from app.models.policy import Policy
from app.models.secret import StoredKey
from app.models.service import Service
from app.models.token import AgentToken


async def resolve_checkout_policy(
    session: AsyncSession,
    *,
    agent_token: AgentToken,
    service_provider: str,
    requested_ttl: int,
) -> tuple[Policy, StoredKey, Service]:
    """Resolve a policy and stored key for checkout.

    Parameters
    ----------
    session : AsyncSession
        Active database session.
    agent_token : AgentToken
        Authenticated agent token.
    service_provider : str
        Service provider name.
    requested_ttl : int
        Requested TTL in seconds.

    Returns
    -------
    tuple[Policy, StoredKey, Service]
        Matching policy, stored key, and service.
    """
    service_result = await session.execute(
        select(Service).where(Service.provider == service_provider)
    )
    service = service_result.scalar_one_or_none()
    if service is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Service not found",
        )

    policy_result = await session.execute(
        select(Policy)
        .where(
            Policy.org_id == agent_token.org_id,
            Policy.service_id == service.id,
            Policy.enabled.is_(True),
            Policy.revoked_at.is_(None),
            (Policy.agent_token_id == agent_token.id)
            | (Policy.agent_token_id.is_(None)),
        )
        .order_by(Policy.agent_token_id.is_(None))
    )
    policy = policy_result.scalars().first()
    if policy is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No matching policy",
        )

    if requested_ttl > policy.max_ttl_seconds:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="TTL exceeds policy",
        )

    await _enforce_checkout_window(session, agent_token.id, policy)
    await _enforce_active_checkout_cap(session, agent_token.id, policy)

    key_result = await session.execute(
        select(StoredKey)
        .where(
            StoredKey.org_id == agent_token.org_id,
            StoredKey.service_id == service.id,
            StoredKey.revoked_at.is_(None),
        )
        .order_by(StoredKey.created_at.desc())
    )
    stored_key = key_result.scalars().first()
    if stored_key is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="No active stored key for service",
        )

    return policy, stored_key, service


async def _enforce_checkout_window(
    session: AsyncSession, agent_token_id: UUID, policy: Policy
) -> None:
    """Enforce per-window checkout count.

    Parameters
    ----------
    session : AsyncSession
        Active database session.
    agent_token_id : UUID
        Agent token identifier.
    policy : Policy
        Policy row.

    Returns
    -------
    None
        Raises on policy violation.
    """
    now = datetime.now(timezone.utc)
    delta = (
        timedelta(days=1) if policy.checkout_window == "daily" else timedelta(hours=1)
    )
    threshold = now - delta
    result = await session.execute(
        select(func.count(Checkout.id)).where(
            Checkout.agent_token_id == agent_token_id,
            Checkout.policy_id == policy.id,
            Checkout.checked_out_at >= threshold,
        )
    )
    count = result.scalar_one()
    if count >= policy.max_checkouts_per_window:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Checkout quota exceeded",
        )


async def _enforce_active_checkout_cap(
    session: AsyncSession, agent_token_id: UUID, policy: Policy
) -> None:
    """Enforce active checkout count.

    Parameters
    ----------
    session : AsyncSession
        Active database session.
    agent_token_id : UUID
        Agent token identifier.
    policy : Policy
        Policy row.

    Returns
    -------
    None
        Raises on policy violation.
    """
    now = datetime.now(timezone.utc)
    result = await session.execute(
        select(func.count(Checkout.id)).where(
            Checkout.agent_token_id == agent_token_id,
            Checkout.policy_id == policy.id,
            Checkout.returned_at.is_(None),
            Checkout.revoked_at.is_(None),
            Checkout.expires_at > now,
        )
    )
    active_count = result.scalar_one()
    if active_count >= policy.max_active_checkouts:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Active checkout cap exceeded",
        )
