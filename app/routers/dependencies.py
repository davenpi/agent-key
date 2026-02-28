"""Shared router helpers."""

from sqlalchemy.ext.asyncio import AsyncSession


async def commit_session(session: AsyncSession) -> None:
    """Commit the current transaction.

    Parameters
    ----------
    session : AsyncSession
        Active database session.

    Returns
    -------
    None
        Commits current transaction.
    """
    await session.commit()
