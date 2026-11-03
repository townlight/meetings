from __future__ import annotations

import ast
import importlib
import os
from pathlib import Path
import subprocess
import time
import uuid

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import ForeignKeyConstraint, create_engine, text
from sqlalchemy.engine import make_url


ROOT = Path(__file__).resolve().parents[1]

CANONICAL_TABLES = [
    "meeting_bodies",
    "meetings",
    "agenda_items",
    "staff_reports",
    "motions",
    "votes",
    "public_comments",
    "notices",
    "minutes",
    "transcripts",
    "action_items",
    "packet_versions",
    "ordinances_adopted",
    "closed_sessions",
]

REQUIRED_COLUMNS = {
    "meeting_bodies": {"id", "name", "body_type", "is_active", "created_at", "updated_at"},
    "meetings": {
        "id",
        "meeting_body_id",
        "title",
        "meeting_type",
        "scheduled_start",
        "location",
        "status",
        "statutory_basis",
        "cancelled_at",
        "cancellation_reason",
        "created_at",
        "updated_at",
    },
    "agenda_items": {
        "id",
        "meeting_id",
        "title",
        "status",
        "department_name",
        "source_references",
        "staff_report_required",
        "created_at",
        "updated_at",
    },
    "staff_reports": {
        "id",
        "agenda_item_id",
        "title",
        "body",
        "document_ref",
        "source_references",
        "sensitivity_label",
        "staff_acl_roles",
        "created_at",
        "updated_at",
    },
    "motions": {
        "id",
        "meeting_id",
        "agenda_item_id",
        "text",
        "seconded_by",
        "captured_by",
        "correction_of_id",
        "correction_reason",
        "immutable_hash",
        "created_at",
        "updated_at",
    },
    "votes": {
        "id",
        "motion_id",
        "voter_name",
        "vote",
        "actor",
        "correction_of_id",
        "correction_reason",
        "immutable_hash",
        "created_at",
        "updated_at",
    },
    "public_comments": {
        "id",
        "meeting_id",
        "agenda_item_id",
        "public_record_id",
        "commenter_name",
        "body",
        "visibility",
        "status",
        "submitted_at",
        "moderation_notes",
        "created_at",
        "updated_at",
    },
    "notices": {
        "id",
        "meeting_id",
        "notice_type",
        "due_at",
        "posted_at",
        "statutory_basis",
        "posting_proof",
        "document_ref",
        "created_at",
        "updated_at",
    },
    "minutes": {
        "id",
        "meeting_id",
        "status",
        "body",
        "source_materials",
        "sentence_citations",
        "prompt_version",
        "human_approver",
        "adopted_at",
        "signed_by",
        "document_ref",
        "created_at",
        "updated_at",
    },
    "transcripts": {
        "id",
        "meeting_id",
        "source_uri",
        "status",
        "document_ref",
        "sensitivity_label",
        "staff_acl_roles",
        "created_at",
        "updated_at",
    },
    "action_items": {
        "id",
        "meeting_id",
        "description",
        "status",
        "assigned_to",
        "source_motion_id",
        "created_at",
        "updated_at",
    },
    "packet_versions": {
        "id",
        "meeting_id",
        "version",
        "snapshot_uri",
        "agenda_item_ids",
        "snapshot_hash",
        "actor",
        "created_at",
        "updated_at",
    },
    "ordinances_adopted": {
        "id",
        "meeting_id",
        "agenda_item_id",
        "ordinance_number",
        "title",
        "adopted_at",
        "townlight_code_handoff_status",
        "document_ref",
        "created_at",
        "updated_at",
    },
    "closed_sessions": {
        "id",
        "meeting_id",
        "statutory_basis",
        "access_level",
        "staff_acl_roles",
        "material_uri",
        "public_redaction",
        "sensitivity_label",
        "created_at",
        "updated_at",
    },
}

CC5_EVOLVED_COLUMNS = {
    table_name: columns - {"id", "created_at", "updated_at"} - {
        "name",
        "body_type",
        "is_active",
        "meeting_body_id",
        "title",
        "scheduled_start",
        "status",
        "meeting_id",
        "department_name",
        "agenda_item_id",
        "body",
        "text",
        "motion_id",
        "voter_name",
        "vote",
        "correction_of_id",
        "commenter_name",
        "visibility",
        "notice_type",
        "due_at",
        "posted_at",
        "statutory_basis",
        "source_uri",
        "description",
        "version",
        "snapshot_uri",
        "ordinance_number",
        "access_level",
    }
    for table_name, columns in REQUIRED_COLUMNS.items()
}

