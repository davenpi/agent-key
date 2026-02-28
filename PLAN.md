# Agent Key — Implementation Plan

## Product Thesis

The core problem is controlled credential issuance for non-human actors. AI agents need API keys to use third-party services, but the current process is designed for humans. This service gives agents a programmatic way to obtain credentials, governed by human-defined policies, with full auditability.

The product wedge is **convenience** — make it trivially easy for an agent to get a key. Governance and spend control become enforceable as the product matures into proxy and delegated-credential modes.

## Users and Buyers

- **Users**: AI agents, developers integrating agents with external APIs, platform teams managing shared access.
- **Buyers**: Engineering teams deploying multiple agents, AI platform teams, startups building agentic products across providers.

## Two Access Modes

The product has two fundamentally different modes of operation. Being honest about what each mode can and cannot enforce is critical.

### Mode 1: Vault Checkout (MVP)

The human deposits provider API keys. The agent checks them out, governed by policy. The agent receives the raw upstream key.

**What we can enforce:**

- Which services an agent may access
- How often keys are checked out (issuance-rate limits)
- Maximum concurrent checkouts
- Checkout quotas (e.g., 100 checkouts/day)
- Maximum checkout duration (re-checkout required after TTL)

**What we cannot enforce in this mode:**

- What the agent does with the key after checkout (scope, spend, request volume)
- Immediate revocation of upstream access (we revoke future checkouts, not the live key)
- Real-time budget limits

This mode is honest about its limits: it controls _access to keys_, not _usage of keys_.

### Mode 2: Brokered Access (Phase 3+)

Two sub-modes, depending on provider capabilities:

- **Proxy**: Agent calls us, we forward to upstream with the real key. Enables request-level policy, metering, and spend enforcement. Agent never sees the raw key.
- **Delegated ephemeral credentials**: For providers that support it (AWS STS, GitHub Apps, GCP service accounts), we mint short-lived, scoped credentials natively. Strongest guarantees.

This is where scope enforcement, budget caps, and real-time controls become genuine.

## Architecture

```
┌─────────────┐       ┌─────────────────────────────────────┐
│              │       │           Agent Key Service          │
│   AI Agent   │──────▶│                                     │
│              │◀──────│  ┌───────────┐    ┌──────────────┐  │
└─────────────┘       │  │  Control   │    │  Data Plane  │  │
                      │  │   Plane    │    │              │  │
┌─────────────┐       │  │           │    │  - Credential │  │
│   Human     │──────▶│  │  - Policy  │    │    issuance  │  │
│   Admin     │       │  │  - Config  │    │  - Checkout   │  │
└─────────────┘       │  │  - Audit   │    │  - (Proxy)   │  │
                      │  └───────────┘    └──────────────┘  │
                      │         │                │           │
                      │    ┌────▼────────────────▼────┐     │
                      │    │     Postgres + KMS        │     │
                      │    └──────────────────────────┘     │
                      └─────────────────────────────────────┘
```

**Control plane**: Tenant management, agent identity verification, policy storage and evaluation, audit and billing records. Handles admin workflows.

**Data plane**: Low-latency credential issuance, checkout flow, and (later) request proxying. Kept fast and narrow.

## Data Model

### Organizations

The billing/ownership entity. A human creates an org.

- `id` (uuid), `name`, `created_at`

### Agent Tokens

How an agent authenticates. Issued by a human, used by the agent.

- `id` (uuid), `org_id`, `name`, `token_hash`, `created_at`, `revoked_at`
- MVP: service tokens (hashed, static). Auth layer designed to accept OIDC JWTs as a fast follow.

### Services

Third-party providers we support.

- `id` (uuid), `name`, `provider` (e.g., "openai"), `base_url`

### Stored Keys

Human-deposited provider API keys. Encrypted at rest via envelope encryption.

- `id` (uuid), `org_id`, `service_id`, `encrypted_key`, `key_ciphertext_blob` (for KMS envelope)
- `label`, `created_at`, `revoked_at`

### Policies

Rules governing what an agent can check out. Deny-by-default.

- `id` (uuid), `org_id`, `agent_token_id` (nullable — org-wide if null)
- `service_id`
- `max_checkouts_per_window`, `checkout_window` (e.g., "daily") — issuance-rate limit
- `max_active_checkouts` — how many open checkout records an agent may hold at once
- `max_ttl_seconds` — maximum checkout duration
- `enabled`

Note: `allowed_scopes` and `max_spend_cents` are intentionally omitted from MVP. These become meaningful when proxy mode or delegated credentials are available.

