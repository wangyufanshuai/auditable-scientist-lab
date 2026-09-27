# T3 published figure-eight finite-horizon result

The [protocol](T3_FIGURE_EIGHT_PROTOCOL.json) was committed locally at
`4a75872` before integrating its endpoints; its SHA-256 is
`7828754b52af988780a5e4679b017ff5c20d1aa490cc9720d250b1e719643a3d`.
The input is Carles Simó's rounded decimal state printed in Figure 1 of
[Chenciner and Montgomery (2000)](https://doi.org/10.2307/2661357).
The source PDF, pinned SciPy/NumPy environment, method, source-code hashes,
three outputs, gates, and scientific boundaries are bound in the
[audit](../artifacts/t3-figure-eight-audit.json). The PDF and dependency wheels
are not redistributed.

| Case | Horizon | Fine RK4 vs DOP853 position error | Velocity error | Coarse/fine error ratio | DOP853 sampled minimum separation |
|---|---:|---:|---:|---:|---:|
| Published state | 1 approximate period | 2.05e-12 | 5.92e-12 | 89.4 | 0.691 |
| Published state | 10 approximate periods | 5.82e-10 | 6.01e-10 | 6.65 | 0.691 |
| Momentum-balanced velocity perturbation | 10 approximate periods | 7.41e-10 | 8.51e-10 | 4.91 | 0.680 |

All positions, velocities, and time units here are dimensionless. The
one-period DOP853 endpoint differs from the printed initial positions by
`4.10e-8`; ten-period closure is reported but is not an acceptance gate because
the paper's decimal state is approximate. The perturbed ten-period trajectory
is deliberately different from the printed orbit; its `0.319` closure distance
is not interpreted as a Lyapunov exponent or chaos test. The repulsive-gravity
negative control differs from the attractive quarter-period endpoint by
`2.56` position units.

No inward crossing of the `0.25` pair-separation event was observed. The
maximum sampled fine-RK4 relative energy drift across the three cases is
`1.06e-12`. The pinned run used 52,489 DOP853 right-hand-side calls and
151,200 fixed RK4 steps, below the frozen 100,000 and 160,000 limits.
`python scripts/verify_t3_figure_eight.py --verify` dynamically recomputes the
receipt in the pinned environment. Core acceptance checks the committed
source fingerprints, endpoints, arithmetic, gates, budget, and boundaries
without importing SciPy; that static check alone does not rerun the solver.

This is bounded numerical reproduction of one special, published planar
three-body family. It supplies a more demanding finite-horizon comparison
than the earlier equilateral fixture, but does not establish chaotic-regime
accuracy, general N-body validity, an untouched scientific holdout, rights to
redistribute the source PDF, or a real-mission comparison. The Claim remains
`unverified` and those gates remain open.
