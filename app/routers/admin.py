"""Admin routes."""

from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.models.audit import AuditLog
from app.models.checkout import Checkout
from app.models.policy import Policy
from app.models.secret import StoredKey
from app.models.service import Service
from app.models.token import AdminToken, AgentToken
from app.routers.dependencies import commit_session
from app.schemas.admin import (
    AdminTokenCreateRequest,
    AgentCreateRequest,
    AuditResponse,
    CheckoutAdminResponse,
    PolicyCreateRequest,
    PolicyResponse,
    PolicyUpdateRequest,
    ServiceResponse,
    ServiceUpsertRequest,
    StoredKeyCreateRequest,
    StoredKeyResponse,
)
from app.schemas.common import MessageResponse, TokenResponse
from app.services.audit import log_event
from app.services.auth import require_admin_token
from app.services.checkout import revoke_checkout
from app.services.security import generate_plaintext_token, hash_token, lookup_hash
from app.services.vault import create_stored_key

router = APIRouter(prefix="/v1/admin", tags=["admin"])


async def _ensure_admin_token_name_available(
    session: AsyncSession, *, org_id: UUID, name: str
) -> None:
    """Ensure an admin token name is unused within the organization.

    Parameters
    ----------
    session : AsyncSession
        Active database session.
    org_id : UUID
        Organization identifier.
    name : str
        Requested token name.

    Returns
    -------
    None
        Raises on conflict.
    """
    result = await session.execute(
        select(AdminToken.id).where(
            AdminToken.org_id == org_id,
            AdminToken.name == name,
        )
    )
    if result.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Admin token name already exists",
        )


async def _ensure_agent_token_name_available(
    session: AsyncSession, *, org_id: UUID, name: str
) -> None:
    """Ensure an agent token name is unused within the organization.

    Parameters
    ----------
    session : AsyncSession
        Active database session.
    org_id : UUID
        Organization identifier.
    name : str
        Requested token name.

    Returns
    -------
    None
        Raises on conflict.
    """
    result = await session.execute(
        select(AgentToken.id).where(
            AgentToken.org_id == org_id,
            AgentToken.name == name,
        )
    )
    if result.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Agent token name already exists",
        )


async def _get_service_or_404(session: AsyncSession, service_id: UUID) -> Service:
    """Return a service or raise 404.

    Parameters
    ----------
    session : AsyncSession
        Active database session.
    service_id : UUID
        Service identifier.

    Returns
    -------
    Service
        Matching service row.
    """
    service = await session.get(Service, service_id)
    if service is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Service not found",
        )
    return service


async def _ensure_service_provider_available(
    session: AsyncSession, *, provider: str
) -> None:
    """Ensure a provider slug is not already registered.

    Parameters
    ----------
    session : AsyncSession
        Active database session.
    provider : str
        Provider slug.

    Returns
    -------
    None
        Raises on conflict.
    """
    result = await session.execute(
        select(Service.id).where(Service.provider == provider)
    )
    if result.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Service provider already exists",
        )


async def _ensure_stored_key_label_available(
    session: AsyncSession, *, org_id: UUID, service_id: UUID, label: str
) -> None:
    """Ensure a stored-key label is unique per org/service pair.

    Parameters
    ----------
    session : AsyncSession
        Active database session.
    org_id : UUID
        Organization identifier.
    service_id : UUID
        Service identifier.
    label : str
        Requested label.

    Returns
    -------
    None
        Raises on conflict.
    """
    result = await session.execute(
        select(StoredKey.id).where(
            StoredKey.org_id == org_id,
            StoredKey.service_id == service_id,
            StoredKey.label == label,
        )
    )
    if result.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Stored key label already exists for service",
        )


async def _get_agent_token_for_org_or_404(
    session: AsyncSession, *, org_id: UUID, agent_token_id: UUID
) -> AgentToken:
    """Return an agent token scoped to an organization or raise 404.

    Parameters
    ----------
    session : AsyncSession
        Active database session.
    org_id : UUID
        Organization identifier.
    agent_token_id : UUID
        Agent token identifier.

    Returns
    -------
    AgentToken
        Matching agent token row.
    """
    result = await session.execute(
        select(AgentToken).where(
            AgentToken.id == agent_token_id,
            AgentToken.org_id == org_id,
        )
    )
    token = result.scalar_one_or_none()
    if token is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent token not found",
        )
    return token