### Checkouts

When an agent checks out a key, we create a time-bound record.

- `id` (uuid), `agent_token_id`, `stored_key_id`, `policy_id`
- `checked_out_at`, `expires_at`, `returned_at`, `revoked_at`

Named "checkout" rather than "lease" to avoid implying upstream-enforced expiry. This is a local record — the upstream key doesn't expire when the checkout does.

### Audit Log

Append-only. No updates or deletes.

- `id` (uuid), `org_id`, `agent_token_id`
- `action` (e.g., "key_checked_out", "key_returned", "checkout_revoked", "policy_created")
- `resource_type`, `resource_id`, `metadata` (JSON), `timestamp`

## API

### Agent-Facing

Authenticated via `Authorization: Bearer <agent_token>`. Auth layer is pluggable — service tokens now, OIDC later.

```
POST   /v1/credentials/checkout   — Check out a key for a service
POST   /v1/credentials/return     — Return a checkout early
GET    /v1/credentials/active     — List active checkouts for this agent
GET    /v1/services               — List available services for this agent
```

#### `POST /v1/credentials/checkout`

```json
// Request
{
  "service": "openai",
  "ttl": 3600
}

// Response
{
  "checkout_id": "chk_abc123",
  "api_key": "sk-...",
  "service": "openai",
  "checked_out_at": "2026-03-01T10:00:00Z",
  "expires_at": "2026-03-01T11:00:00Z",
  "note": "This is a raw provider key. Scope and spend are not enforced by Agent Key in vault mode."
}
```

The response explicitly tells the agent (and the developer reading logs) what the service does and does not control.

### Admin-Facing

Authenticated via org-level admin credentials. MVP choice: a separate hashed admin bearer token per org, with the auth layer designed to support hosted user auth or SSO later.

```
POST   /v1/admin/agents           — Create an agent token
DELETE /v1/admin/agents/:id       — Revoke an agent token
GET    /v1/admin/agents           — List agent tokens

POST   /v1/admin/keys             — Deposit a key into the vault
DELETE /v1/admin/keys/:id         — Revoke a stored key
GET    /v1/admin/keys             — List stored keys (metadata only, never plaintext)

POST   /v1/admin/policies         — Create a policy
PUT    /v1/admin/policies/:id     — Update a policy
GET    /v1/admin/policies         — List policies

GET    /v1/admin/checkouts        — List all active checkouts
POST   /v1/admin/checkouts/:id/revoke — Revoke a checkout (blocks future re-checkout)

GET    /v1/admin/audit            — Query audit log
```

## Tech Stack

- **Framework**: FastAPI
- **Database**: Postgres (via SQLAlchemy + asyncpg)
- **Migrations**: Alembic
- **Encryption**: Envelope encryption — data key encrypted by a KMS master key. For local dev, a file-based master key with clear warnings.
- **Auth**: Service tokens (hashed with argon2) now. Auth layer designed as a pluggable dependency so OIDC can slot in without refactoring routes.
- **Validation**: Pydantic v2
- **Testing**: pytest + httpx (async test client)

## File Structure

```
agent-key/
├── main.py                    # App entrypoint, FastAPI app factory
├── pyproject.toml
├── alembic.ini
├── alembic/                   # Migrations
├── app/
│   ├── __init__.py
│   ├── config.py              # Settings via pydantic-settings, env vars
│   ├── database.py            # Async engine, session factory, base model
│   ├── models/                # SQLAlchemy ORM models
│   │   ├── __init__.py
│   │   ├── org.py
│   │   ├── agent_token.py
│   │   ├── service.py
│   │   ├── stored_key.py
│   │   ├── policy.py
│   │   ├── checkout.py
│   │   └── audit.py
│   ├── schemas/               # Pydantic request/response models
│   │   ├── __init__.py
│   │   ├── credentials.py
│   │   └── admin.py
│   ├── routers/               # API route handlers
│   │   ├── __init__.py
│   │   ├── credentials.py
│   │   └── admin.py
│   ├── services/              # Business logic
│   │   ├── __init__.py
│   │   ├── auth.py            # Pluggable auth (service token now, OIDC later)
│   │   ├── vault.py           # Encrypt/decrypt stored keys
│   │   ├── policy.py          # Policy evaluation
│   │   ├── checkout.py        # Checkout/return flow
│   │   └── audit.py           # Audit log writes and queries
│   └── crypto/                # Encryption primitives
│       ├── __init__.py
│       └── envelope.py        # Envelope encryption, KMS integration
└── tests/
    ├── __init__.py
    ├── conftest.py            # Fixtures: test DB, test client, factory helpers
    ├── test_credentials.py
    ├── test_admin.py
    ├── test_policy.py
    └── test_vault.py
```

