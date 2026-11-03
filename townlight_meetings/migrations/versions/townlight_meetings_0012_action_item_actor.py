"""Add actor attribution to action_items for restart-safe capture records."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "townlight_meetings_0012"
down_revision = "townlight_meetings_0011"
branch_labels = None
depends_on = None

SCHEMA = "townlight_meetings"


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    columns = {
        column["name"]
        for column in inspector.get_columns("action_items", schema=SCHEMA)
    }
    if "actor" not in columns:
        op.add_column(
            "action_items",
            sa.Column("actor", sa.String(255), nullable=True),
            schema=SCHEMA,
        )


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    columns = {
        column["name"]
        for column in inspector.get_columns("action_items", schema=SCHEMA)
    }
    if "actor" in columns:
        op.drop_column("action_items", "actor", schema=SCHEMA)
