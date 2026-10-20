"""Read-only Records source projection of explicitly public archive snapshots.

Never queries raw transcripts, packet attachments or restricted archive records.
The archive ID and document kind identify the historical snapshot, not 'latest'.
"""
import hashlib
from civicclerk.public_archive import PublicArchiveRepository


def public_documents(db_url: str, query: str = "", source_id: str | None = None) -> list[dict]:
    store = PublicArchiveRepository(db_url=db_url)
    try:
        results = []
        for record in store.search(query="", include_closed=False):
            for kind, content in (("agenda", record.posted_agenda),
                                  ("packet", record.posted_packet),
                                  ("minutes", record.approved_minutes)):
                identity = f"townlight:meetings:archive:{record.id}:{kind}"
                if not content or (source_id is not None and identity != source_id):
                    continue
                if query.casefold() not in (record.title + "\n" + content).casefold():
                    continue
                digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
                references = next((entry.get("source_references", {}) for entry in
                                   reversed(record.audit_entries)), {})
                results.append({"source_id": identity, "archive_id": record.id,
                    "meeting_id": record.meeting_id, "kind": kind,
                    "title": f"{record.title} — {kind}", "sha256": digest,
                    "version": record.id, "source_references": references,
                    "visibility": "public", "text": content,
                    "citation": f"{identity}; sha256={digest}"})
        return results
    finally:
        store.engine.dispose()
