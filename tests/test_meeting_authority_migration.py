"""Real PostgreSQL transactional migration checks on an explicit disposable DB."""
import importlib
import os
from uuid import UUID, uuid4

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations


@pytest.fixture
def connection(request):
    url = os.environ.get("MEETINGS_MIGRATION_TEST_URL")
    if not url:
        pytest.skip("Set MEETINGS_MIGRATION_TEST_URL to a disposable pre-0017 database")
    engine = sa.create_engine(url)
    with engine.connect() as conn:
        transaction = conn.begin()
        assert conn.scalar(sa.text("SELECT version_num FROM alembic_version_townlight_meetings")) == getattr(request, "param", "townlight_meetings_0016")
        try:
            yield conn
        finally:
            transaction.rollback()
    engine.dispose()


def migrate(connection):
    migration = importlib.import_module("townlight_meetings.migrations.versions.townlight_meetings_0017_meeting_authority")
    with Operations.context(MigrationContext.configure(connection)):
        migration.upgrade()


def seed(connection, identity):
    connection.execute(sa.text("""INSERT INTO townlight_meetings.meeting_records
      (id,title,meeting_type,status,audit_entries,created_at,updated_at)
      VALUES (:id,'Synthetic authority test','regular','SCHEDULED',
              '[{"actor":"synthetic-clerk","action":"meeting.created"}]',now(),now())"""), {"id": identity})


def test_import_preserves_history_and_real_child_foreign_key(connection):
    identity = str(uuid4())
    seed(connection, identity)
    before = connection.execute(sa.text("SELECT * FROM townlight_meetings.meeting_records WHERE id=:id"), {"id": identity}).mappings().one()
    migrate(connection)
    row = connection.execute(sa.text("SELECT * FROM townlight_meetings.meetings WHERE id=CAST(:id AS uuid)"), {"id": identity}).mappings().one()
    for field in ("title", "meeting_type", "status", "audit_entries", "created_at", "updated_at", "scheduled_start", "meeting_body_id"):
        assert row[field] == before[field]
    assert connection.scalar(sa.text("SELECT count(*) FROM townlight_meetings.meeting_records WHERE id=:id"), {"id": identity}) == 1
    # No manually mirrored parent: the migrated lifecycle row satisfies real FK.
    connection.execute(sa.text("""INSERT INTO townlight_meetings.minutes
      (id,meeting_id,status,body,capture_seq) VALUES
      (:id,:meeting,'DRAFT','Synthetic cited draft',900001)"""),
      {"id": uuid4(), "meeting": UUID(identity)})


def test_conflicting_parent_aborts_without_overwriting(connection):
    identity = str(uuid4())
    seed(connection, identity)
    body = uuid4()
    connection.execute(sa.text("INSERT INTO townlight_meetings.meeting_bodies(id,name,body_type) VALUES (:id,'Synthetic','council')"), {"id": body})
    connection.execute(sa.text("""INSERT INTO townlight_meetings.meetings
      (id,title,meeting_body_id,scheduled_start,status)
      VALUES (:id,'Conflicting title',:body,now(),'SCHEDULED')"""), {"id": UUID(identity), "body": body})
    with pytest.raises(RuntimeError, match="Conflicting meeting identities"):
        migrate(connection)
    assert connection.scalar(sa.text("SELECT title FROM townlight_meetings.meetings WHERE id=CAST(:id AS uuid)"), {"id": identity}) == "Conflicting title"
    assert "audit_entries" not in {c["name"] for c in sa.inspect(connection).get_columns("meetings", schema="townlight_meetings")}


@pytest.mark.parametrize("connection", ["townlight_meetings_0017"], indirect=True)
def test_agenda_import_preserves_draft_and_existing_parent(connection):
    identity = str(uuid4())
    connection.execute(sa.text("""INSERT INTO townlight_meetings.agenda_item_lifecycle_records
      (id,title,department_name,status,audit_entries,created_at,updated_at)
      VALUES (:id,'Synthetic report','Works','DRAFTED','[]',now(),now())"""), {"id":identity})
    migration = importlib.import_module("townlight_meetings.migrations.versions.townlight_meetings_0018_agenda_authority")
    with Operations.context(MigrationContext.configure(connection)):
        migration.upgrade()
    row=connection.execute(sa.text("SELECT title,meeting_id,status FROM townlight_meetings.agenda_items WHERE id=CAST(:id AS uuid)"), {"id":identity}).one()
    assert tuple(row) == ("Synthetic report",None,"DRAFTED")
    assert connection.scalar(sa.text("SELECT count(*) FROM townlight_meetings.agenda_item_lifecycle_records WHERE id=:id"), {"id":identity}) == 1