async def _ensure_policy_available(
    session: AsyncSession,
    *,
    org_id: UUID,
    service_id: UUID,
    agent_token_id: UUID | None,
) -> None:
    """Ensure the org does not already have the same policy target.

    Parameters
    ----------
    session : AsyncSession
        Active database session.
    org_id : UUID
        Organization identifier.
    service_id : UUID
        Service identifier.
    agent_token_id : UUID | None
        Optional scoped agent token identifier.

    Returns
    -------
    None
        Raises on conflict.
    """
    query = select(Policy.id).where(
        Policy.org_id == org_id,
        Policy.service_id == service_id,
    )
    if agent_token_id is None:
        query = query.where(Policy.agent_token_id.is_(None))
    else:
        query = query.where(Policy.agent_token_id == agent_token_id)
    result = await session.execute(query)
    if result.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Policy already exists for this service target",
        )


@router.post("/tokens", response_model=TokenResponse)
async def create_admin_token(
    payload: AdminTokenCreateRequest,
    admin_token: AdminToken = Depends(require_admin_token),
    session: AsyncSession = Depends(get_session),
) -> TokenResponse:
    """Create an additional admin token."""
    await _ensure_admin_token_name_available(
        session,
        org_id=admin_token.org_id,
        name=payload.name,
    )
    plaintext = generate_plaintext_token("adm")
    token = AdminToken(
        org_id=admin_token.org_id,
        name=payload.name,
        token_hash=hash_token(plaintext),
        token_lookup=lookup_hash(plaintext),
    )
    session.add(token)
    await session.flush()
    await log_event(
        session,
        org_id=admin_token.org_id,
        action="admin_token_created",
        resource_type="admin_token",
        resource_id=str(token.id),
        metadata={"name": token.name},
    )
    await commit_session(session)
    return TokenResponse(id=token.id, token=plaintext, name=token.name)


@router.post("/agents", response_model=TokenResponse)
async def create_agent_token(
    payload: AgentCreateRequest,
    admin_token: AdminToken = Depends(require_admin_token),
    session: AsyncSession = Depends(get_session),
) -> TokenResponse:
    """Create an agent token."""
    await _ensure_agent_token_name_available(
        session,
        org_id=admin_token.org_id,
        name=payload.name,
    )
    plaintext = generate_plaintext_token("agt")
    token = AgentToken(
        org_id=admin_token.org_id,
        name=payload.name,
        token_hash=hash_token(plaintext),
        token_lookup=lookup_hash(plaintext),
    )
    session.add(token)
    await session.flush()
    await log_event(
        session,
        org_id=admin_token.org_id,
        action="agent_token_created",
        resource_type="agent_token",
        resource_id=str(token.id),
        metadata={"name": token.name},
    )
    await commit_session(session)
    return TokenResponse(id=token.id, token=plaintext, name=token.name)


@router.get("/agents", response_model=list[TokenResponse])
async def list_agent_tokens(
    admin_token: AdminToken = Depends(require_admin_token),
    session: AsyncSession = Depends(get_session),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> list[TokenResponse]:
    """List agent token metadata."""
    result = await session.execute(
        select(AgentToken)
        .where(AgentToken.org_id == admin_token.org_id)
        .order_by(AgentToken.created_at.desc(), AgentToken.id.desc())
        .limit(limit)
        .offset(offset)
    )
    return [
        TokenResponse(id=row.id, token="redacted", name=row.name)
        for row in result.scalars().all()
    ]


@router.delete("/agents/{agent_token_id}", response_model=MessageResponse)
async def revoke_agent_token(
    agent_token_id: str,
    admin_token: AdminToken = Depends(require_admin_token),
    session: AsyncSession = Depends(get_session),
) -> MessageResponse:
    """Revoke an agent token."""
    result = await session.execute(
        select(AgentToken).where(
            AgentToken.id == agent_token_id,
            AgentToken.org_id == admin_token.org_id,
        )
    )
    token = result.scalar_one_or_none()
    if token is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent token not found",
        )
    token.revoked_at = datetime.now(timezone.utc)
    await log_event(
        session,
        org_id=admin_token.org_id,
        action="agent_token_revoked",
        resource_type="agent_token",
        resource_id=str(token.id),
        metadata={},
    )
    await commit_session(session)
    return MessageResponse(message="Agent token revoked", timestamp=token.revoked_at)