PLACEHOLDER_TARGET_PREFIXES = {
    "townlight_core.auth",
    "townlight_core.rbac",
    "townlight_core.ingestion",
    "townlight_core.notifications",
    "townlight_core.exemptions",
    "townlight_core.onboarding",
    "townlight_core.catalog",
}


def model_module():
    try:
        return importlib.import_module("townlight_meetings.models")
    except ModuleNotFoundError as exc:
        pytest.fail(f"townlight_meetings.models must exist for Milestone 2 schema work: {exc}")


def migration_path() -> Path:
    return ROOT / "townlight_meetings" / "migrations" / "versions" / "townlight_meetings_0001_schema.py"


def agenda_intake_migration_path() -> Path:
    return ROOT / "townlight_meetings" / "migrations" / "versions" / "townlight_meetings_0002_agenda_intake_queue.py"


def packet_assembly_migration_path() -> Path:
    return ROOT / "townlight_meetings" / "migrations" / "versions" / "townlight_meetings_0003_packet_assembly_records.py"


def notice_checklist_migration_path() -> Path:
    return ROOT / "townlight_meetings" / "migrations" / "versions" / "townlight_meetings_0004_notice_checklist_records.py"


def meeting_records_migration_path() -> Path:
    return ROOT / "townlight_meetings" / "migrations" / "versions" / "townlight_meetings_0005_meeting_records.py"


def agenda_item_lifecycle_records_migration_path() -> Path:
    return (
        ROOT
        / "townlight_meetings"
        / "migrations"
        / "versions"
        / "townlight_meetings_0006_agenda_item_lifecycle_records.py"
    )


def vendor_sync_persistence_migration_path() -> Path:
    return (
        ROOT
        / "townlight_meetings"
        / "migrations"
        / "versions"
        / "townlight_meetings_0009_vendor_sync_persistence.py"
    )


def data_model_completion_migration_path() -> Path:
    return (
        ROOT
        / "townlight_meetings"
        / "migrations"
        / "versions"
        / "townlight_meetings_0011_data_model_completion.py"
    )


def test_canonical_table_models_exist_and_no_tables_are_missing_or_extra() -> None:
    models = model_module()
    metadata = models.Base.metadata
    townlight_meetings_tables = {
        table.fullname for table in metadata.tables.values() if table.schema == "townlight_meetings"
    }

    assert sorted(townlight_meetings_tables) == sorted(f"townlight_meetings.{name}" for name in CANONICAL_TABLES)


def test_models_use_townlight_meetings_schema_and_townlight_core_shared_base() -> None:
    models = model_module()
    townlight_core_db = importlib.import_module("townlight_core.db")

    assert models.Base is townlight_core_db.Base
    for table_name in CANONICAL_TABLES:
        table = models.Base.metadata.tables[f"townlight_meetings.{table_name}"]
        assert table.schema == "townlight_meetings"


def test_models_do_not_declare_a_competing_sqlalchemy_base() -> None:
    model_files = list((ROOT / "townlight_meetings").glob("**/*.py"))
    offenders: list[str] = []
    for path in model_files:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                for base in node.bases:
                    if getattr(base, "id", None) == "DeclarativeBase":
                        offenders.append(str(path.relative_to(ROOT)))
            if isinstance(node, ast.Call) and getattr(node.func, "id", None) == "declarative_base":
                offenders.append(str(path.relative_to(ROOT)))

    assert offenders == []


def test_each_canonical_table_has_required_foundation_columns() -> None:
    models = model_module()

    for table_name, expected_columns in REQUIRED_COLUMNS.items():
        table = models.Base.metadata.tables[f"townlight_meetings.{table_name}"]
        assert expected_columns <= set(table.columns.keys()), table_name


def test_no_foreign_keys_target_townlight_core_placeholder_packages_or_unreleased_shared_tables() -> None:
    models = model_module()

    for table in models.Base.metadata.tables.values():
        for constraint in table.constraints:
            if not isinstance(constraint, ForeignKeyConstraint):
                continue
            for element in constraint.elements:
                target = str(element.target_fullname)
                assert not any(target.startswith(prefix) for prefix in PLACEHOLDER_TARGET_PREFIXES)
                assert not target.startswith("townlight_core."), (
                    "CivicMeetings may only FK into TownlightCore tables that exist in v0.3.0; "
                    f"unexpected target: {target}"
                )


