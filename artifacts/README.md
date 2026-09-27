# Evidence artifacts

The acceptance package is maintained here as bounded local evidence:

- `acceptance.json` — command receipts with exit code, timestamp, input/version,
  and result path, plus explicit scope and remaining scientific gates.
- `test-report.md` — unit, contract, replay, and failure-path results.
- `demo-transcript.md` — a bounded offline CLI transcript.
- `sample-run.json` — a complete replayable Run with claims and evidence refs.

The current T1 package is `acceptance.json`, `test-report.md`, `demo-transcript.md`, and
`sample-run.json`; T2–T5 have the same four files in their track-specific subdirectories.
`acceptance-runs-v15/` holds the current T1 CLI Run, and `track-runs-v8/` holds one
policy-guarded CLI Run per bounded T2–T5 fixture. Each runtime bundle includes a replay
manifest, snapshotted input, JSONL event log, and deterministic report. The v2 manifests
use bounded `run://` and `root://` references. A copied checkout replays in the recorded
environment; changing dependency versions remains a fail-closed condition.
The current T4 package uses exact decimal transfer witnesses and requires all five
declared obligations; earlier v5–v7 packages are historical and are not current replay evidence.
The separate `t3-external-runs/` package records the pinned optional SciPy
Tool/Provider Run, its license snapshots, replay and mutation controls. The core
T3 Run does not require SciPy.
`wheel-audit.json` records installation and CLI replay from a temporary wheel-only environment.
These artifacts do not establish real-data validity, publication readiness, or scientific novelty.
