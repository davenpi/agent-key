"""Python SDK tests."""

from uuid import uuid4

import httpx
import pytest

from agent_key import (
    AgentKeyAuthError,
    AgentKeyClient,
    AgentKeyConflictError,
    AgentKeyValidationError,
)


class TestAgentKeyClient:
    """SDK client behavior tests."""

    def test_from_env_requires_agent_token(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Reject missing agent token environment configuration.

        Parameters
        ----------
        monkeypatch : pytest.MonkeyPatch
            Environment monkeypatch helper.

        Returns
        -------
        None
            Asserts env validation.
        """
        monkeypatch.delenv("AGENT_KEY_AGENT_TOKEN", raising=False)
        monkeypatch.setenv("AGENT_KEY_BASE_URL", "http://example.test")

        with pytest.raises(AgentKeyValidationError):
            AgentKeyClient.from_env()

    def test_checkout_context_manager_auto_returns(self) -> None:
        """Auto-return a checkout when leaving the context manager.

        Returns
        -------
        None
            Asserts checkout and return request flow.
        """
        checkout_id = str(uuid4())
        requests: list[tuple[str, str]] = []

        def handler(request: httpx.Request) -> httpx.Response:
            requests.append((request.method, request.url.path))
            if (
                request.method == "POST"
                and request.url.path == "/v1/credentials/checkout"
            ):
                return httpx.Response(
                    200,
                    json={
                        "checkout_id": checkout_id,
                        "api_key": "sk-test",
                        "service": "openai",
                        "checked_out_at": "2026-02-28T10:00:00Z",
                        "expires_at": "2026-02-28T11:00:00Z",
                        "note": "vault mode",
                    },
                )
            if (
                request.method == "POST"
                and request.url.path == "/v1/credentials/return"
            ):
                return httpx.Response(200, json={"message": "Checkout returned"})
            raise AssertionError(
                f"Unexpected request {request.method} {request.url.path}"
            )

        client = AgentKeyClient(
            base_url="http://agent-key.test",
            agent_token="agt_test",
            transport=httpx.MockTransport(handler),
        )

        with client.checkout("openai", ttl=300) as checkout:
            assert checkout.api_key == "sk-test"
            assert checkout.result.service == "openai"
            assert checkout.result.ttl_remaining_seconds >= 0

        assert requests == [
            ("POST", "/v1/credentials/checkout"),
            ("POST", "/v1/credentials/return"),
        ]

    def test_checkout_raises_typed_auth_error(self) -> None:
        """Map authentication failures to a typed exception.

        Returns
        -------
        None
            Asserts typed error mapping.
        """

        def handler(request: httpx.Request) -> httpx.Response:
            _ = request
            return httpx.Response(401, json={"detail": "Invalid agent token"})

        client = AgentKeyClient(
            base_url="http://agent-key.test",
            agent_token="bad-token",
            transport=httpx.MockTransport(handler),
        )

        with pytest.raises(AgentKeyAuthError) as exc_info:
            client.checkout("openai")

        assert exc_info.value.status_code == 401

    def test_return_checkout_surfaces_conflict(self) -> None:
        """Map return conflicts to the typed conflict exception.

        Returns
        -------
        None
            Asserts conflict handling.
        """

        def handler(request: httpx.Request) -> httpx.Response:
            _ = request
            return httpx.Response(409, json={"detail": "Checkout has expired"})

        client = AgentKeyClient(
            base_url="http://agent-key.test",
            agent_token="agt_test",
            transport=httpx.MockTransport(handler),
        )

        with pytest.raises(AgentKeyConflictError) as exc_info:
            client.return_checkout(uuid4())

        assert exc_info.value.status_code == 409
        assert str(exc_info.value) == "Checkout has expired"

    def test_list_services_uses_env_configuration(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Build the client from env and fetch visible services.

        Parameters
        ----------
        monkeypatch : pytest.MonkeyPatch
            Environment monkeypatch helper.

        Returns
        -------
        None
            Asserts env-based configuration and response parsing.
        """
        monkeypatch.setenv("AGENT_KEY_BASE_URL", "http://agent-key.test")
        monkeypatch.setenv("AGENT_KEY_AGENT_TOKEN", "agt_test")

        def handler(request: httpx.Request) -> httpx.Response:
            assert request.headers["Authorization"] == "Bearer agt_test"
            assert request.url.path == "/v1/services"
            return httpx.Response(
                200,
                json=[
                    {
                        "provider": "openai",
                        "name": "OpenAI",
                        "base_url": "https://api.openai.com/v1",
                    }
                ],
            )

        client = AgentKeyClient(
            base_url="http://agent-key.test",
            agent_token="agt_test",
            transport=httpx.MockTransport(handler),
        )

        services = client.list_services()

        assert len(services) == 1
        assert services[0].provider == "openai"

    def test_list_active_checkouts_returns_typed_records(self) -> None:
        """Parse active checkout records into a typed SDK response.

        Returns
        -------
        None
            Asserts active-checkout parsing.
        """

        def handler(request: httpx.Request) -> httpx.Response:
            assert request.url.path == "/v1/credentials/active"
            return httpx.Response(
                200,
                json=[
                    {
                        "id": str(uuid4()),
                        "stored_key_id": str(uuid4()),
                        "policy_id": str(uuid4()),
                        "checked_out_at": "2026-02-28T10:00:00Z",
                        "expires_at": "2026-02-28T11:00:00Z",
                        "returned_at": None,
                        "revoked_at": None,
                    }
                ],
            )

        client = AgentKeyClient(
            base_url="http://agent-key.test",
            agent_token="agt_test",
            transport=httpx.MockTransport(handler),
        )

        checkouts = client.list_active_checkouts()

        assert len(checkouts) == 1
        assert checkouts[0].returned_at is None
