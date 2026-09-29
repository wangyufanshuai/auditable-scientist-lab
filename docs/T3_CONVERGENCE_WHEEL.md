# T3 package convergence evaluator

The T3 convergence evaluator is the installable replay boundary for the
bounded harmonic-dynamics sweep. It runs 27 dimensionless unit-mass cases over
three frequencies, three initial states, and three step sizes. The receipt
checks the expected second-order Verlet and fourth-order RK4 refinement,
fine-grid position and energy error, backend agreement, and explicit-Euler
energy growth as a negative control.

The evaluator is available from the package after wheel installation:

```python
from auditable_scientist.tracks.convergence import build_receipt
receipt = build_receipt()
assert receipt["passed"]
```

`python scripts/verify_t3_sweep.py --verify` verifies the committed receipt
against that same package implementation. The wheel replay runs the evaluator
outside the checkout, so a passing result does not depend on the repository's
`scripts/` directory.

This remains finite synthetic oscillator evidence. It does not establish
long-horizon chaotic accuracy, general multi-body validity, mission validity,
real-data validity, or publication readiness.
