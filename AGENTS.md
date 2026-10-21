<a id="civicmeetings-agent-instructions"></a>

# Townlight Meetings Agent Instructions

## Governing Workflow

Use Agent Pipeline for all productization work. The retired `coder-ui-qa-test`
skill is no longer authoritative for this repository.

Pipeline work must preserve evidence in `.agent-runs/<run-id>/` when a run is
active, follow the scoped manifest/scope-lock, and run the repo's own gates
before push or merge.

## Project Purpose

Townlight Meetings is the Townlight module for municipal meeting operations: agenda
intake, packet assembly, statutory notice proof, meeting outcomes, minutes,
public posting, public archives, and Townlight Core-backed integration contracts.

## Stack

- Backend: Python, FastAPI, SQLAlchemy/Alembic, PostgreSQL, Redis, Celery-style
  workers where applicable.
- Frontend: React, Vite, TypeScript.
- Runtime: Docker Compose, local-first deployment.
- Shared platform dependency: Townlight Core, currently pinned to the published
  Townlight Core v1.0.1 release wheel unless a scoped pipeline run changes it.

## Operating Priorities

- Productize Townlight Meetings as part of the Townlight starter set with Townlight Core
  and Townlight Records AI.
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
