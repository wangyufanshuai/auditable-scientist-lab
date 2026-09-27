# Evidence artifacts

The acceptance package is maintained here as bounded local evidence:

- `acceptance.json` — command receipts with exit code, timestamp, input/version,
  and result path, plus explicit scope and remaining scientific gates.
- `test-report.md` — unit, contract, replay, and failure-path results.
- `demo-transcript.md` — a bounded offline CLI transcript.
- `sample-run.json` — a complete replayable Run with claims and evidence refs.

The current T1 package is `acceptance.json`, `test-report.md`, `demo-transcript.md`, and
`sample-run.json`; T2–T5 have the same four files in their track-specific subdirectories.
`acceptance-runs-v18/` holds the historical T1 CLI Run, `t1-combined-runs-v3/`
holds the combined analytic/RK4 T1 Run, and `track-runs-v16/` holds one
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
`t1-combined-cli-audit-v4.json` records the versioned console and package-module router,
including historical source-bundle replay and tamper rejection.
`t1-de440s-ephemeris-snapshot.json` and its audit record two fixed-date NAIF
DE440s geometry comparisons. The optional kernel is ignored by Git; the saved
snapshot is not a spacecraft trajectory or independent mission validation.
`t1-de440s-run-audit.json` binds that small snapshot to an offline Tool/Policy/
Provider Run with moved replay and mutation controls. Run replay recomputes
geometry from saved states; it does not rerun the NAIF kernel.
`t1-mars-center-ephemeris-snapshot.json` and its audit add a checksum-verified
MAR099s mass-center offset to the DE440s planetary states. This supplies a
Mars-center geometry diagnostic, not a spacecraft encounter or mission proof.
`t1-maven-source-snapshot.json` and its audit read three exploratory states
from a PDS4-archived, checksum-pinned reconstructed MAVEN cruise SPK. They
record its Sun/Mars-barycenter segment transition and the Mars-center chain,
but that source audit alone does not establish spacecraft propagation or mission validity.
`t1-maven-preflight-snapshot.json` and its audit add two precommitted 24-hour
Sun-only RK4 comparisons with NAV endpoints. They bind a pure-Python solver,
step refinement, two-body energy, wrong-sign negative and measured errors to
the fixed protocol; mission-domain dynamics and scientific validation stay open.
`t1-maven-preflight-run-audit.json` binds that saved comparison to a single
offline Tool/Policy/Provider Run, with portable replay and tamper/policy
controls. Replay does not access the original SPK binaries.
`t1-maven-planetary-force-snapshot.json` and its audit bind a separately
precommitted Sun-plus-Earth-Moon/Mars-barycenter tide diagnostic to the same
two previously inspected NAV arcs. The dynamic check needs four pinned local
NAIF files; the committed snapshot is statically checked in core acceptance.
It is not a maneuver reconstruction or scientific holdout.
`symbolic-engine-audit.json` is a read-only observation of a newly located local source directory; it binds file hashes and preserves the blocked external-provider gate without importing its code.
The DE440s snapshot is source-tracked ephemeris-model data for two fixed-date
geometry comparisons. None of these artifacts establishes real-mission validity,
publication readiness, or scientific novelty.
