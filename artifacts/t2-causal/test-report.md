# T2 evaluator test report

- Command: `python scripts/verify_acceptance.py`
- Result: independently replayed by the portfolio verifier
- Evidence level: bounded local fixture
- Real-data claim: false
- Research-candidate claim: false

The optional [context-sensitivity negative control](../t2-causal-sensitivity-audit.json) keeps the declared synthetic outcome dependent on `do(intervention_value)` only and rejects a fixed candidate that leaks `context_value` on holdout. This is a semantic control for the fixture, not causal identification, exchangeability, real intervention evidence, source-rights review, or a research-candidate claim.
