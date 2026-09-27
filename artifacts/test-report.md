# Acceptance test report

- Recorded: 2026-09-27
- Scope: T1 Hohmann offline vertical slice
- Scientific status: engineering and bounded reproduction evidence only

| Check | Command | Exit code | Result |
|---|---|---:|---|
| Contract, replay, CLI, adapter, policy, T2–T5 track tests | `python -m pytest -q` | 0 | 63 passed in the project environment and a fresh virtual environment; includes source/evidence mutation, bounded-path, input-snapshot, and copied-checkout replay checks |
| Editable package install | `python -m pip install -e . --no-deps --no-build-isolation` | 0 | installed |
| Offline run | `python -m auditable_scientist.cli run examples/hohmann/run.json --offline --seed 17 --output-dir artifacts/acceptance-runs-v15` | 0 | snapshotted input and v2 manifest written |
| Replay | `python -m auditable_scientist.cli replay artifacts/acceptance-runs-v15/run-02a00f229aabd3d2` | 0 | 8 manifest checks and saved Run/event/output integrity verified |
| Inspect | `python -m auditable_scientist.cli inspect artifacts/acceptance-runs-v15/run-02a00f229aabd3d2` | 0 | completed / reproduced |
| Track CLI | `python -m auditable_scientist.cli run-track T2..T5 <fixture> --output-dir artifacts/track-runs-v6` | 0 | four policy-guarded runs and replays verified; T3 compares Velocity-Verlet, RK4, and the analytic solution |
| Fresh Python environment | `python -m venv <temp>`, `<temp>/Scripts/python -m pip install -e ".[test]"`, then `-m pytest -q` | 0 | 63 passed; the copied-checkout test generates runs inside that environment before relocation |
| Standalone wheel outside checkout | `python -m pip wheel . --no-deps`, force-reinstall in an isolated venv, then CLI `init/run/replay/inspect/export-report` and `init-track/run-track/replay` | 0 | [wheel-audit.json](wheel-audit.json) records five replay receipts, 15 packaged resources, and five successful moved-run replays |
| Copied checkout without original fixtures | `python scripts/verify_committed_relocation.py` | 0 | [relocation-audit.json](relocation-audit.json) records five successful replays and rejection of a tampered T3 snapshot |
| Portfolio verifier | `python scripts/verify_acceptance.py` | 0 | T1–T5 receipts and T2–T5 CLI runs verified |

The test process emits the existing `pytest-asyncio` configuration deprecation warning; this
project uses no async fixtures. The run's source and evidence files remain marked `unverified`
where local licensing or real-data rights are not established.
