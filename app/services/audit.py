"""Audit logging service."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AuditLog


async def log_event(
    session: AsyncSession,
    *,
    org_id: UUID,
    action: str,
    resource_type: str,
    resource_id: str,
    metadata: dict[str, str | int | float | None],
    agent_token_id: UUID | None = None,
) -> AuditLog:
    """Persist an audit event.

    Parameters
    ----------
    session : AsyncSession
        Active database session.
    org_id : UUID
        Organization identifier.
    action : str
        Event action.
    resource_type : str
        Kind of resource touched.
    resource_id : str
        String resource identifier.
    metadata : dict[str, str | int | float | None]
        Additional event metadata.
    agent_token_id : UUID | None, default=None
        Optional agent token identifier.

    Returns
    -------
    AuditLog
        Persisted audit record.
    """
    event = AuditLog(
        org_id=org_id,
        agent_token_id=agent_token_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        event_metadata=metadata,
    )
    session.add(event)
    await session.flush()
    return event
