"""Verify Townlight Meetings' contract inside the Townlight starter-set installer."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from townlight_meetings import __version__


DEFAULT_UMBRELLA_ROOT = ROOT.parent / "townlight"
EXPECTED_TOWNLIGHT_CORE_RUNTIME = "1.3.0.dev2"
EXPECTED_RECORDS_VERSION = "1.8.0.dev2"


@dataclass(frozen=True)
class Check:
    status: str
    name: str
    message: str
    fix: str

    def public_dict(self) -> dict[str, str]:
        return {
            "status": self.status,
            "name": self.name,
            "message": self.message,
            "fix": self.fix,
        }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Check Townlight Meetings' Townlight starter-set installer contract."
    )
    parser.add_argument(
        "--umbrella-root",
        default=str(DEFAULT_UMBRELLA_ROOT),
        help="Path to the sibling townlight umbrella checkout.",
    )
    parser.add_argument("--output", help="Optional JSON report path.")
    parser.add_argument(
        "--require-archives",
        action="store_true",
        help="Fail unless the generated Linux and Windows starter-set archives exist.",
    )
    parser.add_argument(
        "--print-only",
        action="store_true",
        help="Print the starter-set integration plan without reading the umbrella checkout.",
    )
    return parser.parse_args()


def _pass(name: str, message: str) -> Check:
    return Check(status="PASS", name=name, message=message, fix="No action required.")


def _fail(name: str, message: str, fix: str) -> Check:
    return Check(status="FAIL", name=name, message=message, fix=fix)


def _load_json(path: Path) -> dict[str, object] | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return data


def build_checks(*, umbrella_root: Path, require_archives: bool) -> list[Check]:
    checks: list[Check] = []
    modules_path = umbrella_root / "installer" / "modules.json"
    manifest = _load_json(modules_path)
    if manifest is None:
        return [
            _fail(
                "umbrella checkout",
                f"missing umbrella installer manifest at {modules_path}",
                "Pass --umbrella-root pointing to the townlight checkout before using this as release evidence.",
            )
        ]

    profiles = {str(item.get("id")): item for item in manifest.get("profiles", []) if isinstance(item, dict)}
    modules = {str(item.get("id")): item for item in manifest.get("modules", []) if isinstance(item, dict)}

    clerk_core = profiles.get("clerk-core")
    if isinstance(clerk_core, dict) and clerk_core.get("modules") == [
        "townlight_core",
        "townlight_records",
        "townlight_meetings",
    ]:
        checks.append(
            _pass(
                "clerk-core profile order",
                "clerk-core installs TownlightCore first, then TownlightRecords, then Townlight Meetings.",
            )
        )
    else:
        checks.append(
            _fail(
                "clerk-core profile order",
                "clerk-core profile does not resolve to townlight_core, townlight_records, townlight_meetings.",
                "Fix townlight/installer/modules.json before publishing Townlight Meetings as a starter-set module.",
            )
        )

    clerk = modules.get("townlight_meetings")
    if isinstance(clerk, dict):
        if (
            clerk.get("selectable") is True
            and clerk.get("current_version") == __version__
            and clerk.get("townlight_core_requirement") == EXPECTED_TOWNLIGHT_CORE_RUNTIME
            and "townlight_core" in clerk.get("dependencies", [])
        ):
            checks.append(
                _pass(
                    "Townlight Meetings module contract",
                    f"Townlight Meetings is selectable at v{__version__} and depends on TownlightCore {EXPECTED_TOWNLIGHT_CORE_RUNTIME}.",
                )
            )
        else:
            checks.append(
                _fail(
                    "Townlight Meetings module contract",
                    "Townlight Meetings manifest entry does not match its version, selectability, or TownlightCore dependency.",
                    "Update the umbrella module manifest and rerun the starter-set installer verification.",
                )
            )
    else:
        checks.append(
            _fail(
                "Townlight Meetings module contract",
                "umbrella manifest has no townlight_meetings module entry.",
                "Add Townlight Meetings to townlight/installer/modules.json.",
            )
        )

    records = modules.get("townlight_records")
    if isinstance(records, dict) and records.get("current_version") == EXPECTED_RECORDS_VERSION:
        checks.append(
            _pass(
                "Townlight Records pairing",
                f"starter set pairs Townlight Meetings with TownlightRecords {EXPECTED_RECORDS_VERSION}.",
            )
        )
    else:
        checks.append(
            _fail(
                "Townlight Records pairing",
                "starter set does not record the expected TownlightRecords pairing.",
                "Update the umbrella manifest or this checker before changing the starter-set pair.",
            )
        )

    contract_path = umbrella_root / "docs" / "installer" / "starter-set-release-contract.md"
    if contract_path.is_file():
        text = contract_path.read_text(encoding="utf-8")
        required_phrases = (
            "Townlight Core installs first",
            "Townlight Records and Townlight Meetings are selectable",
            f"Townlight Meetings reports version {__version__} with Townlight Core {EXPECTED_TOWNLIGHT_CORE_RUNTIME}",
            "exact signed Windows installed acceptance remains pending",
            "source-only checks do not certify an installer",
        )
        missing = [phrase for phrase in required_phrases if phrase not in text]
        if missing:
            checks.append(
                _fail(
                    "starter-set release contract",
                    "release contract is missing: " + ", ".join(missing),
                    "Restore the umbrella starter-set release contract before relying on Townlight Meetings installer evidence.",
                )
            )
        else:
            checks.append(
                _pass(
                    "starter-set release contract",
                    "umbrella release contract records selectable modules, workflow proof, and current live-exchange boundary.",
                )
            )
    else:
        checks.append(
            _fail(
                "starter-set release contract",
                f"missing {contract_path}",
                "Add docs/installer/starter-set-release-contract.md to the umbrella repo.",
            )
        )

    archive_paths = (
        umbrella_root / "installer" / "dist" / "Townlight-clerk-core-linux-0.1.0.tar.gz",
        umbrella_root / "installer" / "dist" / "Townlight-clerk-core-windows-0.1.0.zip",
    )
    missing_archives = [path.name for path in archive_paths if not path.is_file()]
    if missing_archives and require_archives:
        checks.append(
            _fail(
                "starter-set archives",
                "missing generated release archives: " + ", ".join(missing_archives),
                "Run the umbrella installer artifact generator and rerun this check.",
            )
        )
    elif missing_archives:
        checks.append(
            Check(
                status="WARN",
                name="starter-set archives",
                message="generated release archives are not present in this checkout: " + ", ".join(missing_archives),
                fix="Use --require-archives for release evidence; warning-only is acceptable in source-only CI.",
            )
        )
    else:
        checks.append(
            _pass(
                "starter-set archives",
                "Linux and Windows starter-set release archives are present.",
            )
        )

    return checks


def _payload(checks: list[Check], umbrella_root: Path) -> dict[str, object]:
    return {
        "product": "Townlight Meetings",
        "version": __version__,
        "umbrella_root": str(umbrella_root),
        "starter_set_ready": all(check.status in {"PASS", "WARN"} for check in checks),
        "release_evidence_ready": all(check.status == "PASS" for check in checks),
        "townlight_core_runtime": EXPECTED_TOWNLIGHT_CORE_RUNTIME,
        "townlight_records_pair": EXPECTED_RECORDS_VERSION,
        "checks": [check.public_dict() for check in checks],
    }


def _print_report(checks: list[Check], umbrella_root: Path) -> None:
    payload = _payload(checks, umbrella_root)
    print("Townlight Meetings starter-set integration")
    print(f"Version: {__version__}")
    print(f"Umbrella root: {umbrella_root}")
    print(f"starter_set_ready={str(payload['starter_set_ready']).lower()}")
    print(f"release_evidence_ready={str(payload['release_evidence_ready']).lower()}")
    for check in checks:
        print(f"[{check.status}] {check.name}: {check.message}")
        print(f"  fix: {check.fix}")
    if payload["release_evidence_ready"]:
        print("STARTER-SET-INTEGRATION: RELEASE-EVIDENCE-READY")
    elif payload["starter_set_ready"]:
        print("STARTER-SET-INTEGRATION: SOURCE-READY")
    else:
        print("STARTER-SET-INTEGRATION: FAILED")


def _print_plan() -> None:
    print("Townlight Meetings starter-set integration")
    print("Release evidence checks:")
    print("  1. Umbrella clerk-core profile installs Townlight Core, Townlight Records, then Townlight Meetings.")
    print(f"  2. Townlight Meetings is selectable and records its Townlight Core {EXPECTED_TOWNLIGHT_CORE_RUNTIME} runtime dependency.")
    print(f"  3. Townlight Records is paired at v{EXPECTED_RECORDS_VERSION}.")
    print("  4. Umbrella release contract requires package workflow proof.")
    print("  5. Linux and Windows starter-set archives exist when --require-archives is used.")
    print("STARTER-SET-INTEGRATION: PLAN")


def main() -> int:
    args = parse_args()
    if args.print_only:
        _print_plan()
        return 0
    umbrella_root = Path(args.umbrella_root).resolve()
    checks = build_checks(umbrella_root=umbrella_root, require_archives=args.require_archives)
    payload = _payload(checks, umbrella_root)
    if args.output:
        Path(args.output).write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    _print_report(checks, umbrella_root)
    return 0 if payload["starter_set_ready"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
