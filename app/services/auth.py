"""Authentication dependencies."""

from __future__ import annotations

from typing import TypeVar

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.models.organization import Organization
from app.models.token import AdminToken, AgentToken
from app.services.security import verify_token

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
    admin_token = await _match_token(
        session=session,
        query=select(AdminToken).where(AdminToken.revoked_at.is_(None)),
        raw_token=credentials.credentials,
    )
    if admin_token is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid admin token",
        )
    return admin_token


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
    agent_token = await _match_token(
        session=session,
        query=select(AgentToken).where(AgentToken.revoked_at.is_(None)),
        raw_token=credentials.credentials,
    )
    if agent_token is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid agent token",
        )
    return agent_token


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


async def _match_token(
    session: AsyncSession,
    query: Select[tuple[TokenModel]],
    raw_token: str,
) -> TokenModel | None:
    """Match a raw token against hashed rows.

    Parameters
    ----------
    session : AsyncSession
        Active database session.
    query : Select[tuple[T]]
        Candidate token query.
    raw_token : str
        Raw bearer token.

    Returns
    -------
    T | None
        Matching token row if found.
    """
    result = await session.execute(query)
    rows = result.scalars().all()
    for row in rows:
        if verify_token(raw_token, row.token_hash):
            return row
    return None
