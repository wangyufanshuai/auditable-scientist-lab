# T4 proof-carrying simulation checkpoint

- Evaluator: `proof-carrying-simulation-v1`
- Status: `validated-reproduction` for finite machine-checkable obligations
- Positive gate: mass conservation, nonnegative state, and trajectory hash verified
- Negative gate: tampered trajectory leaves the claim `blocked`

The package couples a trajectory to explicit checker IDs and a hash. It is not a formal theorem
prover or a claim of mathematical completeness; that backend remains an open gate.
