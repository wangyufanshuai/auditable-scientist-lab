# Auditable Scientist Lab — Hohmann vertical slice

- Run: `run-7a65020acaf83cfc`
- Status: `completed`
- Evidence level: `validated-reproduction` within a committed analytic fixture
- Network: disabled; all calculations are offline

## Question

Can a bounded candidate search recover the heliocentric Hohmann transfer time-of-flight expression and pass a fixed holdout and dimensional gate?

## Candidate result

- Candidate: `tof-hohmann-v1`
- Expression: `pi*sqrt(((r1+r2)/2)^3/mu)/86400`
- Dimensional status: `valid`
- Candidate-set hash: `a99ed081f76b29cbf8a14255b2cae3181cdac59d225e28765842464bdfac4b85`
- Train RMSE (days): `2.81599719144e-13`
- Holdout RMSE (days): `2.61520914399e-13`
- Holdout threshold (days): `1e-08`
- Holdout gate: `True` (holdout RMSE is within threshold)

## Candidate ranking

| Candidate | Dimensional | Complexity | Train RMSE (days) | Holdout RMSE (days) |
|---|---|---:|---:|---:|
| `tof-hohmann-v1` | `valid` | 5 | 2.816e-13 | 2.61521e-13 |
| `tof-inner-orbit-v1` | `valid` | 3 | 75.8786 | 83.4762 |
| `tof-outer-orbit-v1` | `valid` | 3 | 84.8265 | 93.8634 |
| `tof-missing-pi-v1` | `valid` | 4 | 177.896 | 173.443 |
| `tof-radius-sum-v1` | `valid` | 4 | 477.152 | 465.208 |

## Boundaries

- The dataset is a local committed fixture derived from the project-05 analytic baseline; it is not a real-data validation.
- The selected formula reproduces the declared calculation within this input domain; this is not a novelty, production, or publication claim.
- The external symbolic-physics-engine adapter remains blocked pending a path, revision, and license.

## Replay

- Manifest verification: `pending`
- Checks: `run replay command`
