"""Packet snapshot, export bundle, and notice compliance helpers for Townlight Meetings."""

from __future__ import annotations

import json
import hashlib
import shutil
import sqlalchemy as sa
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from civicclerk import __version__ as CIVICCLERK_VERSION
from civiccore import __version__ as CIVICCORE_VERSION
from civiccore.audit import AuditActor, AuditHashChain, AuditSubject
from civiccore.exports import BundleFile, ExportBundle, build_sha256sums, validate_bundle, write_manifest
from civiccore.notifications import evaluate_notice_compliance as evaluate_shared_notice_compliance
from civiccore.provenance import ProvenanceBundle, SourceKind, SourceReference


PUBLIC_BLOCKED_SENSITIVITY = {"closed_session", "staff_only", "restricted"}

packet_metadata = sa.MetaData()
packet_versions = sa.Table("packet_versions", packet_metadata,
    sa.Column("id", sa.Uuid(as_uuid=False), primary_key=True),
    sa.Column("meeting_id", sa.Uuid(as_uuid=False), nullable=False),
    sa.Column("version", sa.Integer(), nullable=False),
    sa.Column("snapshot_uri", sa.Text(), nullable=False),
    sa.Column("agenda_item_ids", sa.JSON()),
    sa.Column("snapshot_hash", sa.String(128)),
    sa.Column("actor", sa.String(255)),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    sa.UniqueConstraint("meeting_id","version",name="uq_packet_versions_meeting_version"),
    schema="civicclerk")


class PacketExportError(ValueError):
    """Raised when a packet export would violate public-record guardrails."""

    def __init__(self, *, code: str, message: str, fix: str, http_status: int = 422) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.fix = fix
        self.http_status = http_status

    def public_dict(self) -> dict[str, str]:
        return {
            "code": self.code,
            "message": self.message,
            "fix": self.fix,
        }


@dataclass(frozen=True)
class PacketSource:
    """Source material included in an exported packet bundle."""

    source_id: str
    title: str
    kind: str = "document"
    source_system: str | None = None
    source_path: str | None = None
    checksum: str | None = None
    sensitivity_label: str | None = None
    citation_label: str | None = None

    def to_reference(self) -> SourceReference:
        try:
            source_kind = SourceKind(self.kind)
        except ValueError as exc:
            raise PacketExportError(
                code="unsupported_source_kind",
                message=f"Packet source kind {self.kind!r} is not supported.",
                fix="Use a Townlight Core source kind such as document, record, meeting_packet, code_section, zoning_parcel, local_file, or url.",
            ) from exc
        return SourceReference(
            source_id=self.source_id,
            kind=source_kind,
            title=self.title,
            source_system=self.source_system,
            source_path=self.source_path,
            checksum=self.checksum,
            sensitivity_label=self.sensitivity_label,
            citation_locator={"label": self.citation_label} if self.citation_label else None,
        )


@dataclass(frozen=True)
class PacketSnapshot:
    id: str
    meeting_id: str
    version: int
    agenda_item_ids: tuple[str, ...]
    actor: str
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def public_dict(self) -> dict:
        return {
            "id": self.id,
            "meeting_id": self.meeting_id,
            "version": self.version,
            "agenda_item_ids": list(self.agenda_item_ids),
            "actor": self.actor,
            "created_at": self.created_at.astimezone(UTC).isoformat(),
        }


@dataclass(frozen=True)
class PacketExportResult:
    """Result of creating a records-ready packet export bundle."""

    meeting_id: str
    bundle_path: str
    manifest_path: str
    checksums_path: str
    civiccore_version: str
    packet_version: int
    audit_hash: str
    generated_files: tuple[str, ...]

    def public_dict(self) -> dict:
        return {
            "meeting_id": self.meeting_id,
            "bundle_path": self.bundle_path,
            "manifest_path": self.manifest_path,
            "checksums_path": self.checksums_path,
            "civiccore_version": self.civiccore_version,
            "packet_version": self.packet_version,
            "audit_hash": self.audit_hash,
            "generated_files": list(self.generated_files),
        }


