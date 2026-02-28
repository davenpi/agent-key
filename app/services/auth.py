"""Authentication dependencies."""

from __future__ import annotations

from typing import TypeVar

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.models.organization import Organization
from app.models.token import AdminToken, AgentToken
from app.services.security import lookup_hash, verify_token

bearer_scheme = HTTPBearer(auto_error=False)
TokenModel = TypeVar("TokenModel", AdminToken, AgentToken)


async def require_admin_token(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    session: AsyncSession = Depends(get_session),
) -> AdminToken:
    """Authenticate an admin token.

    Parameters
    ----------
    credentials : HTTPAuthorizationCredentials | None
        Parsed bearer token.
    session : AsyncSession
        Active database session.

    Returns
    -------
    AdminToken
        Authenticated admin token row.
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing token",
        )
    raw = credentials.credentials
    token_hash_lookup = lookup_hash(raw)
    result = await session.execute(
        select(AdminToken).where(
            AdminToken.token_lookup == token_hash_lookup,
            AdminToken.revoked_at.is_(None),
        )
    )
    row = result.scalar_one_or_none()
    if row is None or not verify_token(raw, row.token_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid admin token",
        )
    return row


async def require_agent_token(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    session: AsyncSession = Depends(get_session),
) -> AgentToken:
    """Authenticate an agent token.

    Parameters
    ----------
    credentials : HTTPAuthorizationCredentials | None
        Parsed bearer token.
    session : AsyncSession
        Active database session.

    Returns
    -------
    AgentToken
        Authenticated agent token row.
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing token",
        )
    raw = credentials.credentials
    token_hash_lookup = lookup_hash(raw)
    result = await session.execute(
        select(AgentToken).where(
            AgentToken.token_lookup == token_hash_lookup,
            AgentToken.revoked_at.is_(None),
        )
    )
    row = result.scalar_one_or_none()
    if row is None or not verify_token(raw, row.token_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid agent token",
        )
    return row


async def ensure_bootstrap_allowed(session: AsyncSession) -> None:
    """Ensure bootstrap can still run.

    Parameters
    ----------
    session : AsyncSession
        Active database session.

    Returns
    -------
    None
        Raises when bootstrap is already complete.
    """
    result = await session.execute(select(Organization.id).limit(1))
    if result.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Bootstrap already completed",
        )
