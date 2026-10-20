"""Durable staff transcript captures; corrections append rather than overwrite."""
from datetime import UTC, datetime
from uuid import uuid4
import sqlalchemy as sa
from civicclerk.meeting_lifecycle import _build_persisted_audit_entry, ZERO_HASH

metadata = sa.MetaData()
transcripts = sa.Table("transcripts",metadata,
    sa.Column("id",sa.Uuid(as_uuid=False),primary_key=True),
    sa.Column("meeting_id",sa.Uuid(as_uuid=False),nullable=False),
    sa.Column("source_uri",sa.Text(),nullable=False),
    sa.Column("status",sa.String(80),nullable=False),
    sa.Column("document_ref",sa.Text()),
    sa.Column("sensitivity_label",sa.String(80),nullable=False),
    sa.Column("staff_acl_roles",sa.JSON()),
    sa.Column("transcript_text",sa.Text()),
    sa.Column("actor",sa.String(255)),
    sa.Column("correction_of_id",sa.Uuid(as_uuid=False)),
    sa.Column("audit_entries",sa.JSON(),nullable=False,server_default=sa.text("'[]'")),
    sa.Column("created_at",sa.DateTime(timezone=True),nullable=False),
    sa.Column("updated_at",sa.DateTime(timezone=True),nullable=False),
    schema="civicclerk")


def public_row(row):
    return {key:(value.replace(tzinfo=UTC).isoformat() if value.tzinfo is None else value.astimezone(UTC).isoformat())
            if isinstance(value,datetime) else value for key,value in dict(row).items()}


class TranscriptRepository:
    def __init__(self,*,db_url):
        self.engine=sa.create_engine(db_url)
        if self.engine.dialect.name=="sqlite":
            self.engine=self.engine.execution_options(schema_translate_map={"civicclerk":None})
        metadata.create_all(self.engine)

    def capture(self,*,meeting_id,source_label,transcript_text,actor,closed_session=False,correction_of_id=None):
        record_id=str(uuid4())
        now=datetime.now(UTC)
        with self.engine.begin() as connection:
            if correction_of_id:
                original=connection.execute(sa.select(transcripts).where(
                    transcripts.c.id==correction_of_id,transcripts.c.meeting_id==meeting_id)).mappings().first()
                if original is None:
                    raise ValueError("Original transcript not found in this meeting.")
            entry=_build_persisted_audit_entry(previous_hash=ZERO_HASH,actor=actor,
                action="transcript.captured",details={"actor":actor,"transcript_id":record_id,
                "meeting_id":meeting_id,"correction_of_id":correction_of_id})
            values=dict(id=record_id,meeting_id=meeting_id,source_uri=source_label,
                status="CAPTURED",transcript_text=transcript_text,actor=actor,
                correction_of_id=correction_of_id,sensitivity_label="closed_session" if closed_session else "staff_only",
                staff_acl_roles=["clerk","admin"],audit_entries=[entry],created_at=now,updated_at=now)
            connection.execute(transcripts.insert().values(**values))
        return public_row(values)

    def list_for_meeting(self,meeting_id):
        with self.engine.connect() as connection:
            rows=connection.execute(sa.select(transcripts).where(transcripts.c.meeting_id==meeting_id)
                .order_by(transcripts.c.created_at,transcripts.c.id)).mappings().all()
        return [public_row(row) for row in rows]