## Implementation Phases

### Phase 1: Core MVP

Get the basic loop working: human deposits key → agent checks out key → agent uses key → checkout expires.

1. **Project setup** — FastAPI app factory, Postgres via SQLAlchemy async, Pydantic settings, Alembic
2. **Data models & migrations** — All tables above
3. **Crypto layer** — Envelope encryption module. KMS-backed in prod, file-based master key for local dev
4. **Auth** — Pluggable auth dependency. Service token implementation (argon2 hashed). Interface designed for OIDC drop-in
5. **Key vault** — Deposit, retrieve (decrypted), revoke stored keys
6. **Policy engine** — Evaluate on checkout: service allowed? Within checkout rate limit? Under active checkout cap? TTL within bounds?
7. **Checkout flow** — Issue time-bound checkouts, return decrypted key, handle returns and expiry
8. **Audit logging** — Append-only log for every action
9. **Admin endpoints** — Full CRUD for agents, keys, policies, plus checkout and audit queries
10. **Agent endpoints** — Checkout, return, list active, list services
11. **Tests** — Unit tests for policy engine and vault, integration tests for the full checkout flow

### Phase 2: Hardening

- Rate limiting per agent token (in-process to start, Redis when needed)
- Checkout expiry enforcement (background task or on-read check)
- Key rotation support (re-encrypt stored keys with new data key)
- Input validation and error handling polish
- OIDC auth provider implementation
- Structured logging and secret redaction guarantees

### Phase 3: Brokered Access

- **Proxy mode**: Agent calls our API, we forward to upstream with real key. Enables real-time request metering, scope enforcement, and spend tracking. This is where `allowed_scopes` and `max_spend` policy fields become meaningful.
- **Delegated ephemeral credentials**: For providers that support it:
  - AWS STS (temporary credentials)
  - GitHub Apps (installation tokens)
  - GCP (short-lived service account keys)
- Provider adapter interface to abstract issuance strategy per service

### Phase 4: Developer Surface

- Python SDK
- TypeScript SDK
- CLI for testing and local development
- Dashboard for policy management, checkout history, and audit logs

## Security Requirements

- TLS everywhere in production
- KMS-backed envelope encryption for stored keys. No plaintext secrets in logs, responses (except the checkout response itself), or error messages
- Per-org data isolation in queries
- Short-lived checkouts by default (1h default, configurable max per policy)
- Append-only audit trail
- Token hashing (argon2) — raw tokens never stored

## Key Design Decisions

1. **Vault checkout first, proxy later.** The convenience wedge gets the product into peoples' hands. Proxy mode is where governance becomes real — but it's operationally heavy and we should earn the right to build it by proving demand.

2. **Honest about enforcement boundaries.** Vault mode controls access to keys, not usage of keys. The API response, docs, and policy model all reflect this clearly. No false promises about scope or spend enforcement until the architecture supports it.

`max_active_checkouts` is intentionally defined as a limit on open checkout records, not a guarantee about true concurrent upstream usage of a copied raw key.

3. **Checkouts, not leases.** Named to reflect what actually happens: a time-bound record of who took which key and when. Not an upstream-enforced credential lifetime.

4. **Deny-by-default policies.** No policy = no access. Explicit allowlisting only.

5. **Pluggable auth from day one.** Service tokens for MVP, but the auth dependency is an interface, not hardcoded. OIDC slots in without touching route handlers.

6. **Postgres from the start.** The concurrency requirements (checkout issuance, revocation, audit) justify a real database from day one. SQLAlchemy async gives us a clean abstraction.

7. **Envelope encryption from the start.** The product stores customer API keys. That's a high-trust position. The crypto story must be credible from v1, not retrofitted.

## Success Metrics

- Time to first successful integration (target: <30 minutes)
- Number of active agents per org
- Credential checkouts per day
- Checkout quota denial rate and reasons (signal for policy tuning)
- Time from "I want to add a provider" to "agent has a key" (measure the convenience wedge)

## Open Questions

- Which 2 providers do we support first? (Likely OpenAI + Anthropic)
- Do we want a free tier, or is this always a paid product?
- How much identity proof do we require from self-hosted agents?
- Should the proxy mode be opt-in per service, or a global org setting?
