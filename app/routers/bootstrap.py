"""Bootstrap routes."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import get_session
from app.models.organization import Organization
from app.models.token import AdminToken
from app.schemas.bootstrap import BootstrapRequest, BootstrapResponse
from app.schemas.common import TokenResponse
from app.services.audit import log_event
from app.services.auth import ensure_bootstrap_allowed
from app.services.security import generate_plaintext_token, hash_token, lookup_hash

router = APIRouter(prefix="/v1", tags=["bootstrap"])


@router.post("/bootstrap", response_model=BootstrapResponse)
async def bootstrap(
    payload: BootstrapRequest,
    session: AsyncSession = Depends(get_session),
) -> BootstrapResponse:
    """Create the initial organization and admin token.

    Parameters
    ----------
    payload : BootstrapRequest
        Bootstrap request.
    session : AsyncSession
        Active database session.

    Returns
    -------
    BootstrapResponse
        Created organization and admin token.
    """
    if not get_settings().bootstrap_enabled:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Bootstrap disabled",
        )
    await ensure_bootstrap_allowed(session)

    organization = Organization(name=payload.organization_name)
    session.add(organization)
    await session.flush()

    plaintext = generate_plaintext_token("adm")
    admin_token = AdminToken(
        org_id=organization.id,
        name=payload.admin_token_name,
        token_hash=hash_token(plaintext),
        token_lookup=lookup_hash(plaintext),
    )
    session.add(admin_token)
    await session.flush()
    await log_event(
        session,
        org_id=organization.id,
        action="organization_bootstrapped",
        resource_type="organization",
        resource_id=str(organization.id),
        metadata={"name": organization.name},
    )
    await session.commit()
    return BootstrapResponse(
        organization_id=str(organization.id),
        admin_token=TokenResponse(
            id=admin_token.id,
            token=plaintext,
            name=admin_token.name,
        ),
    )