@router.post("/services", response_model=ServiceResponse)
async def create_service(
    payload: ServiceUpsertRequest,
    admin_token: AdminToken = Depends(require_admin_token),
    session: AsyncSession = Depends(get_session),
) -> ServiceResponse:
    """Create a provider service."""
    await _ensure_service_provider_available(session, provider=payload.provider)
    service = Service(
        provider=payload.provider,
        name=payload.name,
        base_url=payload.base_url,
    )
    session.add(service)
    await session.flush()
    await log_event(
        session,
        org_id=admin_token.org_id,
        action="service_created",
        resource_type="service",
        resource_id=str(service.id),
        metadata={"provider": service.provider},
    )
    await commit_session(session)
    return ServiceResponse.model_validate(service)


@router.get("/services", response_model=list[ServiceResponse])
async def list_services(
    _: AdminToken = Depends(require_admin_token),
    session: AsyncSession = Depends(get_session),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> list[ServiceResponse]:
    """List services."""
    result = await session.execute(
        select(Service)
        .order_by(Service.provider.asc(), Service.id.asc())
        .limit(limit)
        .offset(offset)
    )
    return [ServiceResponse.model_validate(row) for row in result.scalars().all()]


@router.post("/keys", response_model=StoredKeyResponse)
async def create_key(
    payload: StoredKeyCreateRequest,
    admin_token: AdminToken = Depends(require_admin_token),
    session: AsyncSession = Depends(get_session),
) -> StoredKeyResponse:
    """Store a provider key."""
    await _get_service_or_404(session, payload.service_id)
    await _ensure_stored_key_label_available(
        session,
        org_id=admin_token.org_id,
        service_id=payload.service_id,
        label=payload.label,
    )
    stored_key = await create_stored_key(
        session,
        org_id=admin_token.org_id,
        service_id=payload.service_id,
        label=payload.label,
        api_key=payload.api_key,
    )
    await log_event(
        session,
        org_id=admin_token.org_id,
        action="stored_key_created",
        resource_type="stored_key",
        resource_id=str(stored_key.id),
        metadata={"service_id": str(payload.service_id)},
    )
    await commit_session(session)
    return StoredKeyResponse.model_validate(stored_key)


@router.get("/keys", response_model=list[StoredKeyResponse])
async def list_keys(
    admin_token: AdminToken = Depends(require_admin_token),
    session: AsyncSession = Depends(get_session),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> list[StoredKeyResponse]:
    """List stored key metadata."""
    result = await session.execute(
        select(StoredKey)
        .where(StoredKey.org_id == admin_token.org_id)
        .order_by(StoredKey.created_at.desc(), StoredKey.id.desc())
        .limit(limit)
        .offset(offset)
    )
    return [StoredKeyResponse.model_validate(row) for row in result.scalars().all()]


@router.delete("/keys/{stored_key_id}", response_model=MessageResponse)
async def revoke_key(
    stored_key_id: str,
    admin_token: AdminToken = Depends(require_admin_token),
    session: AsyncSession = Depends(get_session),
) -> MessageResponse:
    """Revoke a stored key."""
    result = await session.execute(
        select(StoredKey).where(
            StoredKey.id == stored_key_id,
            StoredKey.org_id == admin_token.org_id,
        )
    )
    stored_key = result.scalar_one_or_none()
    if stored_key is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Stored key not found",
        )
    stored_key.revoked_at = datetime.now(timezone.utc)
    await log_event(
        session,
        org_id=admin_token.org_id,
        action="stored_key_revoked",
        resource_type="stored_key",
        resource_id=str(stored_key.id),
        metadata={},
    )
    await commit_session(session)
    return MessageResponse(
        message="Stored key revoked",
        timestamp=stored_key.revoked_at,
    )


@router.post("/policies", response_model=PolicyResponse)
async def create_policy(
    payload: PolicyCreateRequest,
    admin_token: AdminToken = Depends(require_admin_token),
    session: AsyncSession = Depends(get_session),
) -> PolicyResponse:
    """Create a policy."""
    await _get_service_or_404(session, payload.service_id)
    if payload.agent_token_id is not None:
        await _get_agent_token_for_org_or_404(
            session,
            org_id=admin_token.org_id,
            agent_token_id=payload.agent_token_id,
        )
    await _ensure_policy_available(
        session,
        org_id=admin_token.org_id,
        service_id=payload.service_id,
        agent_token_id=payload.agent_token_id,
    )
    policy = Policy(org_id=admin_token.org_id, **payload.model_dump())
    session.add(policy)
    await session.flush()
    await log_event(
        session,
        org_id=admin_token.org_id,
        action="policy_created",
        resource_type="policy",
        resource_id=str(policy.id),
        metadata={"service_id": str(policy.service_id)},
    )
    await commit_session(session)
    return PolicyResponse.model_validate(policy)


@router.put("/policies/{policy_id}", response_model=PolicyResponse)
async def update_policy(
    policy_id: str,
    payload: PolicyUpdateRequest,
    admin_token: AdminToken = Depends(require_admin_token),
    session: AsyncSession = Depends(get_session),
) -> PolicyResponse:
    """Update a policy."""
    result = await session.execute(
        select(Policy).where(
            Policy.id == policy_id,
            Policy.org_id == admin_token.org_id,
        )
    )
    policy = result.scalar_one_or_none()
    if policy is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Policy not found",
        )
    for field, value in payload.model_dump(exclude_none=True).items():
        setattr(policy, field, value)
    await log_event(
        session,
        org_id=admin_token.org_id,
        action="policy_updated",
        resource_type="policy",
        resource_id=str(policy.id),
        metadata={},
    )
    await commit_session(session)
    return PolicyResponse.model_validate(policy)


