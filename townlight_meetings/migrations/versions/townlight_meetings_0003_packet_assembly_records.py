"""Create packet assembly records table."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from townlight_meetings.migrations.guards import idempotent_create_table


revision = "townlight_meetings_0003"
down_revision = "townlight_meetings_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    idempotent_create_table(
        "packet_assembly_records",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("meeting_id", sa.String(64), nullable=False),
        sa.Column("packet_snapshot_id", sa.String(64), nullable=False),
        sa.Column("packet_version", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("status", sa.String(80), nullable=False),
        sa.Column("actor", sa.String(255), nullable=False),
        sa.Column("agenda_item_ids", postgresql.JSONB(), nullable=False),
        sa.Column("source_references", postgresql.JSONB(), nullable=False),
        sa.Column("citations", postgresql.JSONB(), nullable=False),
        sa.Column("finalized_by", sa.String(255), nullable=True),
        sa.Column("finalized_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_audit_hash", sa.String(128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        schema="townlight_meetings",
    )


def downgrade() -> None:
    op.drop_table("packet_assembly_records", schema="townlight_meetings")
