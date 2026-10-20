"""Retain packet contents/deliveries and notice proof history."""
from alembic import op
import sqlalchemy as sa

revision = "civicclerk_0020_delivery"
down_revision = "civicclerk_0019_minutes"
branch_labels = None
depends_on = None


def upgrade():
    for table, names in {
        "packet_assembly_records": ("snapshot_content", "delivery_history", "audit_entries"),
        "notice_checklist_records": ("audit_entries",),
    }.items():
        for name in names:
            op.add_column(table, sa.Column(name, sa.JSON(), nullable=False,
                server_default=sa.text("'[]'")), schema="civicclerk")


def downgrade():
    raise RuntimeError("Preserve packet and notice history; use forward recovery or a consistent backup.")
