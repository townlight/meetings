"""Retain packet contents/deliveries and notice proof history."""
from alembic import op
import sqlalchemy as sa

revision = "townlight_meetings_0020"
down_revision = "townlight_meetings_0019"
branch_labels = None
depends_on = None


def upgrade():
    for table, names in {
        "packet_assembly_records": ("snapshot_content", "delivery_history", "audit_entries"),
        "notice_checklist_records": ("audit_entries",),
    }.items():
        for name in names:
            op.add_column(table, sa.Column(name, sa.JSON(), nullable=False,
                server_default=sa.text("'[]'")), schema="townlight_meetings")


def downgrade():
    raise RuntimeError("Preserve packet and notice history; use forward recovery or a consistent backup.")
