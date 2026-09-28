# T3 bounded numerical comparison

The fixture solves the unit-mass harmonic oscillator
`dx/dt = v`, `dv/dt = -omega^2*x` for declared `x0`, `v0`, `omega`, `dt`,
and `steps`. The primary fixed-step solver is Velocity-Verlet. A separate,
locally written classical four-slope RK4 implementation in
`src/auditable_scientist/tracks/reference_rk4.py` supplies a second numerical
trajectory. Both final positions are checked against
`x(t) = x0*cos(omega*t) + v0*sin(omega*t)/omega`; their position difference
and maximum observed energy drift are also gated. Explicit Euler remains the
required failing conservation control.

The RK4 formula follows Peter Young, [*Comparison of methods for integrating
the simple harmonic oscillator*](https://bpb-us-e1.wpmucdn.com/sites.ucsc.edu/dist/7/1905/files/2025/03/ode_solve.pdf),
Physics 115/242, equations (9a)–(9e), checked 2026-09-27. The source is cited
for the standard mathematical method; no external code or data was copied, and
the page's redistribution rights have not been established. The implementation
has no external solver dependency. The fixture and evaluator source bytes are
SHA-256 fingerprinted in each T3 receipt and run package.

Passing this comparison establishes only a bounded local reproduction of this
linear oscillator. It does not validate multi-body dynamics, long-horizon
conservation, real missions, numerical stability outside the declared grid,
or an external production solver. Those gates remain open.
