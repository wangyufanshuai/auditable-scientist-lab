# P7 acceptance checkpoint

- Status: `implementing`
- Date: 2026-09-21
- Scope: T1 acceptance package plus T2–T5 bounded track portfolio

## Verified

- `artifacts/acceptance.json` records commands, exit codes, input versions, output paths, and
  scientific boundaries.
- The T1 Run now contains an append-only Event chain and a Trace bound to the Run ID and input
  hash. The replay manifest verifies input, source/evidence files, candidate order, and full
  computational output.
- `scripts/verify_acceptance.py` validates the Run, EventLog, ReplayManifest, all five track
  receipts, file-level SHA-256 evidence, independently replays T2–T5 evaluators, reconstructs
  their negative cases, and checks the T5 no-execution boundary.
- `artifacts/track-portfolio.json` lists T1, T2, T3, T4, and T5 in order. Each T2–T5 evaluator
  has a positive fixture, negative case, input hash, acceptance receipt, and open gates.

## Commands

| Command | Result |
|---|---|
| `python -m pytest -q` | 30 passed |
| `python scripts/generate_track_artifacts.py` | exit 0 |
| `python scripts/verify_acceptance.py` | exit 0; T1–T5 verified and T2–T5 evaluators replayed |
| `python -m pip install -e . --no-deps --no-build-isolation` | exit 0 |

This package is local and bounded. The remote repository has not been pushed, and unresolved
license, real-data, formal-proof, wet-lab, human-review, and publication gates remain explicit.
