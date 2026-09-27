# T3 Pythagorean close-encounter result

The [protocol](T3_PYTHAGOREAN_PROTOCOL.json) was committed locally at
`e74409e` before any project endpoint was computed. Its SHA-256 is
`f9848ae9fb01565f51d3560688a6e5cc30cfd09a274dba2d165bfa309de29927`.
The [audit](../artifacts/t3-pythagorean-audit.json) binds the source PDF hashes,
the pinned SciPy/NumPy environment, code hashes, comparison states, events,
invariants, negative control, and call counts. The source PDFs and package
wheels are not redistributed.

| Scenario | Largest normalized position difference at $t=1,5,10$ | Largest velocity difference | DOP853 guard time | Adaptive RK4 guard time |
|---|---:|---:|---:|---:|
| Published state | $1.70\times10^{-7}$ | $3.81\times10^{-6}$ | $15.8299133167$ | $15.8299140776$ |
| Authored $10^{-8}$ initial-$x$ perturbation | $1.70\times10^{-7}$ | $3.81\times10^{-6}$ | $15.8299133213$ | $15.8299140818$ |

Both methods stopped at an inward crossing of the predeclared `0.001`
separation between masses 4 and 5; no post-guard orbit is reported. The
published-state guard time differs by about $7.61\times10^{-7}$ time units
between methods and lies in the predeclared `14–17` window around the
historical close approach. Across both scenarios, the maximum sampled
relative energy drift was $6.53\times10^{-10}$ for DOP853 and
$6.95\times10^{-8}$ for adaptive RK4. The wrong-sign gravity control differed
from the attractive $t=1$ position by `0.128` after position normalization.
All 12 predeclared engineering checks passed. The run used 47,978 DOP853
right-hand-side calls, 83,544 independent RK4 calls, and 6,962 RK4 step
attempts, within the frozen 300,000, 1,200,000, and 120,000 limits.

The $10^{-8}$ perturbation changed the DOP853 position by only about
$1.86\times10^{-8}$ at $t=10$. We do not infer a Lyapunov exponent or even
observed exponential growth from these pre-guard samples. The source papers
discuss chaotic behavior over a longer trajectory, but this project's result
is a bounded, collision-monitored numerical comparison before that trajectory
reaches the chosen guard. A high-precision convergence study across the close
encounter, an untouched scientific holdout, and independent physical data
remain open. The scientific Claim stays `unverified`.

`python scripts/verify_t3_pythagorean.py --verify` dynamically recomputes the
audit in the pinned environment. Core acceptance checks source fingerprints,
saved arithmetic, guard conditions, budgets, and claim boundaries without
importing SciPy; that static check alone does not rerun the integration.
