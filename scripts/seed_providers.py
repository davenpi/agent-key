"""Seed provider services and stored keys through the admin API."""

from __future__ import annotations

import os
from dataclasses import dataclass

import anyio
import httpx


@dataclass(frozen=True, slots=True)
class ProviderSeed:
    """Provider seed definition.

    Attributes
    ----------
    provider : str
        Provider slug used by the API.
    name : str
        Human-readable provider name.
    base_url : str
        Upstream provider base URL.
    env_var : str
        Environment variable containing the provider key.
    label : str
        Stored-key label to use when seeding.
    """

    provider: str
    name: str
    base_url: str
    env_var: str
    label: str = "local-seed"


PROVIDERS: tuple[ProviderSeed, ...] = (
    ProviderSeed(
        provider="openai",
        name="OpenAI",
        base_url="https://api.openai.com/v1",
        env_var="OPENAI_API_KEY",
    ),
    ProviderSeed(
        provider="anthropic",
        name="Anthropic",
        base_url="https://api.anthropic.com",
        env_var="ANTHROPIC_API_KEY",
    ),
)


async def ensure_service(
    client: httpx.AsyncClient, provider: ProviderSeed
) -> dict[str, str]:
    """Ensure a provider service exists.

    Parameters
    ----------
    client : httpx.AsyncClient
        Authenticated admin API client.
    provider : ProviderSeed
        Provider definition to ensure.

    Returns
    -------
    dict[str, str]
        Service payload from the API.
    """
    response = await client.get(
        "/v1/admin/services",
        params={"limit": 200, "offset": 0},
    )
    response.raise_for_status()
    for service in response.json():
        if service["provider"] == provider.provider:
            return service

    create_response = await client.post(
        "/v1/admin/services",
        json={
            "provider": provider.provider,
            "name": provider.name,
            "base_url": provider.base_url,
        },
    )
    if create_response.status_code not in (200, 409):
        create_response.raise_for_status()
    if create_response.status_code == 200:
        return create_response.json()

    response = await client.get(
        "/v1/admin/services",
        params={"limit": 200, "offset": 0},
    )
    response.raise_for_status()
    for service in response.json():
        if service["provider"] == provider.provider:
            return service
    raise RuntimeError(f"Unable to resolve service for provider {provider.provider}")


async def ensure_stored_key(
    client: httpx.AsyncClient,
    *,
    service_id: str,
    label: str,
    api_key: str,
) -> None:
    """Ensure a stored key exists for the service label.

    Parameters
    ----------
    client : httpx.AsyncClient
        Authenticated admin API client.
    service_id : str
        Service identifier.
    label : str
        Stored-key label.
    api_key : str
        Provider API key.

    Returns
    -------
    None
        Creates the key if needed.
    """
    response = await client.post(
        "/v1/admin/keys",
        json={"service_id": service_id, "label": label, "api_key": api_key},
    )
    if response.status_code in (200, 409):
        return
    response.raise_for_status()


async def main() -> None:
    """Seed provider services and stored keys from environment variables.

    Returns
    -------
    None
        Seeds configured providers and prints a short summary.
    """
    base_url = os.environ.get("AGENT_KEY_BASE_URL", "http://127.0.0.1:8000")
    admin_token = os.environ.get("AGENT_KEY_ADMIN_TOKEN")
    if not admin_token:
        raise SystemExit("AGENT_KEY_ADMIN_TOKEN is required")

    headers = {"Authorization": f"Bearer {admin_token}"}
    async with httpx.AsyncClient(
        base_url=base_url,
        headers=headers,
        timeout=10.0,
    ) as client:
        for provider in PROVIDERS:
            api_key = os.environ.get(provider.env_var)
            if not api_key:
                continue
            service = await ensure_service(client, provider)
            await ensure_stored_key(
                client,
                service_id=service["id"],
                label=provider.label,
                api_key=api_key,
            )
            print(f"seeded {provider.provider}")


if __name__ == "__main__":
    anyio.run(main)
