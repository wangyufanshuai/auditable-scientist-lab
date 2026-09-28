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

The optional [real projectile source inventory](../t2-projectile-source-audit.json) pins a 2025 article PDF and two supplementary workbooks without redistributing them. The measured workbook contains 179 samples from 30 trials, while the article reports 82 experiments. Fifteen trial IDs have a declared `v0` above the article's stated launcher range; the column's meaning is unresolved. Supplement reuse rights, coverage, physical-model comparison, trial-level holdout, and causal identification remain open. The Claim is `unverified`.
