# P4 Hohmann vertical slice checkpoint

- Status: `implementing`
- Date: 2026-09-20
- Run: `artifacts/p4-runs/run-7a65020acaf83cfc`
- Scientific status: validated reproduction within a committed analytic fixture; not real-data
  validation, new-physics discovery, production readiness, or publication evidence.

## Closed in this checkpoint

- `init` creates a versioned Hohmann configuration.
- `run --offline --seed 17` loads the committed nine-case dataset, evaluates a fixed five-item
  candidate catalog, ranks only on train residuals, and applies the holdout threshold afterwards.
- The selected `tof-hohmann-v1` candidate passed dimensional analysis and a fixed holdout RMSE
  gate of `1e-8` days; observed holdout RMSE was `2.61520914399e-13` days.
- The Run contains observations, evidence references, a claim transition, and a four-event hash
  chain. The evidence files are marked `unverified` because byte-level replay does not prove
  licensing or real-data provenance.
- `replay` compares the input hash, source and evidence snapshots, candidate ordering, and full
  computational output. `inspect` and `export-report` expose the result without network access.

## Commands

| Command | Result |
|---|---|
| `python -m pytest -q` | 17 passed |
| `python -m pip install -e . --no-deps --no-build-isolation` | exit 0 |
| `python -m auditable_scientist.cli run examples/hohmann/run.json --offline --seed 17 --output-dir artifacts/p4-runs` | exit 0 |
| `python -m auditable_scientist.cli replay artifacts/p4-runs/run-7a65020acaf83cfc` | verified, five replay checks |

## Remaining gate

P4 does not close the external symbolic engine, real-data rights, an independent numerical
backend, or any of the T2–T5 domain slices. P5 must formalize adapter manifests and the blocked
provider interface; P6 must add the minimal policy/agent boundary before the final acceptance
package.
