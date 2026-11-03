"""Unify intake lifecycle with canonical agenda references; preserve originals."""
from alembic import op
import sqlalchemy as sa

revision = "townlight_meetings_0018"
down_revision = "townlight_meetings_0017"
branch_labels = None
depends_on = None


def upgrade():
    connection = op.get_bind()
    connection.execute(sa.text("LOCK TABLE townlight_meetings.agenda_item_lifecycle_records, townlight_meetings.agenda_items IN ACCESS EXCLUSIVE MODE"))
    conflicts = connection.scalar(sa.text("""SELECT count(*)
      FROM townlight_meetings.agenda_item_lifecycle_records old
      JOIN townlight_meetings.agenda_items current ON current.id=old.id::uuid
      WHERE current.title IS DISTINCT FROM old.title OR current.status IS DISTINCT FROM old.status
         OR current.department_name IS DISTINCT FROM old.department_name"""))
    if conflicts:
        raise RuntimeError("Conflicting agenda identities: reconcile before migration; no rows overwritten.")
    op.add_column("agenda_items", sa.Column("audit_entries", sa.JSON(), nullable=False, server_default=sa.text("'[]'")), schema="townlight_meetings")
    op.alter_column("agenda_items", "meeting_id", nullable=True, schema="townlight_meetings")
    connection.execute(sa.text("""INSERT INTO townlight_meetings.agenda_items
      (id,title,status,department_name,audit_entries,created_at,updated_at)
      SELECT id::uuid,title,status,department_name,audit_entries,created_at,updated_at
      FROM townlight_meetings.agenda_item_lifecycle_records
      ON CONFLICT(id) DO UPDATE SET audit_entries=EXCLUDED.audit_entries"""))


def downgrade():
    raise RuntimeError("Recover forward or restore a consistent backup; old intake rows lack newer work.")
