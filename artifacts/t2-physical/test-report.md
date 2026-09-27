# T2P evaluator test report

- Command: `python scripts/verify_acceptance.py`
- Result: independently replayed by the portfolio verifier
- Evidence level: bounded local fixture
- Real-data claim: false
- Research-candidate claim: false

An optional impact-to-impact endpoint estimator independently recomputes 124
synthetic factual and intervened horizontal outcomes, including 24 varied
holdout states. The 84-case holdout effect RMSE is approximately 8.7e-16 m;
an ignored-intervention estimator has approximately 0.266 m RMSE. This checks
only the declared simulator and does not establish real causal identification.

The optional `python scripts/verify_t2_independent_run.py --verify` checks a
shared Tool/Policy/Provider Run with both fixture snapshots, source and environment
fingerprints, one tool call, moved replay, mutation controls, and policy denials.
Its real-world Claim remains `unverified`.
