"""Use one meeting parent for lifecycle, minutes, packets and archives.

Legacy input remains intact. Run while application writers are stopped. Unknown
historical schedule/body values stay unknown rather than being fabricated.
"""
from alembic import op
import sqlalchemy as sa

revision = "townlight_meetings_0017"
down_revision = "townlight_meetings_0016"
branch_labels = None
depends_on = None


def upgrade():
    connection = op.get_bind()
    connection.execute(sa.text("LOCK TABLE townlight_meetings.meeting_records, townlight_meetings.meetings IN ACCESS EXCLUSIVE MODE"))
    conflict = connection.scalar(sa.text("""
        SELECT count(*) FROM townlight_meetings.meeting_records old
        JOIN townlight_meetings.meetings current ON current.id = old.id::uuid
        WHERE current.title IS DISTINCT FROM old.title
           OR current.meeting_type IS DISTINCT FROM old.meeting_type
           OR current.status IS DISTINCT FROM old.status
           OR current.meeting_body_id IS DISTINCT FROM NULLIF(old.meeting_body_id, '')::uuid
           OR current.scheduled_start IS DISTINCT FROM old.scheduled_start
           OR current.location IS DISTINCT FROM old.location
    """))
    if conflict:
        raise RuntimeError("Conflicting meeting identities: reconcile before migration; no rows overwritten.")
    op.add_column("meetings", sa.Column("audit_entries", sa.JSON(), nullable=False, server_default=sa.text("'[]'")), schema="townlight_meetings")
    op.alter_column("meetings", "meeting_body_id", nullable=True, schema="townlight_meetings")
    op.alter_column("meetings", "scheduled_start", nullable=True, schema="townlight_meetings")
    connection.execute(sa.text("""
        INSERT INTO townlight_meetings.meetings
          (id, title, meeting_type, meeting_body_id, scheduled_start, location,
           status, audit_entries, created_at, updated_at)
        SELECT id::uuid, title, meeting_type, NULLIF(meeting_body_id, '')::uuid,
               scheduled_start, location, status, audit_entries, created_at, updated_at
        FROM townlight_meetings.meeting_records
        ON CONFLICT (id) DO UPDATE SET audit_entries = EXCLUDED.audit_entries
    """))


def downgrade():
    raise RuntimeError("Recover forward or restore a verified consistent backup; legacy rows do not contain newer work.")
