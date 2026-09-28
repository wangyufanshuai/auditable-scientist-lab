# T3 Pythagorean close-encounter protocol

The [machine-readable protocol](T3_PYTHAGOREAN_PROTOCOL.json) freezes a bounded
test of Burrau's Pythagorean three-body initial state before any project solver
endpoint is computed. The [2021 Physical Review D paper](https://doi.org/10.1103/PhysRevD.104.083020)
prints positions `(1, 3)`, `(-2, -1)`, `(1, -1)` for masses `3`, `4`, `5`, all
at rest. Here `G=1`, positions, velocities, masses, and time are dimensionless.
The initial energy is `-769/60`, the center of mass is at the origin, and all
three pair distances are the corresponding 3–4–5 triangle sides. These exact
inputs, not any later calculated endpoints, are taken from the source.

[Szebehely and Peters (1967)](https://articles.adsabs.harvard.edu/pdf/1967AJ.....72..876S)
describe repeated close approaches and report a particularly close encounter
near `t=15.830`. [Boekholt and Portegies Zwart (2015)](https://doi.org/10.1186/s40668-014-0005-3)
show why a double-precision energy check alone is insufficient to trust a
long chaotic trajectory. The two locally held source PDFs are fingerprinted in
the JSON protocol and excluded from Git; source rights do not authorize
redistribution. The 2015 HTML article is contextual, not an endpoint oracle.

The primary comparisons are the states at `t=1, 5, 10` from a pinned DOP853
reference and a separately implemented adaptive Cartesian RK4 backend. Both
solvers monitor all three pair distances and terminate on an inward crossing
of `0.001` up to `t=20`; no softened force or continuation through collision
is permitted. A second trajectory changes only the lightest body's initial
`x` coordinate by `1e-8`. That perturbation is an authored stress case, not a
published initial condition. A repulsive-force run to `t=1` is the negative
control. The JSON fixes tolerances, errors, invariants, event matching,
sampling, and call budgets. Results that violate a bound fail visibly rather
than causing a retune of this protocol.

An engineering pass would mean that the two implementations agree on the
pre-event finite trajectory and the close-approach stopping event under this
particular budget. It cannot establish a reliable post-event orbit or a
Lyapunov exponent. The literature's classification of this system as chaotic
does not promote this project's Claim: high-precision long-time convergence,
an untouched scientific holdout, and independent physical observations remain
open, and the Claim remains `unverified`.
