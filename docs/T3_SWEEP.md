# T3 bounded parameter and step-size sweep

This is an engineering check of the unit-mass linear oscillator
`x'' + omega^2*x = 0`. It does not extend the T3 claim to multi-body dynamics,
real missions, or an external production solver.

`scripts/verify_t3_sweep.py` fixes three positive frequencies (0.7, 1.0, 1.6),
three nonzero initial-position states, and 128/256/512 steps. All cases end at
the same dimensionless phase `omega*t = 7*pi/2`, so halving the step count's
inverse holds the physical problem fixed for each frequency and state. There
are 27 solver evaluations. Position errors are divided by
`sqrt(x0^2 + (v0/omega)^2)`; energy drift is divided by initial energy.

The acceptance gates require the two consecutive error-reduction ratios to
fall in [3.5, 4.5] for Velocity-Verlet and [12, 20] for fixed-step RK4. At
512 steps, normalized position error must stay below `1e-3` and `1e-6`
respectively, energy drift below `1e-3` and `1e-6`, and final-position
disagreement below `1e-3`. Explicit Euler must show at least `1e-2`
normalized energy drift for every fine-grid case. These thresholds are fixed
in the script and included in the audit artifact.

The [sweep audit](../artifacts/t3-sweep.json) records each case, ratios,
thresholds, solver source hashes, and six gate results. The observed
Velocity-Verlet ratio range is 4.0006–4.0049; RK4 is 15.7083–15.9921.
The largest fine-grid normalized position errors are 2.114e-4 and 1.949e-8.
The smallest fine-grid Euler energy drift is 0.2663. Recompute the saved
artifact with:

```powershell
python scripts/verify_t3_sweep.py --verify
```

The sweep uses the existing local Velocity-Verlet and RK4 implementations
plus the analytic oscillator solution. It demonstrates the expected order on
this declared grid. It does not establish stability over arbitrary horizons,
absolute physical units, observational fit, source rights for an external
solver, or independent scientific validation.
