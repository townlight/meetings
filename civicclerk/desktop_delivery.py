"""Local packet delivery using existing repositories and Core export contracts."""
from pathlib import Path
from uuid import uuid4
import hashlib
import json

from civicclerk.packet_assembly import PacketAssemblyRepository
from civicclerk.packet_notice import PacketStore, PacketSource
from civicclerk.notice_checklist import NoticeChecklistRepository
from civiccore.exports import validate_bundle
from civiccore.exports import BundleFile, ExportBundle, write_manifest, build_sha256sums
from civicclerk import __version__ as module_version
from civiccore import __version__ as core_version


def data_root(profile: Path) -> Path:
    locations = profile / "config" / "locations.json"
    root = Path(json.loads(locations.read_text(encoding="utf-8"))["data_root"]) if locations.exists() else profile / "Data"
    if not root.is_absolute():
        raise ValueError("Configured data root must be absolute.")
    return root.resolve()


def verify_source(profile: Path, receipt: dict) -> Path:
    path = Path(receipt["stored_path"]).resolve(strict=True)
    if not path.is_relative_to(data_root(profile) / "files" / "meetings") or not path.is_file():
        raise ValueError("Source is outside the managed Meetings file store.")
    with path.open("rb") as stream:
        digest = hashlib.file_digest(stream,"sha256").hexdigest()
    if digest != receipt["sha256"] or path.stat().st_size != receipt["size_bytes"]:
        raise ValueError("Source bytes no longer match the captured packet version.")
    return path


def deliver_packet(*, db_url: str, profile: Path, packet_id: str, actor: str) -> dict | None:
    assemblies = PacketAssemblyRepository(db_url=db_url)
    snapshots = PacketStore(db_url=db_url)
    notices = NoticeChecklistRepository(db_url=db_url)
    try:
        packet = assemblies.get(packet_id)
        if packet is None:
            return None
        sources, files = [], {}
        for index, receipt in enumerate(packet.source_references):
            source = verify_source(profile,receipt)
            relative = f"sources/{index+1:03d}-{source.name}"
            files[relative] = source
            sources.append(PacketSource(source_id=source.stem,title=receipt["file_name"],
                source_path=relative,checksum=receipt["sha256"],source_system="local_file",
                sensitivity_label="staff_only"))
        root = data_root(profile) / "exports" / "meetings" / str(uuid4())
        root.mkdir(parents=True,exist_ok=False)
        result = snapshots.create_export_bundle(meeting_id=packet.meeting_id,meeting_title=packet.title,
            bundle_path=root,actor=actor,sources=sources,public_bundle=False,
            snapshot_id=packet.packet_snapshot_id,agenda_content=packet.snapshot_content,source_files=files,
            notices=[n.public_dict() for n in notices.list_for_meeting(packet.meeting_id)])
        for source, relative in zip(packet.source_references,files,strict=True):
            with (root / relative).open("rb") as stream:
                if hashlib.file_digest(stream,"sha256").hexdigest() != source["sha256"]:
                    raise ValueError("Source changed during delivery. Incomplete output retained; no delivery confirmed.")
        manifest = validate_bundle(root)
        receipt = {**result.public_dict(),"delivery_id":root.name,"actor":actor,
            "publication":"staff-only local export; not website publication",
            "files":[f.model_dump(mode="json") for f in manifest.generated_files]}
        record = assemblies.record_delivery(record_id=packet_id,actor=actor,receipt=receipt)
        return record.public_dict()
    finally:
        for store in (assemblies,snapshots,notices):
            store.engine.dispose()


def deliver_notice(*,db_url: str,profile: Path,notice_id: str,text: str,actor: str) -> dict | None:
    """Preserve each staff-authored notice delivery; no publication side effect."""
    store=NoticeChecklistRepository(db_url=db_url)
    try:
        record=store.get(notice_id)
        if record is None:
            return None
        root=data_root(profile)/"exports"/"meetings"/str(uuid4())
        root.mkdir(parents=True,exist_ok=False)
        with (root/"notice.txt").open("x",encoding="utf-8",newline="\n") as output:
            output.write(text)
        files=[BundleFile.from_path(root,"notice.txt")]
        write_manifest(root,ExportBundle(module_name="civicclerk",module_version=module_version,
            civiccore_version=core_version,files=files,limitations=[
                "Staff-authored notice. Local export only, not proof of posting or legal sufficiency."]))
        build_sha256sums(root,files)
        manifest=validate_bundle(root)
        receipt={"delivery_id":root.name,"bundle_path":str(root),"actor":actor,
            "files":[f.model_dump(mode="json") for f in manifest.generated_files]}
        return store.record_document(record_id=notice_id,actor=actor,text=text,receipt=receipt).public_dict()
    finally:
        store.engine.dispose()