def test_alembic_scaffold_exists_for_townlight_meetings_schema_chain() -> None:
    expected = [
        ROOT / "townlight_meetings" / "migrations" / "alembic.ini",
        ROOT / "townlight_meetings" / "migrations" / "env.py",
        migration_path(),
        agenda_intake_migration_path(),
        packet_assembly_migration_path(),
        notice_checklist_migration_path(),
        meeting_records_migration_path(),
        agenda_item_lifecycle_records_migration_path(),
        vendor_sync_persistence_migration_path(),
        data_model_completion_migration_path(),
    ]

    for path in expected:
        assert path.exists(), f"Missing migration scaffold file: {path.relative_to(ROOT)}"


def test_alembic_env_runs_townlight_core_baseline_first_and_uses_separate_version_table() -> None:
    env_py = ROOT / "townlight_meetings" / "migrations" / "env.py"
    assert env_py.exists(), "townlight_meetings migrations env.py must exist."
    text = env_py.read_text(encoding="utf-8")

    assert "townlight_core.migrations.runner" in text
    assert "upgrade_to_head" in text
    assert "_database_url()" in text
    assert "_run_townlight_core_migrations(section[\"sqlalchemy.url\"])" in text
    assert "subprocess.run" in text
    assert "version_table=\"alembic_version_townlight_meetings\"" in text or "version_table = \"alembic_version_townlight_meetings\"" in text
    assert "target_metadata = Base.metadata" in text