class PacketStore:
    """Packet version and export-bundle store.

    A configured database persists snapshot identity/version metadata. Export bundles are
    written to disk with Townlight Core v0.12.0 manifests, checksums, provenance, and
    hash-chained audit events so they can be validated without the server.
    """

    def __init__(self, *, db_url: str | None = None) -> None:
        self._snapshots: dict[str, list[PacketSnapshot]] = {}
        self.audit_chain = AuditHashChain()
        self.engine = None
        if db_url:
            self.engine = sa.create_engine(db_url)
            if self.engine.dialect.name == "sqlite":
                self.engine = self.engine.execution_options(schema_translate_map={"civicclerk":None})
            packet_metadata.create_all(self.engine)

    def create_snapshot(
        self,
        *,
        meeting_id: str,
        agenda_item_ids: list[str],
        actor: str,
    ) -> PacketSnapshot:
        if self.engine is not None:
            from civicclerk.meeting_lifecycle import meeting_records
            with self.engine.begin() as connection:
                parent = connection.execute(sa.select(meeting_records.c.id).where(
                    meeting_records.c.id == meeting_id).with_for_update()).first()
                if parent is None:
                    raise ValueError("Meeting not found.")
                version = (connection.scalar(sa.select(sa.func.max(packet_versions.c.version)).where(
                    packet_versions.c.meeting_id == meeting_id)) or 0) + 1
                snapshot = PacketSnapshot(id=str(uuid4()),meeting_id=meeting_id,version=version,
                    agenda_item_ids=tuple(agenda_item_ids),actor=actor)
                digest = hashlib.sha256(json.dumps(snapshot.public_dict(),sort_keys=True,separators=(",",":")).encode()).hexdigest()
                connection.execute(packet_versions.insert().values(id=snapshot.id,meeting_id=meeting_id,
                    version=version,snapshot_uri=f"urn:townlight:packet-snapshot:{snapshot.id}",
                    agenda_item_ids=agenda_item_ids,snapshot_hash=digest,actor=actor,
                    created_at=snapshot.created_at,updated_at=snapshot.created_at))
            return snapshot
        existing = self._snapshots.setdefault(meeting_id, [])
        snapshot = PacketSnapshot(
            id=str(uuid4()),
            meeting_id=meeting_id,
            version=len(existing) + 1,
            agenda_item_ids=tuple(agenda_item_ids),
            actor=actor,
        )
        existing.append(snapshot)
        self.audit_chain.record_event(
            actor=AuditActor(actor_id=actor, actor_type="staff"),
            action="packet_snapshot.created",
            subject=AuditSubject(subject_id=snapshot.id, subject_type="packet_snapshot"),
            source_module="civicclerk",
            metadata={
                "meeting_id": meeting_id,
                "version": snapshot.version,
                "agenda_item_ids": list(snapshot.agenda_item_ids),
            },
        )
        return snapshot

    def list_snapshots(self, meeting_id: str) -> list[PacketSnapshot]:
        if self.engine is not None:
            with self.engine.connect() as connection:
                rows = connection.execute(sa.select(packet_versions).where(
                    packet_versions.c.meeting_id == meeting_id).order_by(packet_versions.c.version)).mappings().all()
            return [PacketSnapshot(id=str(r["id"]),meeting_id=str(r["meeting_id"]),version=r["version"],
                agenda_item_ids=tuple(r["agenda_item_ids"] or []),actor=r["actor"],
                created_at=r["created_at"].replace(tzinfo=UTC) if r["created_at"].tzinfo is None else r["created_at"]) for r in rows]
        return list(self._snapshots.get(meeting_id, []))

    def create_export_bundle(
        self,
        *,
        meeting_id: str,
        meeting_title: str,
        bundle_path: str | Path,
        actor: str,
        sources: list[PacketSource],
        notices: list[dict] | None = None,
        public_bundle: bool = True,
        snapshot_id: str | None = None,
        agenda_content: list[dict] | None = None,
        source_files: dict[str, Path] | None = None,
    ) -> PacketExportResult:
        snapshots = self.list_snapshots(meeting_id)
        if not snapshots:
            raise PacketExportError(
                code="packet_snapshot_required",
                message="Packet export requires at least one packet snapshot.",
                fix="Create a packet snapshot before exporting the records-ready bundle.",
            )
        if not sources and agenda_content is None:
            raise PacketExportError(
                code="source_provenance_required",
                message="Packet export requires at least one source reference.",
                fix="Attach source/provenance metadata before exporting the bundle.",
            )

        source_refs = [source.to_reference() for source in sources]
        if public_bundle:
            blocked = [
                source
                for source in source_refs
                if (source.sensitivity_label or "").strip().lower() in PUBLIC_BLOCKED_SENSITIVITY
            ]
            if blocked:
                raise PacketExportError(
                    code="closed_session_source_not_public",
                    message="Public packet export cannot include closed-session or restricted source files.",
                    fix="Remove restricted sources or create a staff-only export bundle instead.",
                )

        root = Path(bundle_path)
        root.mkdir(parents=True, exist_ok=True)
        snapshot = next((item for item in snapshots if item.id == snapshot_id), None) if snapshot_id else snapshots[-1]
        if snapshot is None:
            raise ValueError("Packet version not found.")
        generated_at = datetime.now(UTC)
        provenance = ProvenanceBundle(
            bundle_id=f"civicclerk-{meeting_id}-packet-v{snapshot.version}",
            generated_at=generated_at,
            sources=source_refs,
        )

        packet_data = {
            "meeting_id": meeting_id,
            "meeting_title": meeting_title,
            "packet_version": snapshot.version,
            "agenda_item_ids": list(snapshot.agenda_item_ids),
            "generated_at": generated_at.isoformat(),
            "public_bundle": public_bundle,
            "sources": [source.model_dump(mode="json") for source in source_refs],
        }
        notice_data = {
            "meeting_id": meeting_id,
            "notices": notices or [],
            "generated_at": generated_at.isoformat(),
        }

        _write_json(root / "packet.json", packet_data)
        _write_json(root / "provenance.json", provenance.to_manifest())
        _write_json(root / "notices.json", notice_data)

        files = [
            BundleFile.from_path(root, "packet.json"),
            BundleFile.from_path(root, "provenance.json"),
            BundleFile.from_path(root, "notices.json"),
        ]
        if agenda_content is not None:
            _write_json(root / "agenda.json", agenda_content)
            (root / "packet.md").write_text(
                f"# {meeting_title}\n\nPacket version {snapshot.version}\n\n" +
                "\n\n".join(f"{i+1}. {item.get('title','')}\n\n{item.get('department_name','')}"
                    for i,item in enumerate(agenda_content)), encoding="utf-8")
            files.extend([BundleFile.from_path(root,"agenda.json"),BundleFile.from_path(root,"packet.md")])
        for relative, source in (source_files or {}).items():
            target = root / relative
            if Path(relative).is_absolute() or ".." in Path(relative).parts or not target.resolve().is_relative_to(root.resolve()):
                raise ValueError("Invalid packet source destination.")
            target.parent.mkdir(parents=True,exist_ok=True)
            with source.open("rb") as incoming, target.open("xb") as outgoing:
                shutil.copyfileobj(incoming,outgoing)
            files.append(BundleFile.from_path(root,relative))
        bundle = ExportBundle(
            module_name="civicclerk",
            module_version=CIVICCLERK_VERSION,
            civiccore_version=CIVICCORE_VERSION,
            files=files,
            limitations=[
                "Export bundle is a static records-ready snapshot, not a legal sufficiency determination.",
                "Public bundles exclude closed-session and restricted source files.",
            ],
        )
        manifest = write_manifest(root, bundle)
        build_sha256sums(root, files)
        validate_bundle(root)

        event = self.audit_chain.record_event(
            actor=AuditActor(actor_id=actor, actor_type="staff"),
            action="packet_export_bundle.created",
            subject=AuditSubject(subject_id=meeting_id, subject_type="meeting"),
            source_module="civicclerk",
            metadata={
                "packet_version": snapshot.version,
                "bundle_path": str(root),
                "manifest_files": [file.path for file in manifest.generated_files],
                "public_bundle": public_bundle,
            },
        )
        return PacketExportResult(
            meeting_id=meeting_id,
            bundle_path=str(root),
            manifest_path=str(root / "manifest.json"),
            checksums_path=str(root / "SHA256SUMS.txt"),
            civiccore_version=manifest.civiccore_version,
            packet_version=snapshot.version,
            audit_hash=event.current_hash or "",
            generated_files=tuple(file.path for file in manifest.generated_files),
        )


