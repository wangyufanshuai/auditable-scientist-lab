# Acceptance test report

- Recorded: 2026-09-27
- Scope: T1 Hohmann offline vertical slice
- Scientific status: engineering and bounded reproduction evidence only

| Check | Command | Exit code | Result |
|---|---|---:|---|
| Contract, replay, CLI, adapter, policy, T2–T5 and T2P/T3N tests | `python -m pytest -q -o addopts=''` | 0 | 77 passed in the pinned replay environment; includes 100 physical counterfactual scenarios, equilateral force identity, source/evidence mutation, bounded-path, and copied-checkout checks |
| T1 bounded symbolic grammar | `python -m pytest tests/test_symbolic_grammar.py -q -o addopts=''` | 0 | ten expressions enumerated; candidate evaluators do not call the reference baseline; changing only holdout targets leaves training selection unchanged and fails the holdout gate |
| Editable package install | `python -m pip install -e . --no-deps --no-build-isolation` | 0 | installed |
| Offline run | `python -m auditable_scientist.cli run examples/hohmann/run.json --offline --seed 17 --output-dir artifacts/acceptance-runs-v18` | 0 | snapshotted input and v2 manifest written |
| Replay | `python -m auditable_scientist.cli replay artifacts/acceptance-runs-v18/run-02a00f229aabd3d2` | 0 | 8 manifest checks and saved Run/event/output integrity verified |
| Inspect | `python -m auditable_scientist.cli inspect artifacts/acceptance-runs-v18/run-02a00f229aabd3d2` | 0 | completed / reproduced |
| Track CLI | `python -m auditable_scientist.cli run-track <track> <fixture> --output-dir artifacts/track-runs-v14` | 0 | six policy-guarded T2–T5/T2P/T3N runs and replays verified; the five root tracks remain distinct |
| T4 exact transfer witness | `python -m pytest tests/test_tracks.py -q -o addopts=''`; `python scripts/verify_acceptance.py` | 0 | all five obligations required; recomputed-hash tiny and large-magnitude mass changes, wrong transfer, missing and duplicate checker fail; current T4 Run replays |
| Fresh Python environment | `python -m venv <temp>`, `<temp>/Scripts/python -m pip install -e ".[test]"`, then `-m pytest -q` | 0 | 63 passed; the copied-checkout test generates runs inside that environment before relocation |
| Pinned replay environment | `scripts/verify_replay_environment.py`; `-m pytest -q -o addopts=''`; `scripts/verify_acceptance.py` | 0 | exact Windows AMD64 / CPython 3.12.3 dependency closure matched; 77 tests passed; seven current manifests replayed |
| T2P planar physical counterfactuals | `python -m auditable_scientist.cli run-track T2P examples/causal/physical-fixture.json --output-dir artifacts/track-runs-v14`; `python scripts/verify_acceptance.py` | 0 | 100 fixed scenarios and a full joint-counterfactual example passed; ignoring intervention failed the holdout; only simulator-internal effects are supported |
| T3 bounded grid | `python scripts/verify_t3_sweep.py --write`, then `--verify` | 0 | 27 oscillator evaluations passed six predeclared convergence, accuracy, drift, agreement, and Euler negative gates |
| T3N symmetric three-body subtrack | `python -m auditable_scientist.cli run-track T3N examples/dynamics/nbody-fixture.json --output-dir artifacts/track-runs-v14`; `python scripts/verify_acceptance.py` | 0 | equal-mass training and unequal-mass holdout orbits passed analytic and independent RK4 comparisons; repulsive-force negative control rejected; general perturbed and real-mission gates remain open |
| Optional T3 finite-horizon perturbations | pinned SciPy `python scripts/verify_t3_perturbed.py --write`, then `--verify` | 0 | two synthetic, momentum-balanced perturbations passed Verlet refinement, RK4/DOP853 agreement, invariant, separation, and repulsive-force negative gates; separate from core T3N Run and long-horizon validity |
| Optional T3 perturbed Tool/Provider Run | pinned SciPy `python scripts/verify_t3_perturbed_run.py --write`, then `--verify` | 0 | [t3-perturbed-run-audit.json](t3-perturbed-run-audit.json) binds the two cases to a policy-guarded shared Run, eight replay checks, moved replay, result/license mutation rejection, and policy denials; claim remains unverified |
| Optional T3 SciPy DOP853 | install exact SciPy/NumPy wheel hashes from `requirements-t3-scipy-win-py312.txt`; `python scripts/verify_t3_external_scipy.py --write`, then `--verify` | 0 | nine oscillator cases and wrong-sign negative control passed in a separate environment; remains outside core Run evidence |
| Optional T3 SciPy Tool/Provider Run | `python scripts/verify_t3_external_run.py --write`, then `--verify` in the pinned SciPy environment | 0 | [t3-external-run-audit.json](t3-external-run-audit.json) binds a versioned provider, policy, licenses and source; eight replay checks, moved replay, output/license mutations and policy denials pass |
| Standalone wheel outside checkout | `python scripts/verify_wheel_install.py` | 0 | [wheel-audit.json](wheel-audit.json) records a current source fingerprint, wheel SHA-256, 23 packaged resources, seven CLI replays, and seven successful moved-run replays |
| Copied checkout without original fixtures | `python scripts/verify_committed_relocation.py` | 0 | [relocation-audit.json](relocation-audit.json) records seven successful replays and rejection of a tampered T3 snapshot |
| Portfolio verifier | `python scripts/verify_acceptance.py` | 0 | T1–T5 receipts plus T2P/T3N and all seven CLI runs verified |
| Optional symbolic-provider source audit | `python scripts/audit_symbolic_engine.py` | 0 | [symbolic-engine-audit.json](symbolic-engine-audit.json) records the discovered local path and file hashes; the entrypoint is a stub, the directory is untracked and has no scoped license, so integration remains blocked |

The test process emits the existing `pytest-asyncio` configuration deprecation warning; this
project uses no async fixtures. The run's source and evidence files remain marked `unverified`
where local licensing or real-data rights are not established.
Version constraints do not pin downloaded wheel bytes or interpreter bytes; this is a
same-platform replay result, not a cross-platform reproducibility claim.
