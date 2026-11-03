"""Durable transcript captures and archive actor history."""
from alembic import op
import sqlalchemy as sa

revision = "townlight_meetings_0021"
down_revision = "townlight_meetings_0020"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("transcripts",sa.Column("transcript_text",sa.Text(),nullable=True),schema="townlight_meetings")
    op.add_column("transcripts",sa.Column("actor",sa.String(255),nullable=True),schema="townlight_meetings")
    op.add_column("transcripts",sa.Column("correction_of_id",sa.Uuid(),nullable=True),schema="townlight_meetings")
    for table in ("transcripts","public_meeting_records"):
        op.add_column(table,sa.Column("audit_entries",sa.JSON(),nullable=False,
            server_default=sa.text("'[]'")),schema="townlight_meetings")


def downgrade():
    raise RuntimeError("Do not discard transcript or archive history; recover forward.")
