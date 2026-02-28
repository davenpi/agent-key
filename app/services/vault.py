"""Stored key operations."""

from __future__ import annotations

from functools import lru_cache
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.crypto.envelope import EnvelopeEncryptor
from app.models.secret import StoredKey


@lru_cache(maxsize=1)
def _encryptor() -> EnvelopeEncryptor:
    """Return the cached encryptor instance.

    Returns
    -------
    EnvelopeEncryptor
        Encryptor bound to the current settings.
    """
    from app.config import get_settings

    return EnvelopeEncryptor(get_settings().master_key_path)


async def create_stored_key(
    session: AsyncSession,
    *,
    org_id: UUID,
    service_id: UUID,
    label: str,
    api_key: str,
) -> StoredKey:
    """Store an encrypted provider key.

    Parameters
    ----------
    session : AsyncSession
        Active database session.
    org_id : UUID
        Organization identifier.
    service_id : UUID
        Service identifier.
    label : str
        Human-readable label.
    api_key : str
        Raw provider API key.

    Returns
    -------
    StoredKey
        Persisted stored-key row.
    """
    payload = _encryptor().encrypt(api_key)
    stored_key = StoredKey(
        org_id=org_id,
        service_id=service_id,
        label=label,
        encrypted_secret=payload.encrypted_secret,
        wrapped_data_key=payload.wrapped_data_key,
    )
    session.add(stored_key)
    await session.flush()
    return stored_key


async def decrypt_stored_key(session: AsyncSession, stored_key_id: UUID) -> str:
    """Decrypt a stored key.

    Parameters
    ----------
    session : AsyncSession
        Active database session.
    stored_key_id : UUID
        Stored key identifier.

    Returns
    -------
    str
        Decrypted provider key.
    """
    stored_key = await session.get(StoredKey, stored_key_id)
    if stored_key is None or stored_key.revoked_at is not None:
        raise ValueError("Stored key not found")
    return _encryptor().decrypt(
        stored_key.encrypted_secret,
        stored_key.wrapped_data_key,
    )


async def list_active_stored_keys(
    session: AsyncSession, org_id: UUID
) -> list[StoredKey]:
    """List active stored keys for an organization.

    Parameters
    ----------
    session : AsyncSession
        Active database session.
    org_id : UUID
        Organization identifier.

    Returns
    -------
    list[StoredKey]
        Active stored keys.
    """
    result = await session.execute(
        select(StoredKey).where(
            StoredKey.org_id == org_id,
            StoredKey.revoked_at.is_(None),
        )
    )
    return list(result.scalars().all())
