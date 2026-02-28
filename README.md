## Agent Key

Credential broker for AI agents.

Current mode:

- admins store upstream provider keys
- agents authenticate to Agent Key
- Agent Key enforces checkout policy
- agents receive raw provider keys in vault-checkout mode

## Local Setup

Prerequisites:

- Python 3.12+
- `uv`
- Postgres

Install dependencies:

```bash
uv sync --dev
```

Copy the example environment:

```bash
cp .env.example .env
```

Start Postgres locally. Example with Docker:

```bash
docker run --name agent-key-postgres \
  -e POSTGRES_PASSWORD=postgres \
  -e POSTGRES_USER=postgres \
  -e POSTGRES_DB=agent_key \
  -p 5432:5432 \
  -d postgres:17
```

Apply migrations:

```bash
uv run alembic upgrade head
```

Run the app:

```bash
uv run uvicorn app.main:app --reload
```

Bootstrap the first org/admin token:

```bash
curl -X POST http://127.0.0.1:8000/v1/bootstrap \
  -H 'content-type: application/json' \
  -d '{"organization_name":"Acme","admin_token_name":"root"}'
```

Seed provider services and stored keys from local environment:

```bash
export AGENT_KEY_ADMIN_TOKEN="<bootstrap token>"
export OPENAI_API_KEY="sk-..."
export ANTHROPIC_API_KEY="sk-ant-..."
uv run python scripts/seed_providers.py
```

## Python SDK

The repo now includes a small Python SDK in the `agent_key` package.

Basic usage:

```python
from agent_key import AgentKeyClient

with AgentKeyClient.from_env() as client:
    with client.checkout("openai", ttl=300) as credential:
        print(credential.api_key)
```

Environment:

- `AGENT_KEY_BASE_URL` defaults to `http://127.0.0.1:8000`
- `AGENT_KEY_AGENT_TOKEN` is required

The checkout context manager automatically returns the checkout on exit.

## Notes

- The app no longer creates tables automatically on startup.
- Schema changes must go through Alembic migrations.
- Tests still use isolated SQLite databases for speed.
- The local seed script uses the admin HTTP API and is safe to rerun.
