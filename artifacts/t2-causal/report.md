# T2 causal physical world checkpoint

- Evaluator: `causal-intervention-v1`
- Status: `validated-reproduction` within a deterministic structural fixture
- Positive gate: `passed`
- Negative gate: wrong intervention coefficient rejected

The evaluator applies `do(x=value)` and checks that an unrelated context value does not change
the predicted outcome. This demonstrates intervention semantics in a finite offline fixture; it
does not identify a causal effect from real observations or establish a physical-world claim.

Open gates: real interventions, confounding assumptions, data rights, and human review.
