"""Persist source evidence and canonical Meetings records in one transaction."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from urllib.parse import urlsplit, urlunsplit

import sqlalchemy as sa
from sqlalchemy import Engine
from sqlalchemy.dialects.postgresql import insert as postgres_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from townlight_meetings.agenda_lifecycle import AgendaItemRepository
from townlight_meetings.meeting_lifecycle import MeetingStore, meeting_records

SCHEMA = "townlight_meetings"
metadata = sa.MetaData()
imports = sa.Table(
    "external_meeting_imports",
    metadata,
    sa.Column("source_key", sa.String(64), primary_key=True),
    sa.Column("source", sa.JSON(), nullable=False),
    sa.Column("external_id", sa.Text(), nullable=False),
    sa.Column("payload_hash", sa.String(64), nullable=False),
    sa.Column("payload", sa.JSON(), nullable=False),
    sa.Column("meeting_id", sa.Uuid(as_uuid=False)),
    sa.Column("agenda_item_ids", sa.JSON(), nullable=False),
    sa.Column("actor", sa.String(255), nullable=False),
    sa.Column("imported_at", sa.DateTime(timezone=True), nullable=False),
    sa.UniqueConstraint("meeting_id", name="uq_external_meeting_imports_meeting_id"),
    schema=SCHEMA,
)


def _digest(data: object) -> str:
    return hashlib.sha256(
        json.dumps(data, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    ).hexdigest()


def commit_meeting_import(
    engine: Engine, *, actor: str, source: dict, meeting: dict
) -> dict:
    """Save a selected source record, leaving subsequent changes for review."""
    title = meeting["title"].strip()
    location = meeting.get("location")
    if not title or len(title) > 255 or (location and len(location) > 255):
        raise ValueError("Review the meeting title or location before importing it.")
    agenda = meeting.get("agenda_items", [])
    for item in agenda:
        if not item["title"].strip() or len(item["title"]) > 500 or len(item.get("department") or "") > 255:
            raise ValueError("Review the agenda item title or department before importing it.")
    raw_start = meeting.get("scheduled_start") or meeting.get("source_start")
    scheduled_start = datetime.fromisoformat(raw_start) if raw_start else None
    if scheduled_start is not None and scheduled_start.utcoffset() is None:
        scheduled_start = None
    url = urlsplit(source["url"])
    namespace = source.get("namespace") or urlunsplit(
        (url.scheme, url.netloc.lower(), url.path or "/", url.query, "")
    )
    source_key = _digest([source["connector"], namespace, meeting["external_id"]])
    payload_hash = _digest(meeting)
    if engine.dialect.name == "sqlite":
        engine = engine.execution_options(schema_translate_map={SCHEMA: None})
        insert = sqlite_insert
    else:
        insert = postgres_insert
    meetings = MeetingStore(engine=engine)
    items = AgendaItemRepository(engine=engine)

    with engine.begin() as connection:
        claimed = connection.scalar(insert(imports).values(
            source_key=source_key,
            source=source,
            external_id=meeting["external_id"],
            payload_hash=payload_hash,
            payload=meeting,
            agenda_item_ids=[],
            actor=actor,
            imported_at=datetime.now(UTC),
        ).on_conflict_do_nothing(index_elements=[imports.c.source_key]).returning(imports.c.source_key))
        if claimed is None:
            row = connection.execute(
                sa.select(imports).where(imports.c.source_key == source_key)
            ).mappings().one()
            exists = connection.scalar(
                sa.select(meeting_records.c.id).where(meeting_records.c.id == row["meeting_id"])
            )
            return {
                "status": (
                    "missing-destination" if not exists
                    else "unchanged" if row["payload_hash"] == payload_hash
                    else "changed-source"
                ),
                "meeting_id": row["meeting_id"],
                "agenda_item_ids": row["agenda_item_ids"],
                "source_key": source_key,
            }
        destination = meetings.create(
            title=title, meeting_type="regular", scheduled_start=scheduled_start,
            location=location, actor=actor, connection=connection,
        )
        agenda_item_ids = [
            items.create(
                title=item["title"].strip(), department_name=item.get("department") or "Unspecified",
                meeting_id=destination.id, actor=actor, connection=connection,
            ).id
            for item in agenda
        ]
        connection.execute(imports.update().where(imports.c.source_key == source_key).values(
            meeting_id=destination.id, agenda_item_ids=agenda_item_ids,
        ))
    return {
        "status": "created",
        "meeting_id": destination.id,
        "agenda_item_ids": agenda_item_ids,
        "source_key": source_key,
    }


def read_meeting_import(engine: Engine, meeting_id: str) -> dict | None:
    with engine.connect() as connection:
        row = connection.execute(
            sa.select(imports).where(imports.c.meeting_id == meeting_id)
        ).mappings().one_or_none()
    if row is None:
        return None
    return {
        "source_key": row["source_key"],
        "source": row["source"],
        "payload": row["payload"],
        "meeting_id": row["meeting_id"],
        "agenda_item_ids": row["agenda_item_ids"],
        "actor": row["actor"],
        "imported_at": row["imported_at"].isoformat(),
    }
