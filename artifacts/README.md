# Evidence artifacts

The acceptance package is maintained here as bounded local evidence:

- `acceptance.json` — command receipts with exit code, timestamp, input/version,
  and result path, plus explicit scope and remaining scientific gates.
- `test-report.md` — unit, contract, replay, and failure-path results.
- `demo-transcript.md` — a bounded offline CLI transcript.
- `sample-run.json` — a complete replayable Run with claims and evidence refs.

The current T1 package is `acceptance.json`, `test-report.md`, `demo-transcript.md`, and
`sample-run.json`; T2–T5 have the same four files in their track-specific subdirectories.
`acceptance-runs-v18/` holds the current T1 CLI Run, and `track-runs-v14/` holds one
policy-guarded CLI Run per bounded T2–T5 fixture plus the T2P and T3N subtracks. Each runtime bundle includes a replay
manifest, snapshotted input, JSONL event log, and deterministic report. The v2 manifests
use bounded `run://` and `root://` references. A copied checkout replays in the recorded
environment; changing dependency versions remains a fail-closed condition.
The current T4 package uses exact decimal transfer witnesses and requires all five
declared obligations; earlier v5–v7 packages are historical and are not current replay evidence.
The separate `t3-external-runs/` package records the pinned optional SciPy
Tool/Provider Run, its license snapshots, replay and mutation controls. The core
T3 Run does not require SciPy.
`t3-nbody/` records the dimensionless equilateral three-body benchmark. Its analytic orbit, local RK4 cross-check, and repulsive-force negative control only support this symmetric fixture; perturbed motion and real missions remain open gates.
`t3-perturbed-audit.json` records a pinned-SciPy check of two short, synthetic velocity perturbations. `t3-perturbed-runs/` and `t3-perturbed-run-audit.json` bind the same grid to an optional replayable Tool/Provider Run with moved-run and mutation controls. It is separate from the core T3N Run and cannot support long-horizon, chaotic, or mission accuracy.
`t2-physical/` records 100 synthetic ball-and-floor interventions and a complete paired counterfactual example. Its evidence concerns only the declared simulator; real interventions, causal identification, and external algorithm rights remain open gates.
`wheel-audit.json` records installation and CLI replay from a temporary wheel-only environment.
`symbolic-engine-audit.json` is a read-only observation of a newly located local source directory; it binds file hashes and preserves the blocked external-provider gate without importing its code.
These artifacts do not establish real-data validity, publication readiness, or scientific novelty.
