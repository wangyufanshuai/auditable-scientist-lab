# Acceptance test report

- Recorded: 2026-09-27
- Scope: T1 Hohmann offline vertical slice
- Scientific status: engineering and bounded reproduction evidence only

| Check | Command | Exit code | Result |
|---|---|---:|---|
| Contract, replay, CLI, adapter, policy, T2–T5 track tests | `python -m pytest -q` | 0 | 50 passed, including five T1 replay mutations, four T2 package mutations, four track CLI runs, and four track replay tamper cases |
| Editable package install | `python -m pip install -e . --no-deps --no-build-isolation` | 0 | installed |
| Offline run | `python -m auditable_scientist.cli run examples/hohmann/run.json --offline --seed 17 --output-dir artifacts/acceptance-runs-v11` | 0 | run written |
| Replay | `python -m auditable_scientist.cli replay artifacts/acceptance-runs-v11/run-7a65020acaf83cfc` | 0 | 8 manifest checks and saved Run/event/output integrity verified |
| Inspect | `python -m auditable_scientist.cli inspect artifacts/acceptance-runs-v11/run-7a65020acaf83cfc` | 0 | completed / reproduced |
| Track CLI | `python -m auditable_scientist.cli run-track T2..T5 <fixture> --output-dir artifacts/track-runs-v1` | 0 | four policy-guarded runs and replays verified |
| Fresh Python environment | `python -m venv <temp>`, `<temp>/Scripts/python -m pip install -e ".[test]"`, then `-m pytest -q` | 0 | 50 passed; T1 and T2–T5 fresh runs replayed with their own environment snapshots |
| Portfolio verifier | `python scripts/verify_acceptance.py` | 0 | T1–T5 receipts and T2–T5 CLI runs verified |

The test process emits the existing `pytest-asyncio` configuration deprecation warning; this
project uses no async fixtures. The run's source and evidence files remain marked `unverified`
where local licensing or real-data rights are not established.
