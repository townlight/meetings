<a id="townlight-meetings-agent-instructions"></a>

# Townlight Meetings Agent Instructions

## Governing Workflow

Scott's bounded completion contract governs. Legacy pipeline profiles apply
only when explicitly invoked; they do not authorize delegation, added scope or
repeated gates. Preserve repository-required CI, meaningful affected checks,
actual installed acceptance and historical evidence.

## Project Purpose

Townlight Meetings is the Townlight module for municipal meeting operations: agenda
intake, packet assembly, statutory notice proof, meeting outcomes, minutes,
public posting, public archives, and Townlight Core-backed integration contracts.

## Stack

- Backend: Python, FastAPI, SQLAlchemy/Alembic, PostgreSQL, Redis, Celery-style
  workers where applicable.
- Frontend: React, Vite, TypeScript.
- Runtime: Docker Compose, local-first deployment.
- Distribution/import: `townlight-meetings` / `townlight_meetings`, version1.0.5.
- Shared platform dependency: `townlight-core==1.3.0.dev2`. The exact source
  commit is in `config/core-source.json`; `scripts/install-core-candidate.py`
  builds its local wheel for clean source CI. Never invent a renamed historical
  release asset or fall back to a moving branch/package-index name.

Catalog, exemptions and scaffold are implemented Core contracts in the pinned
candidate. Original CO-7 placeholder ADRs describe their historical freeze.
Use the actual pinned API and owning-product authorization boundaries; a shared
contract does not grant cross-product authority. The selected Windows native
composition and standalone React/Docker application remain distinct deployments.
Meetings does not add catalog, exemption or scaffold consumers in this migration;
its existing dependency-boundary checker remains in force.

The coordinated candidate supports fresh databases/profiles only and refuses
existing unmarked city data. No in-place upgrade or old import shim is provided.
The sole approved old active identifier is `%LOCALAPPDATA%\CivicSuite` for that
profile path. Historical ADRs/receipts retain original names and bytes. Do not
call this candidate installed, accepted or published on source tests alone.

## Operating Priorities

- Productize Townlight Meetings as part of the Townlight starter set with Townlight Core
  and Townlight Records.
- Keep Townlight Core as the shared base tech. Townlight Meetings may depend on Townlight Core;
  Townlight Core must not depend on Townlight Meetings.
- Preserve honest public status language. Do not promote provisional or
  mock-only validation as production deployment proof.
- Favor small, verifiable slices that improve installability, Townlight Core
  integration, UI/UX, operator documentation, and release evidence.

## Required Gates

Before push or merge, run the relevant repo gates directly. At minimum, inspect
the available scripts and CI workflows, then run backend tests, frontend tests,
release/recovery checks, and any installer/runtime proof scripts that apply to
the changed surface.

For release-class work, verify GitHub Actions on the pushed head and verify
public release assets/provenance after tag publication.

## Git Workflow

- Work on a named feature branch.
- Keep changes scoped to the active pipeline run.
- Do not revert unrelated user or prior-agent changes.
- Use conventional commits.
- Push only after local gates are green or a verified blocker is documented.

## Never Do

- Do not skip Windows/Linux lifecycle work when it can be run on this machine.
- Do not claim macOS lifecycle certification while macOS testing is on hold.
- Do not leave stale generated docs, OpenAPI files, or installer/download links
  after version or release-surface changes.
- Do not treat mocked integration evidence as live production deployment proof.