@dataclass(frozen=True)
class NoticeComplianceResult:
    meeting_id: str
    notice_type: str
    scheduled_start: datetime
    posted_at: datetime
    minimum_notice_hours: int
    deadline_at: datetime
    statutory_basis: str | None
    approved_by: str | None
    compliant: bool
    http_status: int
    warnings: list[dict[str, str]]

    def public_dict(self) -> dict:
        return {
            "meeting_id": self.meeting_id,
            "notice_type": self.notice_type,
            "scheduled_start": self.scheduled_start.isoformat(),
            "posted_at": self.posted_at.isoformat(),
            "minimum_notice_hours": self.minimum_notice_hours,
            "deadline_at": self.deadline_at.isoformat(),
            "statutory_basis": self.statutory_basis,
            "approved_by": self.approved_by,
            "compliant": self.compliant,
            "warnings": self.warnings,
        }


@dataclass(frozen=True)
class PostedNotice:
    id: str
    result: NoticeComplianceResult

    def public_dict(self) -> dict:
        return {
            "id": self.id,
            **self.result.public_dict(),
            "posted": True,
        }


class NoticeStore:
    """In-memory posted notice store until DB-backed workflow persistence lands."""

    def __init__(self) -> None:
        self._notices: dict[str, list[PostedNotice]] = {}

    def create(self, result: NoticeComplianceResult) -> PostedNotice:
        notice = PostedNotice(id=str(uuid4()), result=result)
        self._notices.setdefault(result.meeting_id, []).append(notice)
        return notice

    def list_notices(self, meeting_id: str) -> list[PostedNotice]:
        return list(self._notices.get(meeting_id, []))


