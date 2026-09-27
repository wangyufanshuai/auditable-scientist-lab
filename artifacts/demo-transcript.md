# Auditable Scientist Lab — Hohmann vertical slice

- Run: `run-02a00f229aabd3d2`
- Status: `completed`
- Evidence level: `validated-reproduction` within a committed analytic fixture
- Network: disabled; all calculations are offline

## Question

Can a fixed ten-expression grammar select the heliocentric Hohmann transfer time-of-flight expression and pass a fixed holdout and dimensional gate?

## Candidate result

- Candidate: `tof-semimajor-pi-v2`
- Expression: `pi*sqrt(((r1+r2)/2)^3/mu)/86400`
- Dimensional status: `valid`
- Candidate-set hash: `5d5babed73810c5781dae3f4ae00093b9a4a7ffebd6ecec6925803ce2b34f4a0`
- Search scope: `hohmann-radius-factor-grammar-v2`, ten predeclared expressions
- Train RMSE (days): `2.81599719144e-13`
- Holdout RMSE (days): `2.61520914399e-13`
- Holdout threshold (days): `1e-08`
- Holdout gate: `True` (holdout RMSE is within threshold)

## Candidate ranking

| Candidate | Dimensional | Complexity | Train RMSE (days) | Holdout RMSE (days) |
|---|---|---:|---:|---:|
| `tof-semimajor-pi-v2` | `valid` | 6 | 2.816e-13 | 2.61521e-13 |
| `tof-geometric-pi-v2` | `valid` | 6 | 9.24472 | 10.4246 |
| `tof-sum-unit-v2` | `valid` | 4 | 26.0138 | 25.3626 |
| `tof-inner-pi-v2` | `valid` | 4 | 75.8786 | 83.4762 |
| `tof-outer-pi-v2` | `valid` | 4 | 84.8265 | 93.8634 |
| `tof-outer-unit-v2` | `valid` | 3 | 151.682 | 143.57 |
| `tof-semimajor-unit-v2` | `valid` | 5 | 177.896 | 173.443 |
| `tof-geometric-unit-v2` | `valid` | 5 | 180.554 | 176.76 |
| `tof-inner-unit-v2` | `valid` | 3 | 201.638 | 200.012 |
| `tof-sum-pi-v2` | `valid` | 5 | 477.152 | 465.208 |

## Boundaries

- The dataset is a local committed fixture derived from the project-05 analytic baseline; it is not a real-data validation.
- The selected formula reproduces the declared calculation within this input domain; this is not a novelty, production, or publication claim.
- The correct formula is already in the bounded grammar; this is not open-ended symbolic discovery.
- The external symbolic-physics-engine adapter remains blocked: its located entrypoint is a stub and scoped revision/license are absent.
- A separate DE440s snapshot compares two fixed dates against NAIF Mars-barycenter states. It is not part of this analytic Run and does not validate a spacecraft encounter or mission Claim.

## Replay

- Manifest verification: `True`
- Checks: `input_hash, code_revision, environment, seed, source_files, evidence_files, candidate_order, computational_output`
