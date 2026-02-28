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

## Notes

- The app no longer creates tables automatically on startup.
- Schema changes must go through Alembic migrations.
- Tests still use isolated SQLite databases for speed.
