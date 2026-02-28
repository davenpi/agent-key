"""admin usability constraints"""

from __future__ import annotations

from alembic import op

revision = "0002_admin_constraints"
down_revision = "0001_initial_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add admin-facing uniqueness constraints.

    Returns
    -------
    None
        Creates composite uniqueness constraints used by the admin API.
    """
    op.create_unique_constraint(
        "uq_admin_tokens_org_name",
        "admin_tokens",
        ["org_id", "name"],
    )
    op.create_unique_constraint(
        "uq_agent_tokens_org_name",
        "agent_tokens",
        ["org_id", "name"],
    )
    op.create_unique_constraint(
        "uq_stored_keys_org_service_label",
        "stored_keys",
        ["org_id", "service_id", "label"],
    )


def downgrade() -> None:
    """Remove admin-facing uniqueness constraints.

    Returns
    -------
    None
        Drops composite uniqueness constraints.
    """
    op.drop_constraint(
        "uq_stored_keys_org_service_label",
        "stored_keys",
        type_="unique",
    )
    op.drop_constraint(
        "uq_agent_tokens_org_name",
        "agent_tokens",
        type_="unique",
    )
    op.drop_constraint(
        "uq_admin_tokens_org_name",
        "admin_tokens",
        type_="unique",
    )
