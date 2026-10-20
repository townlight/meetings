"""Use one meeting parent for lifecycle, minutes, packets and archives.

Legacy input remains intact. Run while application writers are stopped. Unknown
historical schedule/body values stay unknown rather than being fabricated.
"""
from alembic import op
import sqlalchemy as sa

revision = "civicclerk_0017_authority"
down_revision = "civicclerk_0016_archive_indexes"
branch_labels = None
depends_on = None


def upgrade():
    connection = op.get_bind()
    connection.execute(sa.text("LOCK TABLE civicclerk.meeting_records, civicclerk.meetings IN ACCESS EXCLUSIVE MODE"))
    conflict = connection.scalar(sa.text("""
        SELECT count(*) FROM civicclerk.meeting_records old
        JOIN civicclerk.meetings current ON current.id = old.id::uuid
        WHERE current.title IS DISTINCT FROM old.title
           OR current.meeting_type IS DISTINCT FROM old.meeting_type
           OR current.status IS DISTINCT FROM old.status
           OR current.meeting_body_id IS DISTINCT FROM NULLIF(old.meeting_body_id, '')::uuid
           OR current.scheduled_start IS DISTINCT FROM old.scheduled_start
           OR current.location IS DISTINCT FROM old.location
    """))
    if conflict:
        raise RuntimeError("Conflicting meeting identities: reconcile before migration; no rows overwritten.")
    op.add_column("meetings", sa.Column("audit_entries", sa.JSON(), nullable=False, server_default=sa.text("'[]'")), schema="civicclerk")
    op.alter_column("meetings", "meeting_body_id", nullable=True, schema="civicclerk")
    op.alter_column("meetings", "scheduled_start", nullable=True, schema="civicclerk")
    connection.execute(sa.text("""
        INSERT INTO civicclerk.meetings
          (id, title, meeting_type, meeting_body_id, scheduled_start, location,
           status, audit_entries, created_at, updated_at)
        SELECT id::uuid, title, meeting_type, NULLIF(meeting_body_id, '')::uuid,
               scheduled_start, location, status, audit_entries, created_at, updated_at
        FROM civicclerk.meeting_records
        ON CONFLICT (id) DO UPDATE SET audit_entries = EXCLUDED.audit_entries
    """))


def downgrade():
    raise RuntimeError("Recover forward or restore a verified consistent backup; legacy rows do not contain newer work.")
