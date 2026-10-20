"""Minutes drafting helpers with citation and provenance validation."""

from __future__ import annotations

import threading
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID, uuid4

import sqlalchemy as sa
from sqlalchemy import Engine, create_engine

from civiccore.audit import AuditActor, AuditHashChain, AuditSubject, record_event
from civiccore.ingest import (
    CitedSentence as MinutesSentence,
    SourceMaterial,
    validate_cited_sentences,
)

from civicclerk.prompt_library import (
    expected_prompt_version_hint,
    is_known_prompt_version,
)

@dataclass(frozen=True)
class MinutesProvenance:
    model: str
    prompt_version: str
    data_sources: tuple[str, ...]
    human_approver: str

    def public_dict(self) -> dict[str, str | list[str]]:
        return {
            "model": self.model,
            "prompt_version": self.prompt_version,
            "data_sources": list(self.data_sources),
            "human_approver": self.human_approver,
        }


@dataclass(frozen=True)
class MinutesDraft:
    id: str
    meeting_id: str
    status: str
    sentences: tuple[MinutesSentence, ...]
    source_materials: tuple[SourceMaterial, ...]
    provenance: MinutesProvenance
    adopted: bool = False
    posted: bool = False
    signed_by: str | None = None
    decision_history: tuple[dict, ...] = ()

    def public_dict(self) -> dict:
        return {
            "id": self.id,
            "meeting_id": self.meeting_id,
            "status": self.status,
            "sentences": [sentence.public_dict() for sentence in self.sentences],
            "source_materials": [source.public_dict() for source in self.source_materials],
            "provenance": self.provenance.public_dict(),
            "adopted": self.adopted,
            "posted": self.posted,
            "signed_by": self.signed_by,
            "decision_history": list(self.decision_history),
            "publication_label": "Adopted minutes" if self.adopted else "Draft minutes — not adopted",
        }


@dataclass(frozen=True)
class MinutesValidationError:
    message: str
    fix: str


metadata = sa.MetaData()

