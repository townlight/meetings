from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from civicclerk.agenda_lifecycle import AgendaItemRepository
from civicclerk.main import app


def test_native_create_actor_survives_reopening_both_repositories(tmp_path):
    from civicclerk.meeting_lifecycle import MeetingStore, verify_meeting_audit_entries
    from civicclerk.agenda_lifecycle import verify_agenda_item_audit_entries
    url = f"sqlite:///{tmp_path / 'native-intake.db'}"
    actor = "synthetic-native-actor"
    meetings = MeetingStore(db_url=url)
    agenda = AgendaItemRepository(db_url=url)
    meeting = meetings.create(title="Redstone council", meeting_type="regular", actor=actor)
    item = agenda.create(title="Trail report", department_name="Public Works", actor=actor)
    meetings.engine.dispose()
    agenda.engine.dispose()
    reopened_meetings = MeetingStore(db_url=url)
    reopened_agenda = AgendaItemRepository(db_url=url)
    try:
        saved_meeting = reopened_meetings.get(meeting.id)
        saved_item = reopened_agenda.get(item.id)
        assert saved_meeting.audit_entries[0]["actor"] == actor
        assert saved_item.audit_entries[0]["actor"] == actor
        assert verify_meeting_audit_entries(saved_meeting.audit_entries)[0]
        assert verify_agenda_item_audit_entries(saved_item.audit_entries)[0]
    finally:
        reopened_meetings.engine.dispose()
        reopened_agenda.engine.dispose()


def test_agenda_item_records_persist_status_and_audit_entries(tmp_path) -> None:
    db_url = f"sqlite:///{tmp_path / 'agenda-items.db'}"
    first = AgendaItemRepository(db_url=db_url)
    item = first.create(title="Adopt safe streets plan", department_name="Public Works")

    allowed = first.transition(item_id=item.id, to_status="SUBMITTED", actor="clerk@example.gov")
    rejected = first.transition(item_id=item.id, to_status="POSTED", actor="clerk@example.gov")

    second = AgendaItemRepository(db_url=db_url)
    persisted = second.get(item.id)

    assert allowed is not None
    assert allowed.allowed is True
    assert rejected is not None
    assert rejected.allowed is False
    assert persisted is not None
    assert persisted.status == "SUBMITTED"
    assert [entry["outcome"] for entry in persisted.audit_entries] == ["allowed", "rejected"]
    assert persisted.audit_entries[-1]["to_status"] == "POSTED"


@pytest.mark.asyncio
async def test_api_agenda_items_use_configured_database(monkeypatch, tmp_path) -> None:
    db_url = f"sqlite:///{tmp_path / 'api-agenda-items.db'}"
    monkeypatch.setenv("CIVICCLERK_AGENDA_ITEM_DB_URL", db_url)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        created = await client.post(
            "/agenda-items",
            json={
                "title": "Approve downtown study",
                "department_name": "Planning",
            },
        )
        transitioned = await client.post(
            f"/agenda-items/{created.json()['id']}/transitions",
            json={
                "to_status": "SUBMITTED",
                "actor": "clerk@example.gov",
            },
        )

    second = AgendaItemRepository(db_url=db_url)
    persisted = second.get(created.json()["id"])

    assert created.status_code == 201
    assert transitioned.status_code == 200
    assert transitioned.json()["status"] == "SUBMITTED"
    assert persisted is not None
    assert persisted.title == "Approve downtown study"
    assert persisted.status == "SUBMITTED"
    assert persisted.audit_entries[-1]["reason"] == "transition allowed"
def test_accepted_agenda_assignment_uses_one_parent_and_preserves_audit(tmp_path):
    from civicclerk.meeting_lifecycle import MeetingStore
    from civicclerk.agenda_lifecycle import AgendaItemRepository, verify_agenda_item_audit_entries
    url = f"sqlite:///{tmp_path / 'connected.db'}"
    meetings = MeetingStore(db_url=url)
    meeting = meetings.create(title="Synthetic council", meeting_type="regular", actor="clerk")
    agenda = AgendaItemRepository(db_url=url)
    item = agenda.create(title="Report", department_name="Works", actor="submitter")
    early = agenda.assign_meeting(item_id=item.id, meeting_id=meeting.id, actor="clerk")
    assert early.audit_entries[-1]["workflow_warning"]
    assert early.audit_entries[-1]["human_decision"]
    for status in ("SUBMITTED", "DEPT_APPROVED", "LEGAL_REVIEWED", "CLERK_ACCEPTED"):
        assert agenda.record_human_stage(item_id=item.id, to_status=status, actor="synthetic-reviewer").status == status
    assigned = agenda.assign_meeting(item_id=item.id, meeting_id=meeting.id, actor="clerk")
    assert assigned.meeting_id == meeting.id
    assert assigned.status == "ON_AGENDA"
    assert verify_agenda_item_audit_entries(assigned.audit_entries)[0]
    reopened = AgendaItemRepository(db_url=url)
    assert reopened.get(item.id).public_dict() == assigned.public_dict()
    other = meetings.create(title="Another council", meeting_type="regular", actor="clerk")
    moved = reopened.assign_meeting(item_id=item.id, meeting_id=other.id, actor="clerk")
    assert moved.audit_entries[:-1] == assigned.audit_entries
    assert moved.audit_entries[-1]["previous_meeting_id"] == meeting.id
    assert moved.meeting_id == other.id
    for store in (meetings, agenda, reopened):
        store.engine.dispose()
