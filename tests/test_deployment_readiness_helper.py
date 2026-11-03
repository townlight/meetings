from __future__ import annotations

import sys

import os
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VERSION = "1.0.5"
DEPLOYMENT_ENV_VARS = (
    "TOWNLIGHT_MEETINGS_STAFF_AUTH_MODE",
    "TOWNLIGHT_MEETINGS_STAFF_AUTH_TOKEN_ROLES",
    "TOWNLIGHT_MEETINGS_STAFF_SSO_TRUSTED_PROXIES",
    "TOWNLIGHT_MEETINGS_AGENDA_INTAKE_DB_URL",
    "TOWNLIGHT_MEETINGS_AGENDA_ITEM_DB_URL",
    "TOWNLIGHT_MEETINGS_MEETING_DB_URL",
    "TOWNLIGHT_MEETINGS_PACKET_ASSEMBLY_DB_URL",
    "TOWNLIGHT_MEETINGS_NOTICE_CHECKLIST_DB_URL",
    "TOWNLIGHT_MEETINGS_EXPORT_ROOT",
    "TOWNLIGHT_MEETINGS_DEPLOYMENT_PREFLIGHT_DIST_ROOT",
)


def _base_env() -> dict[str, str]:
    env = os.environ.copy()
    for name in DEPLOYMENT_ENV_VARS:
        env.pop(name, None)
    return env


def test_deployment_readiness_helper_reports_local_rehearsal_as_not_deployment_ready() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/check_deployment_readiness.py"],
        cwd=ROOT,
        env=_base_env(),
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    output = result.stdout
    assert "Townlight Meetings deployment readiness preflight" in output
    assert "deployment_ready=false" in output
    assert "[WARN] staff auth: protected mode denies anonymous staff writes but still needs bearer, OIDC, or trusted-header auth before deployment." in output
    assert "TOWNLIGHT_MEETINGS_STAFF_AUTH_MODE=bearer" in output
    assert "missing deployment database URLs" in output
    assert "values are intentionally not printed" not in output


def test_deployment_readiness_helper_strict_fails_when_not_deployment_ready() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/check_deployment_readiness.py", "--strict"],
        cwd=ROOT,
        env=_base_env(),
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert "deployment_ready=false" in result.stdout