@router.get("/policies", response_model=list[PolicyResponse])
async def list_policies(
    admin_token: AdminToken = Depends(require_admin_token),
    session: AsyncSession = Depends(get_session),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> list[PolicyResponse]:
    """List policies."""
    result = await session.execute(
        select(Policy)
        .where(Policy.org_id == admin_token.org_id)
        .order_by(Policy.created_at.desc(), Policy.id.desc())
        .limit(limit)
        .offset(offset)
    )
    return [PolicyResponse.model_validate(row) for row in result.scalars().all()]


@router.get("/checkouts", response_model=list[CheckoutAdminResponse])
async def list_checkouts(
    admin_token: AdminToken = Depends(require_admin_token),
    session: AsyncSession = Depends(get_session),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> list[CheckoutAdminResponse]:
    """List checkouts for the organization."""
    result = await session.execute(
        select(Checkout)
        .join(AgentToken, AgentToken.id == Checkout.agent_token_id)
        .where(AgentToken.org_id == admin_token.org_id)
        .order_by(Checkout.checked_out_at.desc(), Checkout.id.desc())
        .limit(limit)
        .offset(offset)
    )
    return [CheckoutAdminResponse.model_validate(row) for row in result.scalars().all()]


@router.post("/checkouts/{checkout_id}/revoke", response_model=CheckoutAdminResponse)
async def revoke_checkout_route(
    checkout_id: str,
    admin_token: AdminToken = Depends(require_admin_token),
    session: AsyncSession = Depends(get_session),
) -> CheckoutAdminResponse:
    """Revoke a checkout record."""
    checkout = await revoke_checkout(
        session,
        checkout_id=checkout_id,
        org_id=admin_token.org_id,
    )
    await commit_session(session)
    return CheckoutAdminResponse.model_validate(checkout)


@router.get("/audit", response_model=list[AuditResponse])
async def list_audit_events(
    admin_token: AdminToken = Depends(require_admin_token),
    session: AsyncSession = Depends(get_session),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> list[AuditResponse]:
    """List audit events for the organization."""
    result = await session.execute(
        select(AuditLog)
        .where(AuditLog.org_id == admin_token.org_id)
        .order_by(AuditLog.timestamp.desc(), AuditLog.id.desc())
        .limit(limit)
        .offset(offset)
    )
    return [AuditResponse.model_validate(row) for row in result.scalars().all()]
