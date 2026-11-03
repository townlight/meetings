<a id="cc-1-townlight-meetings-cleanroom-harness"></a>

# CC-1 Townlight Meetings Cleanroom Harness

Status: active Townlight Meetings productization gate.

Current candidate instructions: 2026-11-02. Execution of the changed harness
remains pending; historical evidence does not certify this candidate.

Sprint: CC-1.

## Purpose

CC-1 proves Townlight Meetings can be built and verified from a clean container while
pinning the current upstream platform to the exact Core commit recorded in
`config/core-source.json`, rather than moving Core `main`. The installed
dependency is `townlight-core` 1.3.0.dev2, built from that source. The original
`v1.2.1` release is verified separately as historical provenance, never installed
or relabeled as the current dependency.

The harness is intentionally stricter than a normal CI run:

- the container base image is digest-pinned,
- Docker builds use `--no-cache --pull`,
- the target Townlight Meetings commit is fetched by SHA,
- the current Core wheel is built/installed only after its source commit,
  clean tracked tree and package metadata match the candidate pin,
- original historical Core freeze release assets are downloaded and checked with
  `sha256sum -c SHA256SUMS.txt`,
- `release-attestation.json` is verified with cosign against the exact
  Townlight Core release workflow identity,
- `scripts/verify-release-provenance.py v1.2.1 ...` verifies the
  release provenance contract,
- `scripts/check-townlight_core-placeholder-imports.py` preserves Meetings'
  existing no-new-dependency boundary for catalog, exemptions and scaffold.
  Those Core APIs are implemented; this gate does not claim they are empty or
  add a new Meetings consumer in a naming migration,
- `bash scripts/verify-release.sh` runs the full Townlight Meetings test apparatus, and
- the offline phase runs under `docker run --network none`.

The online phase mounts the host Docker socket into the cleanroom container so
`scripts/verify-release.sh` can run the disposable pgvector migration test
inside the full release apparatus. The mounted socket is used only during the
online verification phase; offline runtime proof still runs with `--network
none` and without the socket.

## Commands

Run from the Townlight Meetings repository root:

```bash
CLEANROOM_RUN_COUNT=2 bash scripts/run-townlight_meetings-cleanroom.sh
```

The host must expose a Docker socket at `/var/run/docker.sock`. If your Docker
socket lives somewhere else, set `CLEANROOM_DOCKER_SOCKET` before running the
harness.

The live Townlight Core provenance check uses GitHub's API through `gh api`. CI
passes `GITHUB_TOKEN` into the online cleanroom phase to avoid unauthenticated
rate limits. Local runs can set `GITHUB_TOKEN` or `GH_TOKEN`; token values are
not written to the evidence manifests.

To target a specific commit and output directory:

```bash
CLEANROOM_RUN_COUNT=2 bash scripts/run-townlight_meetings-cleanroom.sh \
  <commit-sha> \
  docs/evidence/cc1-townlight_meetings-cleanroom-<short-sha>
```

## Evidence Shape

Each run directory contains:

- `cleanroom-manifest.json` - stable cross-machine comparison surface,
- `cleanroom-manifest.sha256` - checksum for the stable manifest,
- `cleanroom-manifest.json.sig` - local signature over the stable manifest,
- `evidence-signing-public.pem` - public key for the local signature,
- `timestamp-manifest.json` - run-specific timestamp/signature/bundle fields,
- `step-results.tsv` - pass/fail ledger for each command,
- `logs/` - command transcripts,
- `townlight_core-freeze-assets/` - downloaded upstream release assets,
- `files.sha256` - checksums for evidence files, and
- `cleanroom-evidence.tar.gz` with its checksum.

The orchestrator writes `comparison.json` and `summary.md` at the evidence
root. `cleanroom-manifest.json` must hash identically across runs. Timestamped
metadata, signatures, and compressed bundles are intentionally run-specific and
are documented by each run's `timestamp-manifest.json`.

## CI

`.github/workflows/cleanroom.yml` runs the same harness on pull requests that
touch the CC-1 harness, the Townlight Core pin, or the cleanroom documentation. The
workflow uploads the full evidence directory as a GitHub Actions artifact so an
outside reviewer can inspect the logs and manifests without relying on local
desktop state.

## Upstream Pin

The current dependency commit is
`3021821bf9a92c790a399ad12aed821d65b09105`, distribution `townlight-core`
1.3.0.dev2 and principal import `townlight_core`. The bootstrap rejects stale
or modified provider sources. Current package-index publication is not assumed.

The unchanged historical freeze release is:

- tag: `v1.2.1`,
- original package asset: `civiccore-1.2.1-py3-none-any.whl`,
- Sigstore identity:
  `https://github.com/CivicSuite/civiccore/.github/workflows/release.yml@refs/tags/v1.2.1`,
- OIDC issuer: `https://token.actions.githubusercontent.com`.

These original identifiers were confirmed against the actual release assets
and attestation. They identify historical evidence only. The historical package
version is1.2.1; its trust anchor is the original tag and release attestation.
