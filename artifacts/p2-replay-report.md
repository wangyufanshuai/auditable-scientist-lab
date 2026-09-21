# P2 replay checkpoint

- Status: `implementing`
- Date: 2026-09-20
- Scope: canonical serialization, append-only EventLog, environment receipt, and
  ReplayManifest verification
- Scientific status: no scientific claim; this is engineering evidence only

## Implemented

- Stable UTF-8 JSON serialization with sorted keys and SHA-256 hashing.
- JSONL append-only EventLog with contiguous sequence numbers, `genesis` anchor,
  previous-payload hash, and fail-closed payload verification.
- ReplayManifest with input hash, code revision, seed, environment, source/evidence
  fingerprints, candidate ordering, and computational output.
- Explicit `ReplayMismatch` failures for changed inputs, source files, evidence files,
  candidate ordering, or computational output.
- Environment capture limited to runtime identifiers and declared package versions.

## Commands

| Command | Result |
|---|---|
| `python -m pytest -q` | 11 passed |
| `python -m pip install -e . --no-deps --no-build-isolation` | exit 0 |

The test process emitted an existing `pytest-asyncio` configuration deprecation warning;
no async fixtures are used by this project.

## Failure-path coverage

- edited event payload;
- append after a tampered log;
- changed source snapshot;
- changed input payload;
- changed computational output;
- changed candidate ordering.

## Remaining gate

P2 has not yet wired a Hohmann numerical run, holdout evaluation, or CLI. The next gate
is P3 deterministic tools, followed by the P4 vertical slice.