def test_deployment_readiness_helper_passes_configured_bearer_environment(tmp_path: Path) -> None:
    env = _base_env()
    dist_root = tmp_path / "dist"
    dist_root.mkdir()
    for name in [
        f"townlight_meetings-{VERSION}-py3-none-any.whl",
        f"townlight_meetings-{VERSION}.tar.gz",
        "SHA256SUMS.txt",
    ]:
        (dist_root / name).write_text("test artifact\n", encoding="utf-8")

    env.update(
        {
            "TOWNLIGHT_MEETINGS_STAFF_AUTH_MODE": "bearer",
            "TOWNLIGHT_MEETINGS_STAFF_AUTH_TOKEN_ROLES": '{"clerk-token":["clerk_admin","meeting_editor"]}',
            "TOWNLIGHT_MEETINGS_AGENDA_INTAKE_DB_URL": f"sqlite:///{tmp_path / 'intake.db'}",
            "TOWNLIGHT_MEETINGS_AGENDA_ITEM_DB_URL": f"sqlite:///{tmp_path / 'items.db'}",
            "TOWNLIGHT_MEETINGS_MEETING_DB_URL": f"sqlite:///{tmp_path / 'meetings.db'}",
            "TOWNLIGHT_MEETINGS_PACKET_ASSEMBLY_DB_URL": f"sqlite:///{tmp_path / 'packet.db'}",
            "TOWNLIGHT_MEETINGS_NOTICE_CHECKLIST_DB_URL": f"sqlite:///{tmp_path / 'notice.db'}",
            "TOWNLIGHT_MEETINGS_EXPORT_ROOT": str(tmp_path / "exports"),
            "TOWNLIGHT_MEETINGS_DEPLOYMENT_PREFLIGHT_DIST_ROOT": str(dist_root),
        }
    )

    result = subprocess.run(
        [sys.executable, "scripts/check_deployment_readiness.py", "--strict"],
        cwd=ROOT,
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    output = result.stdout
    assert "deployment_ready=true" in output
    assert "[PASS] staff auth: bearer mode reports deployment_ready=true." in output
    assert "[PASS] persistent stores: all deployment database URL environment variables are set" in output
    assert "clerk-token" not in output


def test_deployment_readiness_helper_loads_env_file_without_printing_secrets(tmp_path: Path) -> None:
    env = _base_env()
    dist_root = tmp_path / "dist"
    dist_root.mkdir()
    for name in [
        f"townlight_meetings-{VERSION}-py3-none-any.whl",
        f"townlight_meetings-{VERSION}.tar.gz",
        "SHA256SUMS.txt",
    ]:
        (dist_root / name).write_text("test artifact\n", encoding="utf-8")

    profile = tmp_path / "deployment.env"
    profile.write_text(
        "\n".join(
            [
                "# Townlight Meetings deployment profile",
                "export TOWNLIGHT_MEETINGS_STAFF_AUTH_MODE=bearer",
                "TOWNLIGHT_MEETINGS_STAFF_AUTH_TOKEN_ROLES='{\"secret-token\":[\"clerk_admin\",\"meeting_editor\"]}'",
                f"TOWNLIGHT_MEETINGS_AGENDA_INTAKE_DB_URL=sqlite:///{tmp_path / 'intake.db'}",
                f"TOWNLIGHT_MEETINGS_AGENDA_ITEM_DB_URL=sqlite:///{tmp_path / 'items.db'}",
                f"TOWNLIGHT_MEETINGS_MEETING_DB_URL=sqlite:///{tmp_path / 'meetings.db'}",
                f"TOWNLIGHT_MEETINGS_PACKET_ASSEMBLY_DB_URL=sqlite:///{tmp_path / 'packet.db'}",
                f"TOWNLIGHT_MEETINGS_NOTICE_CHECKLIST_DB_URL=sqlite:///{tmp_path / 'notice.db'}",
                f"TOWNLIGHT_MEETINGS_EXPORT_ROOT={tmp_path / 'exports'}",
                f"TOWNLIGHT_MEETINGS_DEPLOYMENT_PREFLIGHT_DIST_ROOT={dist_root}",
            ]
        ),
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            "scripts/check_deployment_readiness.py",
            "--env-file",
            str(profile),
            "--strict",
        ],
        cwd=ROOT,
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "env_file=" in result.stdout
    assert "deployment_ready=true" in result.stdout
    assert "secret-token" not in result.stdout
    assert str(tmp_path / "intake.db") not in result.stdout


def test_deployment_env_example_documents_required_profile_keys_historical_edition() -> None:
    example = (ROOT / "docs" / "examples" / "deployment.env.example").read_text(encoding="utf-8")
    docs = "\n".join(
        [
            (ROOT / "docs" / "history" / "pre-townlight-beta-1" / "README.md").read_text(encoding="utf-8"),
            (ROOT / "docs" / "history" / "pre-townlight-beta-1" / "USER-MANUAL.md").read_text(encoding="utf-8"),
            (ROOT / "docs" / "history" / "pre-townlight-beta-1" / "docs" / "index.html").read_text(encoding="utf-8"),
        ]
    )

    for expected in DEPLOYMENT_ENV_VARS:
        if expected == "TOWNLIGHT_MEETINGS_STAFF_SSO_TRUSTED_PROXIES":
            continue
        assert expected in example
    assert "python scripts/check_deployment_readiness.py --env-file" in example
    assert "docs/examples/deployment.env.example" in docs


def test_deployment_env_example_is_not_mistaken_for_completed_profile() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "scripts/check_deployment_readiness.py",
            "--env-file",
            "docs/examples/deployment.env.example",
            "--strict",
        ],
        cwd=ROOT,
        env=_base_env(),
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert "deployment_ready=false" in result.stdout
    assert "[WARN] deployment profile placeholders:" in result.stdout
    assert "replace-with-secret-token" not in result.stdout
