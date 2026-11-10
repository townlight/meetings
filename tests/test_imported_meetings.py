import pytest
import sqlalchemy as sa

from townlight_meetings.agenda_lifecycle import AgendaItemRepository
from townlight_meetings.imported_meetings import commit_meeting_import, metadata, read_meeting_import
from townlight_meetings.meeting_lifecycle import MeetingStore


SOURCE = {
    "connector": "legistar",
    "url": "https://town.example.gov/meetings",
    "namespace": "//town.example.gov",
    "sha256": "a" * 64,
}
MEETING = {
    "external_id": "42",
    "title": "Town council",
    "scheduled_start": "2026-10-20T18:00:00-06:00",
    "agenda_items": [{"external_id": "7", "title": "Parks budget", "department": "Finance"}],
}


@pytest.fixture
def engine(tmp_path):
    engine = sa.create_engine(f"sqlite+pysqlite:///{tmp_path / 'meetings.db'}").execution_options(
        schema_translate_map={"townlight_meetings": None}
    )
    metadata.create_all(engine)
    try:
        yield engine
    finally:
        engine.dispose()


def test_duplicate_and_changed_source_leave_existing_records_intact(engine):
    saved = commit_meeting_import(engine, actor="staff", source=SOURCE, meeting=MEETING)
    assert saved["status"] == "created"
    later_page = {**SOURCE, "url": "https://town.example.gov/meetings?page=2"}
    repeat = commit_meeting_import(engine, actor="staff", source=later_page, meeting=MEETING)
    assert repeat == {**saved, "status": "unchanged"}
    changed = commit_meeting_import(
        engine, actor="staff", source=SOURCE, meeting={**MEETING, "title": "Revised title"}
    )
    assert changed == {**saved, "status": "changed-source"}
    meetings = MeetingStore(engine=engine)
    assert [meeting.title for meeting in meetings.list()] == ["Town council"]
    item = AgendaItemRepository(engine=engine).get(saved["agenda_item_ids"][0])
    assert item.title == "Parks budget"
    assert item.meeting_id == saved["meeting_id"]
    assert item.status == "DRAFTED"
    receipt = read_meeting_import(engine, saved["meeting_id"])
    assert receipt["actor"] == "staff"
    assert receipt["source"] == SOURCE
    assert receipt["payload"] == MEETING


def test_failed_agenda_write_rolls_back_meeting_and_import_claim(engine, monkeypatch):
    with monkeypatch.context() as patch:
        def refuse(*args, **kwargs):
            raise sa.exc.SQLAlchemyError("test rollback")

        patch.setattr(AgendaItemRepository, "create", refuse)
        with pytest.raises(sa.exc.SQLAlchemyError, match="test rollback"):
            commit_meeting_import(engine, actor="staff", source=SOURCE, meeting=MEETING)
    assert MeetingStore(engine=engine).list() == []
    assert commit_meeting_import(engine, actor="staff", source=SOURCE, meeting=MEETING)["status"] == "created"
