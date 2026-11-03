"""Add provenance model and public posting timestamp to minutes."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "townlight_meetings_0013"
down_revision = "townlight_meetings_0012"
branch_labels = None
depends_on = None

SCHEMA = "townlight_meetings"


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    columns = {
        column["name"]
        for column in inspector.get_columns("minutes", schema=SCHEMA)
    }
    if "model" not in columns:
        op.add_column(
            "minutes",
            sa.Column("model", sa.String(255), nullable=True),
            schema=SCHEMA,
        )
    if "posted_at" not in columns:
        op.add_column(
            "minutes",
            sa.Column("posted_at", sa.DateTime(timezone=True), nullable=True),
            schema=SCHEMA,
        )


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    columns = {
        column["name"]
        for column in inspector.get_columns("minutes", schema=SCHEMA)
    }
    if "posted_at" in columns:
        op.drop_column("minutes", "posted_at", schema=SCHEMA)
    if "model" in columns:
        op.drop_column("minutes", "model", schema=SCHEMA)
