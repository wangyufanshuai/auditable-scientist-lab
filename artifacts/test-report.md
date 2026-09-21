# Acceptance test report

- Recorded: 2026-09-21
- Scope: T1 Hohmann offline vertical slice
- Scientific status: engineering and bounded reproduction evidence only

| Check | Command | Exit code | Result |
|---|---|---:|---|
| Contract, replay, CLI, adapter, policy, T2–T5 track tests | `python -m pytest -q` | 0 | 31 passed |
| Editable package install | `python -m pip install -e . --no-deps --no-build-isolation` | 0 | installed |
| Offline run | `python -m auditable_scientist.cli run examples/hohmann/run.json --offline --seed 17 --output-dir artifacts/acceptance-runs-v7` | 0 | run written |
| Replay | `python -m auditable_scientist.cli replay artifacts/acceptance-runs-v7/run-7a65020acaf83cfc` | 0 | 8 checks verified |
| Inspect | `python -m auditable_scientist.cli inspect artifacts/acceptance-runs-v7/run-7a65020acaf83cfc` | 0 | completed / reproduced |
| Portfolio verifier | `python scripts/verify_acceptance.py` | 0 | T1–T5 receipts verified |

The test process emits the existing `pytest-asyncio` configuration deprecation warning; this
project uses no async fixtures. The run's source and evidence files remain marked `unverified`
where local licensing or real-data rights are not established.