def test_alembic_command_upgrades_real_pgvector_database(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Run the actual operator migration path against disposable Postgres."""
    name = f"townlight_meetings-m2-{uuid.uuid4().hex[:12]}"
    docker_host = os.environ.get("TOWNLIGHT_MEETINGS_DOCKER_HOST_ADDRESS", "127.0.0.1")
    external_url = os.environ.get("TOWNLIGHT_MEETINGS_TEST_DATABASE_URL")
    if external_url:
        target = make_url(external_url)
        assert target.host in {"127.0.0.1", "localhost"}
        assert target.database and target.database.startswith("townlight_meetings_") and target.database.endswith("_test")
        with create_engine(external_url).connect() as connection:
            assert connection.execute(text(
                "SELECT count(*) FROM information_schema.tables WHERE table_schema NOT IN ('pg_catalog', 'information_schema')"
            )).scalar_one() == 0, "External migration test requires a new empty disposable database"
    else:
        subprocess.run(
            [
                "docker", "run", "--name", name,
                "-e", "POSTGRES_PASSWORD=postgres",
                "-e", "POSTGRES_USER=postgres",
                "-e", "POSTGRES_DB=townlight_meetings_test",
                "-p", "5432", "-d", "pgvector/pgvector:pg17",
            ],
            check=True,
            capture_output=True,
            text=True,
        )

    try:
        if external_url:
            db_url = external_url
        else:
            mapped = subprocess.run(
                ["docker", "port", name, "5432/tcp"],
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()
            port = mapped.rsplit(":", maxsplit=1)[-1]
            db_url = f"postgresql+psycopg2://postgres:postgres@{docker_host}:{port}/townlight_meetings_test"
        engine = create_engine(db_url)

        deadline = time.monotonic() + 30
        while True:
            try:
                with engine.connect() as connection:
                    connection.execute(text("select 1"))
                break
            except Exception:
                if time.monotonic() > deadline:
                    raise
                time.sleep(1)

        monkeypatch.setenv("DATABASE_URL", db_url)
        cfg = Config(str(ROOT / "townlight_meetings" / "migrations" / "alembic.ini"))

        command.upgrade(cfg, "townlight_meetings_0016")
        command.upgrade(cfg, "townlight_meetings_0016")

        with engine.connect() as connection:
            townlight_core_revision = connection.execute(
                text("select version_num from alembic_version_townlight_core")
            ).scalar_one()
            townlight_meetings_revision = connection.execute(
                text("select version_num from alembic_version_townlight_meetings")
            ).scalar_one()
            packet_version_columns = set(
                connection.execute(
                    text(
                        """
                        select column_name
                        from information_schema.columns
                        where table_schema = 'townlight_meetings'
                          and table_name = 'packet_versions'
                        """
                    )
                ).scalars()
            )
            packet_version_constraints = set(
                connection.execute(
                    text(
                        """
                        select constraint_name
                        from information_schema.table_constraints
                        where table_schema = 'townlight_meetings'
                          and table_name = 'packet_versions'
                        """
                    )
                ).scalars()
            )
            townlight_meetings_tables = set(
                connection.execute(
                    text(
                        """
                        select table_name
                        from information_schema.tables
                        where table_schema = 'townlight_meetings'
                        """
                    )
                ).scalars()
            )

        assert townlight_core_revision == "townlight_core_0009"
        assert townlight_meetings_revision == "townlight_meetings_0016"
        assert {"agenda_item_ids", "snapshot_hash", "actor"} <= packet_version_columns
        assert "uq_packet_versions_meeting_version" in packet_version_constraints
        assert townlight_meetings_tables == set(CANONICAL_TABLES) | {
            "agenda_item_lifecycle_records",
            "agenda_intake_queue",
            "meeting_records",
            "notice_checklist_records",
            "packet_assembly_records",
            "public_meeting_records",
            "vendor_sync_failures",
            "vendor_sync_run_log",
            "vendor_sync_sources",
        }

        command.downgrade(cfg, "townlight_meetings_0010")
        with engine.connect() as connection:
            downgraded_revision = connection.execute(
                text("select version_num from alembic_version_townlight_meetings")
            ).scalar_one()
            downgraded_packet_columns = set(
                connection.execute(
                    text(
                        """
                        select column_name
                        from information_schema.columns
                        where table_schema = 'townlight_meetings'
                          and table_name = 'packet_versions'
                        """
                    )
                ).scalars()
            )
        assert downgraded_revision == "townlight_meetings_0010"
        assert "snapshot_hash" not in downgraded_packet_columns

        command.upgrade(cfg, "head")
        with engine.connect() as connection:
            reupgraded_revision = connection.execute(
                text("select version_num from alembic_version_townlight_meetings")
            ).scalar_one()
            reupgraded_packet_columns = set(
                connection.execute(
                    text(
                        """
                        select column_name
                        from information_schema.columns
                        where table_schema = 'townlight_meetings'
                          and table_name = 'packet_versions'
                        """
                    )
                ).scalars()
            )
        assert reupgraded_revision == "townlight_meetings_0021"
        assert {"agenda_item_ids", "snapshot_hash", "actor"} <= reupgraded_packet_columns

        with pytest.raises(RuntimeError, match="recover forward"):
            command.downgrade(cfg, "townlight_meetings_0010")

        with engine.connect() as conn:
            post_refusal_revision = conn.execute(
                text("SELECT version_num FROM alembic_version_townlight_meetings")
            ).scalar_one()
        assert post_refusal_revision == "townlight_meetings_0021"
    finally:
        if not external_url:
            subprocess.run(["docker", "rm", "-f", name], check=False, capture_output=True, text=True)


def test_first_migration_declares_revision_and_creates_all_canonical_tables_idempotently() -> None:
    assert migration_path().exists(), "townlight_meetings_0001_schema migration must exist."
    text = migration_path().read_text(encoding="utf-8")

    assert 'revision = "townlight_meetings_0001"' in text
    assert "down_revision = None" in text
    assert "idempotent_create_table" in text
    assert 'op.execute("CREATE SCHEMA IF NOT EXISTS townlight_meetings")' in text

    for table_name in CANONICAL_TABLES:
        assert f'"{table_name}"' in text or f"'{table_name}'" in text
        assert 'schema="townlight_meetings"' in text or "schema='townlight_meetings'" in text


def test_migration_table_list_matches_model_metadata() -> None:
    models = model_module()
    text = migration_path().read_text(encoding="utf-8")

    model_tables = {
        table.name for table in models.Base.metadata.tables.values() if table.schema == "townlight_meetings"
    }
    for table_name in model_tables:
        assert f'"{table_name}"' in text or f"'{table_name}'" in text


def test_agenda_intake_migration_declares_persistent_queue_table() -> None:
    text = agenda_intake_migration_path().read_text(encoding="utf-8")

    assert 'revision = "townlight_meetings_0002"' in text
    assert 'down_revision = "townlight_meetings_0001"' in text
    assert "idempotent_create_table" in text
    assert '"agenda_intake_queue"' in text
    assert '"last_audit_hash"' in text
    assert "postgresql.JSONB()" in text
    assert 'schema="townlight_meetings"' in text


def test_packet_assembly_migration_declares_persistent_records_table() -> None:
    text = packet_assembly_migration_path().read_text(encoding="utf-8")

    assert 'revision = "townlight_meetings_0003"' in text
    assert 'down_revision = "townlight_meetings_0002"' in text
    assert "idempotent_create_table" in text
    assert '"packet_assembly_records"' in text
    assert '"packet_snapshot_id"' in text
    assert '"source_references"' in text
    assert '"citations"' in text
    assert '"last_audit_hash"' in text
    assert "postgresql.JSONB()" in text
    assert 'schema="townlight_meetings"' in text


def test_notice_checklist_migration_declares_persistent_records_table() -> None:
    text = notice_checklist_migration_path().read_text(encoding="utf-8")

    assert 'revision = "townlight_meetings_0004"' in text
    assert 'down_revision = "townlight_meetings_0003"' in text
    assert "idempotent_create_table" in text
    assert '"notice_checklist_records"' in text
    assert '"warnings"' in text
    assert '"posting_proof"' in text
    assert '"last_audit_hash"' in text
    assert "postgresql.JSONB()" in text
    assert 'schema="townlight_meetings"' in text


def test_meeting_records_migration_declares_persistent_records_table() -> None:
    text = meeting_records_migration_path().read_text(encoding="utf-8")

    assert 'revision = "townlight_meetings_0005"' in text
    assert 'down_revision = "townlight_meetings_0004"' in text
    assert "idempotent_create_table" in text
    assert '"meeting_records"' in text
    assert '"meeting_type"' in text
    assert '"scheduled_start"' in text
    assert '"audit_entries"' in text
    assert "postgresql.JSONB()" in text
    assert 'schema="townlight_meetings"' in text


def test_agenda_item_lifecycle_records_migration_declares_persistent_records_table() -> None:
    text = agenda_item_lifecycle_records_migration_path().read_text(encoding="utf-8")

    assert 'revision = "townlight_meetings_0006"' in text
    assert 'down_revision = "townlight_meetings_0005"' in text
    assert "idempotent_create_table" in text
    assert '"agenda_item_lifecycle_records"' in text
    assert '"department_name"' in text
    assert '"audit_entries"' in text
    assert "postgresql.JSONB()" in text
    assert 'schema="townlight_meetings"' in text


def test_vendor_sync_persistence_migration_declares_source_run_and_failure_tables() -> None:
    text = vendor_sync_persistence_migration_path().read_text(encoding="utf-8")

    assert 'revision = "townlight_meetings_0009"' in text
    assert 'down_revision = "townlight_meetings_0008"' in text
    assert "idempotent_create_table" in text
    assert '"vendor_sync_sources"' in text
    assert '"vendor_sync_run_log"' in text
    assert '"vendor_sync_failures"' in text
    assert '"consecutive_failure_count"' in text
    assert '"sync_paused_reason"' in text
    assert 'schema="townlight_meetings"' in text


def test_vendor_sync_cursor_migration_declares_success_cursor_column() -> None:
    text = (ROOT / "townlight_meetings" / "migrations" / "versions" / "townlight_meetings_0010_vendor_sync_cursor.py").read_text(
        encoding="utf-8"
    )

    assert 'revision = "townlight_meetings_0010"' in text
    assert 'down_revision = "townlight_meetings_0009"' in text
    assert '"last_success_cursor_at"' in text
    assert 'schema="townlight_meetings"' in text


def test_data_model_completion_migration_declares_reversible_cc5_contract() -> None:
    text = data_model_completion_migration_path().read_text(encoding="utf-8")

    assert 'revision = "townlight_meetings_0011"' in text
    assert 'down_revision = "townlight_meetings_0010"' in text
    for table_name, column_names in CC5_EVOLVED_COLUMNS.items():
        if not column_names:
            continue
        assert f'"{table_name}"' in text
        for column_name in column_names:
            assert f'"{column_name}"' in text
    assert "uq_packet_versions_meeting_version" in text
    assert "fk_action_items_source_motion_id_motions" in text
    assert "op.add_column" in text
    assert "op.drop_column" in text
    assert "op.create_unique_constraint" in text
    assert "op.drop_constraint" in text


def test_packet_versions_are_versioned_per_meeting_by_schema_contract() -> None:
    models = model_module()
    table = models.Base.metadata.tables["townlight_meetings.packet_versions"]

    unique_constraints = {
        constraint.name: tuple(column.name for column in constraint.columns)
        for constraint in table.constraints
        if getattr(constraint, "name", None)
    }
    assert unique_constraints["uq_packet_versions_meeting_version"] == ("meeting_id", "version")
    assert {"agenda_item_ids", "snapshot_hash", "actor"} <= set(table.columns.keys())


def test_motion_vote_canonical_tables_preserve_append_only_correction_contract() -> None:
    models = model_module()
    motions = models.Base.metadata.tables["townlight_meetings.motions"]
    votes = models.Base.metadata.tables["townlight_meetings.votes"]

    assert {"correction_of_id", "correction_reason", "immutable_hash", "seconded_by"} <= set(motions.columns.keys())
    assert {"correction_of_id", "correction_reason", "immutable_hash", "actor"} <= set(votes.columns.keys())
    assert any(
        element.target_fullname == "townlight_meetings.motions.id"
        for constraint in motions.foreign_key_constraints
        for element in constraint.elements
        if element.parent.name == "correction_of_id"
    )
    assert any(
        element.target_fullname == "townlight_meetings.votes.id"
        for constraint in votes.foreign_key_constraints
        for element in constraint.elements
        if element.parent.name == "correction_of_id"
    )


def test_closed_session_material_has_staff_only_acl_schema_contract() -> None:
    models = model_module()
    closed_sessions = models.Base.metadata.tables["townlight_meetings.closed_sessions"]
    staff_reports = models.Base.metadata.tables["townlight_meetings.staff_reports"]
    transcripts = models.Base.metadata.tables["townlight_meetings.transcripts"]

    for table in [closed_sessions, staff_reports, transcripts]:
        assert {"sensitivity_label", "staff_acl_roles"} <= set(table.columns.keys())
    assert {"material_uri", "public_redaction"} <= set(closed_sessions.columns.keys())


def test_public_comment_schema_matches_live_public_comment_intake_contract() -> None:
    models = model_module()
    public_comments = models.Base.metadata.tables["townlight_meetings.public_comments"]

    assert {
        "public_record_id",
        "commenter_name",
        "body",
        "status",
        "submitted_at",
        "moderation_notes",
    } <= set(public_comments.columns.keys())


def test_townlight_core_document_and_search_extraction_boundary_is_documented() -> None:
    public_archive = (ROOT / "townlight_meetings" / "public_archive.py").read_text(encoding="utf-8")
    adr = (ROOT / "docs" / "adr" / "civicclerk-adr-0006.md").read_text(encoding="utf-8").lower()

    assert "from townlight_core.search import" in public_archive
    assert "status: accepted" in adr
    assert "civiccore 1.2.0 ships search helpers" in adr  # Original historical ADR.
    assert "shared ingestion/document-chunk primitives" in adr
    assert "module-local until its own release train migrates" in adr
    assert "document_ref" in adr
    assert "extraction plan" in adr


def test_docs_and_changelog_record_schema_milestone_without_claiming_lifecycle_behavior_historical_edition() -> None:
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8").lower()
    manual = (ROOT / "docs" / "history" / "pre-townlight-beta-1" / "USER-MANUAL.md").read_text(encoding="utf-8").lower()
    landing = (ROOT / "docs" / "history" / "pre-townlight-beta-1" / "docs" / "index.html").read_text(encoding="utf-8").lower()

    for document_text in [changelog, manual, landing]:
        assert "canonical schema" in document_text
        assert "alembic" in document_text
        assert "agenda lifecycle enforcement shipped" not in document_text
        assert "meeting workflows are implemented" not in document_text


def test_cc5_docs_claims_registry_maps_data_model_claims_to_tests_historical_edition() -> None:
    readme = (ROOT / "docs" / "history" / "pre-townlight-beta-1" / "README.md").read_text(encoding="utf-8")
    manual = (ROOT / "docs" / "history" / "pre-townlight-beta-1" / "USER-MANUAL.md").read_text(encoding="utf-8")
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    landing = (ROOT / "docs" / "history" / "pre-townlight-beta-1" / "docs" / "index.html").read_text(encoding="utf-8")

    assert "### CC-5 data model claims registry" in readme
    assert "civicclerk_0011" in readme
    assert "test_packet_versions_are_versioned_per_meeting_by_schema_contract" in readme
    assert "test_civiccore_document_and_search_extraction_boundary_is_documented" in readme
    for text in [manual, changelog, landing]:
        assert "CC-5" in text
        assert "civicclerk_0011" in text
        assert "closed-session ACL" in text
