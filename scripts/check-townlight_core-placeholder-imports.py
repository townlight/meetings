#!/usr/bin/env python3
"""Preserve Meetings' existing shared-namespace dependency boundary.

Core implements catalog, exemptions and scaffold. Meetings does not consume
those APIs in this candidate; this check prevents adding a new dependency
without changing its owning integration contract. It does not claim those
namespaces are empty or rewrite the historical CO-7 decisions.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path


RESERVED_IMPORTS = ["catalog", "exemptions", "scaffold"]

SOURCE_ROOTS = [
    Path("townlight_meetings"),
    Path("app"),
    Path("backend"),
    Path("src"),
]

SOURCE_SUFFIXES = {".py", ".pyi", ".ts", ".tsx", ".js", ".jsx"}


def source_files() -> list[Path]:
    files: list[Path] = []
    for root in SOURCE_ROOTS:
        if not root.exists():
            continue
        if root.is_file() and root.suffix in SOURCE_SUFFIXES:
            files.append(root)
            continue
        for path in root.rglob("*"):
            if path.is_file() and path.suffix in SOURCE_SUFFIXES:
                files.append(path)
    return sorted(files)


def patterns_for(name: str) -> list[re.Pattern[str]]:
    escaped = re.escape(name)
    return [
        re.compile(rf"^\s*from\s+townlight_core\.{escaped}\b", re.MULTILINE),
        re.compile(rf"^\s*import\s+townlight_core\.{escaped}\b", re.MULTILINE),
        re.compile(rf"['\"]townlight_core\.{escaped}['\"]"),
    ]


def main() -> int:
    failures: list[str] = []
    scanned = source_files()

    for path in scanned:
        text = path.read_text(encoding="utf-8", errors="replace")
        for name in RESERVED_IMPORTS:
            if any(pattern.search(text) for pattern in patterns_for(name)):
                failures.append(f"{path}: townlight_core.{name} is outside Meetings' current integration contract. See AGENTS.md.")

    if failures:
        print("PLACEHOLDER-IMPORT-CHECK: FAILED")
        for failure in failures:
            print(failure)
        return 1

    print(f"PLACEHOLDER-IMPORT-CHECK: PASSED ({len(scanned)} source files scanned)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
