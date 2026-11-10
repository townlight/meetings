"""Retain external source provenance and stable meeting import identities."""

from alembic import op
import sqlalchemy as sa

revision = "townlight_meetings_0022"
down_revision = "townlight_meetings_0021"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "external_meeting_imports",
        sa.Column("source_key", sa.String(64), primary_key=True),
        sa.Column("source", sa.JSON(), nullable=False),
        sa.Column("external_id", sa.Text(), nullable=False),
        sa.Column("payload_hash", sa.String(64), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("meeting_id", sa.Uuid(), nullable=True),
        sa.Column("agenda_item_ids", sa.JSON(), nullable=False),
        sa.Column("actor", sa.String(255), nullable=False),
        sa.Column("imported_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("meeting_id", name="uq_external_meeting_imports_meeting_id"),
        schema="townlight_meetings",
    )
    op.create_table(
        "external_meeting_links",
        sa.Column("destination", sa.String(32), primary_key=True),
        sa.Column("target_id", sa.Uuid(), primary_key=True),
        sa.Column(
            "meeting_id", sa.Uuid(),
            sa.ForeignKey("townlight_meetings.external_meeting_imports.meeting_id"),
            primary_key=True,
        ),
        sa.Column("actor", sa.String(255), nullable=False),
        sa.Column("linked_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        schema="townlight_meetings",
    )


def downgrade():
    raise RuntimeError("Retain import history and recover forward or restore a consistent backup.")
