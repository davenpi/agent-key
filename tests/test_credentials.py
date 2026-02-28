"""Credential-flow tests."""

import pytest


class TestCredentialFlow:
    """End-to-end credential checkout scenarios."""

    @pytest.mark.asyncio
    async def test_bootstrap_and_checkout_flow(self, client) -> None:
        """Allow an admin to bootstrap and an agent to check out a key.

        Parameters
        ----------
        client : AsyncClient
            Test HTTP client.

        Returns
        -------
        None
            Asserts the full happy path.
        """
        bootstrap = await client.post(
            "/v1/bootstrap",
            json={"organization_name": "Acme", "admin_token_name": "root"},
        )
        assert bootstrap.status_code == 200
        admin_token = bootstrap.json()["admin_token"]["token"]
        admin_headers = {"Authorization": f"Bearer {admin_token}"}

        service_response = await client.post(
            "/v1/admin/services",
            headers=admin_headers,
            json={
                "provider": "openai",
                "name": "OpenAI",
                "base_url": "https://api.openai.com/v1",
            },
        )
        assert service_response.status_code == 200
        service_id = service_response.json()["id"]

        key_response = await client.post(
            "/v1/admin/keys",
            headers=admin_headers,
            json={
                "service_id": service_id,
                "label": "primary",
                "api_key": "sk-test",
            },
        )
        assert key_response.status_code == 200

        agent_response = await client.post(
            "/v1/admin/agents",
            headers=admin_headers,
            json={"name": "worker"},
        )
        assert agent_response.status_code == 200
        agent_token = agent_response.json()["token"]
        agent_id = agent_response.json()["id"]

        policy_response = await client.post(
            "/v1/admin/policies",
            headers=admin_headers,
            json={
                "service_id": service_id,
                "agent_token_id": agent_id,
                "max_checkouts_per_window": 5,
                "checkout_window": "daily",
                "max_active_checkouts": 1,
                "max_ttl_seconds": 3600,
                "enabled": True,
            },
        )
        assert policy_response.status_code == 200

        agent_headers = {"Authorization": f"Bearer {agent_token}"}
        visible_services = await client.get("/v1/services", headers=agent_headers)
        assert visible_services.status_code == 200
        assert visible_services.json()[0]["provider"] == "openai"

        checkout_response = await client.post(
            "/v1/credentials/checkout",
            headers=agent_headers,
            json={"service": "openai", "ttl": 300},
        )
        assert checkout_response.status_code == 200
        payload = checkout_response.json()
        assert payload["api_key"] == "sk-test"
        assert payload["service"] == "openai"

        active_response = await client.get(
            "/v1/credentials/active",
            headers=agent_headers,
        )
        assert active_response.status_code == 200
        assert len(active_response.json()) == 1

        return_response = await client.post(
            "/v1/credentials/return",
            headers=agent_headers,
            json={"checkout_id": payload["checkout_id"]},
        )
        assert return_response.status_code == 200

    @pytest.mark.asyncio
    async def test_checkout_denied_without_policy(self, client) -> None:
        """Reject checkouts when no matching policy exists.

        Parameters
        ----------
        client : AsyncClient
            Test HTTP client.

        Returns
        -------
        None
            Asserts policy denial.
        """
        bootstrap = await client.post(
            "/v1/bootstrap",
            json={"organization_name": "Acme", "admin_token_name": "root"},
        )
        admin_token = bootstrap.json()["admin_token"]["token"]
        admin_headers = {"Authorization": f"Bearer {admin_token}"}

        await client.post(
            "/v1/admin/services",
            headers=admin_headers,
            json={
                "provider": "anthropic",
                "name": "Anthropic",
                "base_url": "https://api.anthropic.com",
            },
        )
        agent_response = await client.post(
            "/v1/admin/agents",
            headers=admin_headers,
            json={"name": "worker"},
        )
        agent_token = agent_response.json()["token"]
        agent_headers = {"Authorization": f"Bearer {agent_token}"}

        denied = await client.post(
            "/v1/credentials/checkout",
            headers=agent_headers,
            json={"service": "anthropic", "ttl": 300},
        )
        assert denied.status_code == 403


