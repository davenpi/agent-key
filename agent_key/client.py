"""Synchronous Python SDK client."""

from __future__ import annotations

import os
from datetime import datetime
from time import sleep
from typing import Any
from uuid import UUID

import httpx

from agent_key.exceptions import (
    AgentKeyAPIError,
    AgentKeyAuthError,
    AgentKeyConflictError,
    AgentKeyNotFoundError,
    AgentKeyRateLimitError,
    AgentKeyValidationError,
)
from agent_key.types import (
    ActiveCheckoutInfo,
    CheckoutHandle,
    CheckoutResult,
    ServiceInfo,
)


class AgentKeyClient:
    """Client for the agent-facing Agent Key API.

    Parameters
    ----------
    base_url : str
        Agent Key service base URL.
    agent_token : str
        Agent bearer token.
    timeout : float, default=10.0
        Request timeout in seconds.
    max_retries : int, default=2
        Number of retries for transient errors.
    transport : httpx.BaseTransport | None, default=None
        Optional transport for tests or advanced usage.
    """

    def __init__(
        self,
        *,
        base_url: str,
        agent_token: str,
        timeout: float = 10.0,
        max_retries: int = 2,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.agent_token = agent_token
        self.timeout = timeout
        self.max_retries = max_retries
        self._client = httpx.Client(
            base_url=self.base_url,
            headers={"Authorization": f"Bearer {self.agent_token}"},
            timeout=self.timeout,
            transport=transport,
        )

    @classmethod
    def from_env(cls) -> "AgentKeyClient":
        """Build a client from environment variables.

        Expected variables
        ------------------
        AGENT_KEY_BASE_URL
            Agent Key base URL. Defaults to ``http://127.0.0.1:8000``.
        AGENT_KEY_AGENT_TOKEN
            Required agent bearer token.

        Returns
        -------
        AgentKeyClient
            Configured SDK client.
        """
        base_url = os.environ.get("AGENT_KEY_BASE_URL", "http://127.0.0.1:8000")
        agent_token = os.environ.get("AGENT_KEY_AGENT_TOKEN")
        if not agent_token:
            raise AgentKeyValidationError(
                "AGENT_KEY_AGENT_TOKEN is required to create the client"
            )
        return cls(base_url=base_url, agent_token=agent_token)

    def close(self) -> None:
        """Close the underlying HTTP client.

        Returns
        -------
        None
            Releases HTTP resources.
        """
        self._client.close()

    def list_services(self, *, limit: int = 50, offset: int = 0) -> list[ServiceInfo]:
        """List services visible to the agent.

        Parameters
        ----------
        limit : int, default=50
            Page size.
        offset : int, default=0
            Page offset.

        Returns
        -------
        list[ServiceInfo]
            Visible services.
        """
        response = self._request(
            "GET",
            "/v1/services",
            params={"limit": limit, "offset": offset},
        )
        return [ServiceInfo(**item) for item in response.json()]

    def checkout(self, service: str, ttl: int | None = None) -> CheckoutHandle:
        """Check out a provider key.

        Parameters
        ----------
        service : str
            Provider slug.
        ttl : int | None, default=None
            Optional requested TTL in seconds.

        Returns
        -------
        CheckoutHandle
            Context-manageable checkout handle.
        """
        payload: dict[str, Any] = {"service": service}
        if ttl is not None:
            payload["ttl"] = ttl
        response = self._request("POST", "/v1/credentials/checkout", json=payload)
        data = response.json()
        result = CheckoutResult(
            checkout_id=UUID(data["checkout_id"]),
            api_key=data["api_key"],
            service=data["service"],
            checked_out_at=_parse_datetime(data["checked_out_at"]),
            expires_at=_parse_datetime(data["expires_at"]),
            note=data["note"],
        )
        return CheckoutHandle(client=self, result=result)

    def return_checkout(self, checkout_id: UUID) -> None:
        """Return a checkout early.

        Parameters
        ----------
        checkout_id : UUID
            Checkout identifier.

        Returns
        -------
        None
            Returns the checkout.
        """
        self._request(
            "POST",
            "/v1/credentials/return",
            json={"checkout_id": str(checkout_id)},
        )

    def list_active_checkouts(
        self, *, limit: int = 50, offset: int = 0
    ) -> list[ActiveCheckoutInfo]:
        """List active checkout records.

        Parameters
        ----------
        limit : int, default=50
            Page size.
        offset : int, default=0
            Page offset.

        Returns
        -------
        list[ActiveCheckoutInfo]
            Active checkout records.
        """
        response = self._request(
            "GET",
            "/v1/credentials/active",
            params={"limit": limit, "offset": offset},
        )
        items: list[ActiveCheckoutInfo] = []
        for item in response.json():
            items.append(
                ActiveCheckoutInfo(
                    checkout_id=UUID(item["id"]),
                    stored_key_id=UUID(item["stored_key_id"]),
                    policy_id=UUID(item["policy_id"]),
                    checked_out_at=_parse_datetime(item["checked_out_at"]),
                    expires_at=_parse_datetime(item["expires_at"]),
                    returned_at=(
                        _parse_datetime(item["returned_at"])
                        if item["returned_at"] is not None
                        else None
                    ),
                    revoked_at=(
                        _parse_datetime(item["revoked_at"])
                        if item["revoked_at"] is not None
                        else None
                    ),
                )
            )
        return items

    def _request(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        """Send an HTTP request with light retry logic.

        Parameters
        ----------
        method : str
            HTTP method.
        path : str
            Relative request path.
        **kwargs : Any
            Additional request arguments.

        Returns
        -------
        httpx.Response
            Successful response.
        """
        attempts = self.max_retries + 1
        last_exception: Exception | None = None
        for attempt in range(attempts):
            try:
                response = self._client.request(method, path, **kwargs)
            except httpx.HTTPError as exc:
                last_exception = exc
                if attempt < self.max_retries:
                    sleep(0.1 * (attempt + 1))
                    continue
                raise AgentKeyAPIError(str(exc)) from exc

            if response.status_code < 400:
                return response
            if _is_transient_response(response) and attempt < self.max_retries:
                sleep(0.1 * (attempt + 1))
                continue
            raise _exception_for_response(response)

        if last_exception is not None:
            raise AgentKeyAPIError(str(last_exception)) from last_exception
        raise AgentKeyAPIError("Request failed")

    def __enter__(self) -> "AgentKeyClient":
        """Enter the client context.

        Returns
        -------
        AgentKeyClient
            This client.
        """
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        """Close the client on context exit.

        Parameters
        ----------
        exc_type : type[BaseException] | None
            Exception type if raised.
        exc_value : BaseException | None
            Exception instance if raised.
        traceback : object | None
            Exception traceback if raised.

        Returns
        -------
        None
            Closes the underlying HTTP client.
        """
        _ = (exc_type, exc_value, traceback)
        self.close()


def _parse_datetime(value: str) -> datetime:
    """Parse an ISO datetime string.

    Parameters
    ----------
    value : str
        ISO-formatted datetime string.

    Returns
    -------
    datetime
        Parsed datetime.
    """
    normalized = value.replace("Z", "+00:00")
    return datetime.fromisoformat(normalized)


def _is_transient_response(response: httpx.Response) -> bool:
    """Return whether a response is transient.

    Parameters
    ----------
    response : httpx.Response
        HTTP response.

    Returns
    -------
    bool
        Whether the response is worth retrying.
    """
    return response.status_code in {429, 502, 503, 504}


def _exception_for_response(response: httpx.Response) -> AgentKeyAPIError:
    """Map an error response to a typed SDK exception.

    Parameters
    ----------
    response : httpx.Response
        HTTP response.

    Returns
    -------
    AgentKeyAPIError
        Typed SDK error.
    """
    try:
        data = response.json()
    except ValueError:
        data = {}
    detail = data.get("detail") if isinstance(data, dict) else None
    message = detail or f"Agent Key request failed with status {response.status_code}"

    if response.status_code == 401:
        return AgentKeyAuthError(message, status_code=response.status_code)
    if response.status_code == 404:
        return AgentKeyNotFoundError(message, status_code=response.status_code)
    if response.status_code == 409:
        return AgentKeyConflictError(message, status_code=response.status_code)
    if response.status_code == 429:
        return AgentKeyRateLimitError(message, status_code=response.status_code)
    if response.status_code in {400, 403, 422}:
        return AgentKeyValidationError(message, status_code=response.status_code)
    return AgentKeyAPIError(message, status_code=response.status_code)
