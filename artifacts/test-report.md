# Acceptance test report

- Recorded: 2026-09-27
- Scope: T1 Hohmann offline vertical slice
- Scientific status: engineering and bounded reproduction evidence only

| Check | Command | Exit code | Result |
|---|---|---:|---|
| Contract, replay, CLI, adapter, policy, T2–T5 track tests | `python -m pytest -q` | 0 | 58 passed, including five T1 replay mutations, four T2 package mutations, bundled-resource/LF byte checks, four track replay tamper cases, and a failed-RK4 T3 gate |
| Editable package install | `python -m pip install -e . --no-deps --no-build-isolation` | 0 | installed |
| Offline run | `python -m auditable_scientist.cli run examples/hohmann/run.json --offline --seed 17 --output-dir artifacts/acceptance-runs-v14` | 0 | run written |
| Replay | `python -m auditable_scientist.cli replay artifacts/acceptance-runs-v14/run-7a65020acaf83cfc` | 0 | 8 manifest checks and saved Run/event/output integrity verified |
| Inspect | `python -m auditable_scientist.cli inspect artifacts/acceptance-runs-v14/run-7a65020acaf83cfc` | 0 | completed / reproduced |
| Track CLI | `python -m auditable_scientist.cli run-track T2..T5 <fixture> --output-dir artifacts/track-runs-v5` | 0 | four policy-guarded runs and replays verified; T3 compares Velocity-Verlet, RK4, and the analytic solution |
| Fresh Python environment | `python -m venv <temp>`, `<temp>/Scripts/python -m pip install -e ".[test]"`, then `-m pytest -q` | 0 | 58 passed; T1 and T2–T5 fresh runs replayed with their own environment snapshots |
| Standalone wheel outside checkout | `python -m pip wheel . --no-deps`, force-reinstall in an isolated venv, then CLI `init/run/replay/inspect/export-report` and `init-track/run-track/replay` | 0 | [wheel-audit.json](wheel-audit.json) records five replay receipts, 15 packaged resources, and the T3 method document |
| Portfolio verifier | `python scripts/verify_acceptance.py` | 0 | T1–T5 receipts and T2–T5 CLI runs verified |

The test process emits the existing `pytest-asyncio` configuration deprecation warning; this
project uses no async fixtures. The run's source and evidence files remain marked `unverified`
where local licensing or real-data rights are not established.
