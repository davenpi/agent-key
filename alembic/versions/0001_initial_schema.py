"""initial schema"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create the initial application schema.

    Returns
    -------
    None
        Creates all core tables and indexes.
    """
    op.create_table(
        "organizations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )
    op.create_table(
        "services",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("provider", sa.String(length=100), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("base_url", sa.String(length=512), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("provider"),
    )
    op.create_table(
        "admin_tokens",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("org_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("token_hash", sa.String(length=512), nullable=False),
        sa.Column("token_lookup", sa.String(length=64), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_admin_tokens_lookup",
        "admin_tokens",
        ["token_lookup"],
        unique=False,
    )
    op.create_table(
        "agent_tokens",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("org_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("token_hash", sa.String(length=512), nullable=False),
        sa.Column("token_lookup", sa.String(length=64), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_agent_tokens_lookup",
        "agent_tokens",
        ["token_lookup"],
        unique=False,
    )
    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("org_id", sa.Uuid(), nullable=False),
        sa.Column("agent_token_id", sa.Uuid(), nullable=True),
        sa.Column("action", sa.String(length=100), nullable=False),
        sa.Column("resource_type", sa.String(length=100), nullable=False),
        sa.Column("resource_id", sa.String(length=255), nullable=False),
        sa.Column("event_metadata", sa.JSON(), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["agent_token_id"], ["agent_tokens.id"]),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "policies",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("org_id", sa.Uuid(), nullable=False),
        sa.Column("agent_token_id", sa.Uuid(), nullable=True),
        sa.Column("service_id", sa.Uuid(), nullable=False),
        sa.Column("max_checkouts_per_window", sa.Integer(), nullable=False),
        sa.Column("checkout_window", sa.String(length=50), nullable=False),
        sa.Column("max_active_checkouts", sa.Integer(), nullable=False),
        sa.Column("max_ttl_seconds", sa.Integer(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["agent_token_id"], ["agent_tokens.id"]),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["service_id"], ["services.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "stored_keys",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("org_id", sa.Uuid(), nullable=False),
        sa.Column("service_id", sa.Uuid(), nullable=False),
        sa.Column("label", sa.String(length=255), nullable=False),
        sa.Column("encrypted_secret", sa.LargeBinary(), nullable=False),
        sa.Column("wrapped_data_key", sa.LargeBinary(), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["service_id"], ["services.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "checkouts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("agent_token_id", sa.Uuid(), nullable=False),
        sa.Column("stored_key_id", sa.Uuid(), nullable=False),
        sa.Column("policy_id", sa.Uuid(), nullable=False),
        sa.Column("checked_out_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("returned_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["agent_token_id"], ["agent_tokens.id"]),
        sa.ForeignKeyConstraint(["policy_id"], ["policies.id"]),
        sa.ForeignKeyConstraint(["stored_key_id"], ["stored_keys.id"]),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    """Drop the initial application schema.

    Returns
    -------
    None
        Drops all core tables and indexes.
    """
    op.drop_table("checkouts")
    op.drop_table("stored_keys")
    op.drop_table("policies")
    op.drop_table("audit_logs")
    op.drop_index("ix_agent_tokens_lookup", table_name="agent_tokens")
    op.drop_table("agent_tokens")
    op.drop_index("ix_admin_tokens_lookup", table_name="admin_tokens")
    op.drop_table("admin_tokens")
    op.drop_table("services")
    op.drop_table("organizations")
