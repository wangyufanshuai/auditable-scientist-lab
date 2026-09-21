# T3 physics dynamics checkpoint

- Evaluator: `harmonic-dynamics-v1`
- Solver: `velocity-verlet-v1`
- Status: `validated-reproduction` against a closed-form harmonic reference
- Positive gate: holdout position error and energy drift within thresholds
- Negative gate: explicit Euler conservation drift rejected

The parameter sweep is deterministic and replayable. It is a dynamics foundation slice, not
multi-body mission validation, hardware evidence, or production solver qualification.