minutes_table = sa.Table(
    "minutes",
    metadata,
    sa.Column("id", sa.Uuid(as_uuid=False), primary_key=True),
    sa.Column("meeting_id", sa.Uuid(as_uuid=False), nullable=False),
    sa.Column("status", sa.String(80), nullable=False),
    sa.Column("body", sa.Text(), nullable=False),
    sa.Column("source_materials", sa.JSON(), nullable=True),
    sa.Column("sentence_citations", sa.JSON(), nullable=True),
    sa.Column("prompt_version", sa.String(120), nullable=True),
    sa.Column("human_approver", sa.String(255), nullable=True),
    sa.Column("model", sa.String(255), nullable=True),
    sa.Column("adopted_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("posted_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("signed_by", sa.String(255), nullable=True),
    sa.Column("decision_history", sa.JSON(), nullable=False, server_default=sa.text("'[]'")),
    sa.Column("document_ref", sa.Text(), nullable=True),
    sa.Column("capture_seq", sa.BigInteger(), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    schema="civicclerk",
)


class MinutesDraftStore:
    """In-memory minutes draft store until DB-backed persistence lands.

    No adoption/posting writers exist yet by design; see MinutesDraftRepository.
    """

    def __init__(self) -> None:
        self._drafts: dict[str, MinutesDraft] = {}
        self._drafts_by_meeting: dict[str, list[str]] = {}

    def create_draft(
        self,
        *,
        meeting_id: str,
        model: str,
        prompt_version: str,
        human_approver: str,
        source_materials: list[SourceMaterial],
        sentences: list[MinutesSentence],
    ) -> MinutesDraft | MinutesValidationError:
        validation_error = _validate_create_inputs(prompt_version, source_materials, sentences)
        if validation_error is not None:
            return validation_error

        source_ids = tuple(source.source_id for source in source_materials)
        draft = MinutesDraft(
            id=str(uuid4()),
            meeting_id=meeting_id,
            status="DRAFT",
            sentences=tuple(sentences),
            source_materials=tuple(source_materials),
            provenance=MinutesProvenance(
                model=model,
                prompt_version=prompt_version,
                data_sources=source_ids,
                human_approver=human_approver,
            ),
        )
        self._drafts[draft.id] = draft
        self._drafts_by_meeting.setdefault(meeting_id, []).append(draft.id)
        return draft

    def get_draft(self, draft_id: str) -> MinutesDraft | None:
        return self._drafts.get(draft_id)

    def list_drafts(self, meeting_id: str) -> list[MinutesDraft]:
        return [
            self._drafts[draft_id]
            for draft_id in self._drafts_by_meeting.get(meeting_id, [])
        ]

    def list_recent(self, *, limit: int = 5) -> list[MinutesDraft]:
        """Return recent citation-gated drafts for the staff dashboard."""

        return list(reversed(list(self._drafts.values())))[:limit]


class MinutesDraftRepository:
    """SQLAlchemy-backed minutes draft store on the canonical minutes table.

    Sentences persist to the sentence_citations JSON column, source materials
    to the source_materials JSON column, and provenance decomposes into the
    model / prompt_version / human_approver columns. data_sources is derived
    from source_materials on read; adopted/posted derive from adopted_at /
    posted_at being non-NULL. The NOT NULL body column stores the joined
    sentence text so the canonical schema contract stays satisfied.

    Human posting, adoption and signing decisions are recorded separately;
    suggested sequencing warns but never invents or blocks a human decision.
    """

    def __init__(self, *, db_url: str | None = None, engine: Engine | None = None) -> None:
        base_engine = engine or create_engine(db_url or "sqlite+pysqlite:///:memory:", future=True)
        if base_engine.dialect.name == "sqlite":
            self.engine = base_engine.execution_options(schema_translate_map={"civicclerk": None})
        else:
            self.engine = base_engine
            with self.engine.begin() as connection:
                connection.execute(sa.text("CREATE SCHEMA IF NOT EXISTS civicclerk"))
        metadata.create_all(self.engine)
        self.audit_chain = AuditHashChain()
        # Serializes seal+insert+append so concurrent draft creations cannot
        # fork the hash chain or leave sealed events for writes that never
        # landed.
        self._chain_lock = threading.Lock()

    def create_draft(
        self,
        *,
        meeting_id: str,
        model: str,
        prompt_version: str,
        human_approver: str,
        source_materials: list[SourceMaterial],
        sentences: list[MinutesSentence],
        human_authored: bool = False,
    ) -> MinutesDraft | MinutesValidationError:
        validation_error = _validate_create_inputs(prompt_version, source_materials, sentences)
        if validation_error is not None and not human_authored:
            return validation_error

        now = datetime.now(UTC)
        draft_id = str(uuid4())
        from civicclerk.meeting_lifecycle import _build_persisted_audit_entry, ZERO_HASH
        creation_history = [_build_persisted_audit_entry(
            previous_hash=ZERO_HASH, actor=human_approver, action="minutes.human_draft",
            details={"actor":human_approver,"minutes_id":draft_id,"human_decision":True,
                     "warnings":[validation_error.message] if validation_error else [],
                     "note":"Staff-authored draft; creation is not adoption, posting or approval."}
        )] if human_authored else []
        with self._chain_lock:
            event = record_event(
                self.audit_chain.events,
                actor=AuditActor(actor_id=human_approver, actor_type="clerk"),
                action="minutes.draft_created",
                subject=AuditSubject(subject_id=draft_id, subject_type="minutes_draft"),
                source_module="civicclerk",
                metadata={
                    "meeting_id": meeting_id,
                    "sentence_count": len(sentences),
                },
            )
            values = {
                "id": draft_id,
                "meeting_id": meeting_id,
                "status": "DRAFT",
                "body": "\n".join(sentence.text for sentence in sentences),
                "source_materials": [source.public_dict() for source in source_materials],
                "sentence_citations": [sentence.public_dict() for sentence in sentences],
                "prompt_version": prompt_version,
                "human_approver": human_approver,
                "model": model,
                "adopted_at": None,
                "posted_at": None,
                "signed_by": None,
                "decision_history": creation_history,
                "document_ref": None,
                "created_at": now,
                "updated_at": now,
            }
            with self.engine.begin() as connection:
                values["capture_seq"] = _minutes_next_capture_seq(connection)
                connection.execute(minutes_table.insert().values(**values))
            # Append only after the transaction commits so a failed insert
            # never leaves a phantom sealed event on the chain.
            self.audit_chain.events.append(event)
        return self.get_draft(draft_id) or _minutes_row_to_draft(values)

    def get_draft(self, draft_id: str) -> MinutesDraft | None:
        parsed = _minutes_uuid_text_or_none(draft_id)
        if parsed is None:
            return None
        with self.engine.begin() as connection:
            row = connection.execute(
                sa.select(minutes_table).where(minutes_table.c.id == parsed)
            ).mappings().first()
        return _minutes_row_to_draft(row) if row is not None else None

    def record_decision(self, *, draft_id: str, action: str, actor: str,
                        note: str = "") -> MinutesDraft | None:
        """Record the selected human act only; retain all earlier decisions.

        Signing does not silently adopt or post. Posting does not adopt. An
        unusual order generates an audit warning, never an approval barrier.
        """
        if action not in {"post", "adopt", "sign"}:
            raise ValueError("Unknown minutes decision.")
        from civicclerk.meeting_lifecycle import _build_persisted_audit_entry, ZERO_HASH
        with self.engine.begin() as connection:
            row = connection.execute(sa.select(minutes_table).where(
                minutes_table.c.id == draft_id).with_for_update()).mappings().first()
            if row is None:
                return None
            history = list(row["decision_history"] or [])
            warnings = []
            if action == "sign" and row["adopted_at"] is None:
                warnings.append("Minutes are not adopted; this signature does not adopt them.")
            if action == "adopt" and row["posted_at"] is None:
                warnings.append("Minutes have not been posted; adoption does not post them.")
            if action == "post" and row["adopted_at"] is None:
                warnings.append("Published view must say Draft minutes — not adopted.")
            now = datetime.now(UTC)
            entry = _build_persisted_audit_entry(previous_hash=history[-1]["entry_hash"] if history else ZERO_HASH,
                actor=actor, action=f"minutes.human_{action}", details={"actor":actor,
                "minutes_id":draft_id,"human_decision":True,"note":note,
                "prior_status":row["status"],"warnings":warnings})
            values = {"decision_history":[*history,entry],"updated_at":now}
            if action == "post":
                values.update(posted_at=row["posted_at"] or now)
                if row["adopted_at"] is None and not row["signed_by"]:
                    values["status"] = "POSTED_DRAFT"
            elif action == "adopt":
                values.update(adopted_at=row["adopted_at"] or now)
                if not row["signed_by"]:
                    values["status"] = "ADOPTED"
            else:
                values.update(signed_by=actor,status="SIGNED")
            connection.execute(minutes_table.update().where(minutes_table.c.id == draft_id).values(**values))
        return self.get_draft(draft_id)

    def list_drafts(self, meeting_id: str) -> list[MinutesDraft]:
        parsed = _minutes_uuid_text_or_none(meeting_id)
        if parsed is None:
            return []
        statement = (
            sa.select(minutes_table)
            .where(minutes_table.c.meeting_id == parsed)
            .order_by(minutes_table.c.capture_seq.asc())
        )
        with self.engine.begin() as connection:
            rows = connection.execute(statement).mappings().all()
        return [_minutes_row_to_draft(row) for row in rows]

    def list_recent(self, *, limit: int = 5) -> list[MinutesDraft]:
        """Return recent citation-gated drafts for the staff dashboard."""

        statement = (
            sa.select(minutes_table)
            .order_by(minutes_table.c.capture_seq.desc())
            .limit(limit)
        )
        with self.engine.begin() as connection:
            rows = connection.execute(statement).mappings().all()
        return [_minutes_row_to_draft(row) for row in rows]


def validate_minutes_draft(
    *,
    source_materials: list[SourceMaterial],
    sentences: list[MinutesSentence],
) -> MinutesValidationError | None:
    error = validate_cited_sentences(
        source_materials=source_materials,
        sentences=sentences,
    )
    if error is None:
        return None
    if error.message == "Every material sentence must include at least one citation.":
        return MinutesValidationError(
            message="Every material minutes sentence must include at least one citation.",
            fix="Add source citations to each sentence before accepting AI-drafted minutes.",
        )
    if error.message == "Generated sentence cites an unknown source.":
        return MinutesValidationError(
            message="Minutes sentence cites an unknown source.",
            fix=error.fix,
        )
    return MinutesValidationError(message=error.message, fix=error.fix)


def _validate_create_inputs(
    prompt_version: str,
    source_materials: list[SourceMaterial],
    sentences: list[MinutesSentence],
) -> MinutesValidationError | None:
    """Shared create_draft input gates: prompt-library version, then citations."""

    if not is_known_prompt_version(prompt_version):
        expected = expected_prompt_version_hint()
        return MinutesValidationError(
            message="Minutes drafts must use a prompt version from the CivicMeetings YAML prompt library.",
            fix=f"Use prompt_version '{expected}' or another version returned by the prompt library.",
        )
    return validate_minutes_draft(
        source_materials=source_materials,
        sentences=sentences,
    )


def _minutes_next_capture_seq(connection: sa.Connection) -> int:
    """Allocate the next monotonic insertion-order sequence for minutes rows.

    Runs inside the insert transaction; callers already hold _chain_lock, so
    MAX+1 cannot race within the single writer process the in-memory audit
    chain requires. Ordering by capture_seq keeps insertion order even when
    rows share a created_at timestamp (the uuid4 id is random and must never
    decide order).
    """

    current = connection.execute(
        sa.select(sa.func.coalesce(sa.func.max(minutes_table.c.capture_seq), 0))
    ).scalar_one()
    return int(current) + 1


def _minutes_uuid_text_or_none(value: str | None) -> str | None:
    if value is None:
        return None
    try:
        return str(UUID(str(value)))
    except (AttributeError, TypeError, ValueError):
        return None


def _minutes_row_to_draft(row) -> MinutesDraft:
    data = dict(row)
    source_materials = tuple(
        SourceMaterial(
            source_id=source["source_id"],
            label=source["label"],
            text=source["text"],
        )
        for source in (data.get("source_materials") or [])
    )
    sentences = tuple(
        MinutesSentence(
            text=sentence["text"],
            citations=tuple(sentence["citations"]),
        )
        for sentence in (data.get("sentence_citations") or [])
    )
    return MinutesDraft(
        id=str(data["id"]),
        meeting_id=str(data["meeting_id"]),
        status=data["status"],
        sentences=sentences,
        source_materials=source_materials,
        provenance=MinutesProvenance(
            model=data.get("model") or "",
            prompt_version=data.get("prompt_version") or "",
            data_sources=tuple(source.source_id for source in source_materials),
            human_approver=data.get("human_approver") or "",
        ),
        adopted=data.get("adopted_at") is not None,
        posted=data.get("posted_at") is not None,
        signed_by=data.get("signed_by"),
        decision_history=tuple(data.get("decision_history") or []),
    )


__all__ = [
    "MinutesDraft",
    "MinutesDraftRepository",
    "MinutesDraftStore",
    "MinutesProvenance",
    "MinutesSentence",
    "MinutesValidationError",
    "SourceMaterial",
    "validate_minutes_draft",
]