def evaluate_notice_compliance(
    *,
    meeting_id: str,
    notice_type: str,
    scheduled_start: datetime,
    posted_at: datetime,
    minimum_notice_hours: int,
    statutory_basis: str | None,
    approved_by: str | None,
) -> NoticeComplianceResult:
    shared_result = evaluate_shared_notice_compliance(
        meeting_id=meeting_id,
        notice_type=notice_type,
        scheduled_start=scheduled_start,
        posted_at=posted_at,
        minimum_notice_hours=minimum_notice_hours,
        statutory_basis=statutory_basis,
        approved_by=approved_by,
    )
    return NoticeComplianceResult(
        meeting_id=shared_result.meeting_id,
        notice_type=shared_result.notice_type,
        scheduled_start=shared_result.scheduled_start,
        posted_at=shared_result.posted_at,
        minimum_notice_hours=shared_result.minimum_notice_hours,
        deadline_at=shared_result.deadline_at,
        statutory_basis=shared_result.statutory_basis,
        approved_by=shared_result.approved_by,
        compliant=shared_result.compliant,
        http_status=shared_result.http_status,
        warnings=[warning.public_dict() for warning in shared_result.warnings],
    )


def _write_json(path: Path, payload: dict) -> None:
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


__all__ = [
    "NoticeComplianceResult",
    "NoticeStore",
    "PacketExportError",
    "PacketExportResult",
    "PacketSnapshot",
    "PacketSource",
    "PacketStore",
    "PostedNotice",
    "evaluate_notice_compliance",
]