class TestPolicyLimits:
    """Policy-enforcement tests."""

    @pytest.mark.asyncio
    async def test_active_checkout_cap_is_enforced(self, client) -> None:
        """Block a second checkout when the active cap is reached.

        Parameters
        ----------
        client : AsyncClient
            Test HTTP client.

        Returns
        -------
        None
            Asserts the active checkout cap.
        """
        bootstrap = await client.post(
            "/v1/bootstrap",
            json={"organization_name": "Acme", "admin_token_name": "root"},
        )
        admin_token = bootstrap.json()["admin_token"]["token"]
        admin_headers = {"Authorization": f"Bearer {admin_token}"}
        service_response = await client.post(
            "/v1/admin/services",
            headers=admin_headers,
            json={
                "provider": "openai",
                "name": "OpenAI",
                "base_url": "https://api.openai.com/v1",
            },
        )
        service_id = service_response.json()["id"]
        await client.post(
            "/v1/admin/keys",
            headers=admin_headers,
            json={"service_id": service_id, "label": "primary", "api_key": "sk-test"},
        )
        agent_response = await client.post(
            "/v1/admin/agents",
            headers=admin_headers,
            json={"name": "worker"},
        )
        agent_token = agent_response.json()["token"]
        agent_id = agent_response.json()["id"]
        await client.post(
            "/v1/admin/policies",
            headers=admin_headers,
            json={
                "service_id": service_id,
                "agent_token_id": agent_id,
                "max_checkouts_per_window": 5,
                "checkout_window": "daily",
                "max_active_checkouts": 1,
                "max_ttl_seconds": 3600,
                "enabled": True,
            },
        )
        agent_headers = {"Authorization": f"Bearer {agent_token}"}
        first = await client.post(
            "/v1/credentials/checkout",
            headers=agent_headers,
            json={"service": "openai", "ttl": 300},
        )
        assert first.status_code == 200
        second = await client.post(
            "/v1/credentials/checkout",
            headers=agent_headers,
            json={"service": "openai", "ttl": 300},
        )
        assert second.status_code == 403


class TestPagination:
    """Pagination behavior tests."""

    @pytest.mark.asyncio
    async def test_agent_list_pagination_is_stably_ordered(self, client) -> None:
        """Return paginated agent lists in deterministic newest-first order.

        Parameters
        ----------
        client : AsyncClient
            Test HTTP client.

        Returns
        -------
        None
            Asserts stable ordering across paginated requests.
        """
        bootstrap = await client.post(
            "/v1/bootstrap",
            json={"organization_name": "Acme", "admin_token_name": "root"},
        )
        admin_token = bootstrap.json()["admin_token"]["token"]
        admin_headers = {"Authorization": f"Bearer {admin_token}"}

        created_names: list[str] = []
        for name in ("agent-a", "agent-b", "agent-c"):
            response = await client.post(
                "/v1/admin/agents",
                headers=admin_headers,
                json={"name": name},
            )
            assert response.status_code == 200
            created_names.append(response.json()["name"])

        first_page = await client.get(
            "/v1/admin/agents?limit=2&offset=0",
            headers=admin_headers,
        )
        second_page = await client.get(
            "/v1/admin/agents?limit=2&offset=2",
            headers=admin_headers,
        )

        assert first_page.status_code == 200
        assert second_page.status_code == 200
        assert [row["name"] for row in first_page.json()] == ["agent-c", "agent-b"]
        assert [row["name"] for row in second_page.json()] == ["agent-a"]


class TestAdminConflicts:
    """Admin conflict handling tests."""

    @pytest.mark.asyncio
    async def test_duplicate_agent_name_returns_conflict(self, client) -> None:
        """Reject duplicate agent token names within the same org.

        Parameters
        ----------
        client : AsyncClient
            Test HTTP client.

        Returns
        -------
        None
            Asserts duplicate-name conflict handling.
        """
        bootstrap = await client.post(
            "/v1/bootstrap",
            json={"organization_name": "Acme", "admin_token_name": "root"},
        )
        admin_token = bootstrap.json()["admin_token"]["token"]
        admin_headers = {"Authorization": f"Bearer {admin_token}"}

        first = await client.post(
            "/v1/admin/agents",
            headers=admin_headers,
            json={"name": "worker"},
        )
        second = await client.post(
            "/v1/admin/agents",
            headers=admin_headers,
            json={"name": "worker"},
        )

        assert first.status_code == 200
        assert second.status_code == 409
        assert second.json()["detail"] == "Agent token name already exists"

    @pytest.mark.asyncio
    async def test_duplicate_policy_target_returns_conflict(self, client) -> None:
        """Reject duplicate policies for the same service target.

        Parameters
        ----------
        client : AsyncClient
            Test HTTP client.

        Returns
        -------
        None
            Asserts duplicate-policy conflict handling.
        """
        bootstrap = await client.post(
            "/v1/bootstrap",
            json={"organization_name": "Acme", "admin_token_name": "root"},
        )
        admin_token = bootstrap.json()["admin_token"]["token"]
        admin_headers = {"Authorization": f"Bearer {admin_token}"}

        service_response = await client.post(
            "/v1/admin/services",
            headers=admin_headers,
            json={
                "provider": "openai",
                "name": "OpenAI",
                "base_url": "https://api.openai.com/v1",
            },
        )
        service_id = service_response.json()["id"]

        first = await client.post(
            "/v1/admin/policies",
            headers=admin_headers,
            json={
                "service_id": service_id,
                "max_checkouts_per_window": 5,
                "checkout_window": "daily",
                "max_active_checkouts": 1,
                "max_ttl_seconds": 3600,
                "enabled": True,
            },
        )
        second = await client.post(
            "/v1/admin/policies",
            headers=admin_headers,
            json={
                "service_id": service_id,
                "max_checkouts_per_window": 10,
                "checkout_window": "daily",
                "max_active_checkouts": 2,
                "max_ttl_seconds": 1800,
                "enabled": True,
            },
        )

        assert first.status_code == 200
        assert second.status_code == 409
        assert (
            second.json()["detail"] == "Policy already exists for this service target"
        )
