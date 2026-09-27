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
| Track CLI | `python -m auditable_scientist.cli run-track T2..T5 <fixture> --output-dir artifacts/track-runs-v7` | 0 | four policy-guarded runs and replays verified; T3 compares Velocity-Verlet, RK4, and the analytic solution |
| T4 exact transfer witness | `python -m pytest tests/test_tracks.py -q -o addopts=''`; `python scripts/verify_acceptance.py` | 0 | all five obligations required; recomputed-hash tiny and large-magnitude mass changes, wrong transfer, missing and duplicate checker fail; current T4 Run replays |
| Fresh Python environment | `python -m venv <temp>`, `<temp>/Scripts/python -m pip install -e ".[test]"`, then `-m pytest -q` | 0 | 63 passed; the copied-checkout test generates runs inside that environment before relocation |
| Pinned fresh replay environment | `python -m venv <temp>`; `<temp>/Scripts/python -m pip install -e ".[test]" -c requirements-replay-win-py312.txt`; `-m pip check`; `scripts/verify_replay_environment.py`; `-m pytest -q -o addopts=''`; `scripts/verify_acceptance.py` | 0 | exact Windows AMD64 / CPython 3.12.3 dependency closure matched; 63 tests passed; all five committed manifests replayed |
| T3 bounded grid | `python scripts/verify_t3_sweep.py --write`, then `--verify` | 0 | 27 oscillator evaluations passed six predeclared convergence, accuracy, drift, agreement, and Euler negative gates |
| Optional T3 SciPy DOP853 | install exact SciPy/NumPy wheel hashes from `requirements-t3-scipy-win-py312.txt`; `python scripts/verify_t3_external_scipy.py --write`, then `--verify` | 0 | nine oscillator cases and wrong-sign negative control passed in a separate environment; remains outside core Run evidence |
| Standalone wheel outside checkout | `python scripts/verify_wheel_install.py` | 0 | [wheel-audit.json](wheel-audit.json) records a current source fingerprint, wheel SHA-256, 16 packaged resources, five CLI replays, and five successful moved-run replays |
| Copied checkout without original fixtures | `python scripts/verify_committed_relocation.py` | 0 | [relocation-audit.json](relocation-audit.json) records five successful replays and rejection of a tampered T3 snapshot |
| Portfolio verifier | `python scripts/verify_acceptance.py` | 0 | T1–T5 receipts and T2–T5 CLI runs verified |

The test process emits the existing `pytest-asyncio` configuration deprecation warning; this
project uses no async fixtures. The run's source and evidence files remain marked `unverified`
where local licensing or real-data rights are not established.
Version constraints do not pin downloaded wheel bytes or interpreter bytes; this is a
same-platform replay result, not a cross-platform reproducibility claim.
