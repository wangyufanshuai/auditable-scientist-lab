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

The optional [real projectile source inventory](../t2-projectile-source-audit.json) pins a 2025 article PDF and two supplementary workbooks without redistributing them. The measured workbook contains 179 samples from 30 trials, while the article reports 82 experiments. Fifteen trial IDs have a declared `v0` above the article's stated launcher range; the column's meaning is unresolved. Official supplement rights language is reviewed, but raw-XLSX redistribution remains unconfirmed. Coverage, physical-model comparison, trial-level holdout, and causal identification remain open. The [blocked model protocol](../docs/T2_PROJECTILE_MODEL_PROTOCOL.md) freezes a whole-trial split but permits no fit. The Claim is `unverified`.

The optional [projectile source reconciliation receipt](../t2-projectile-source-reconciliation-audit.json) binds the 82-experiment article statement to the 30-trial/179-row intake, records 52 experiments unaccounted for by this intake, preserves the unresolved `v0` role and workbook local-path metadata as provenance-only signals, and keeps rights, model, causal, holdout, research-candidate, and publication claims blocked. Its negative controls reject coverage spoofing, forced `v0` resolution, hash tampering, ignored cross-split duplicates, and rights promotion.
