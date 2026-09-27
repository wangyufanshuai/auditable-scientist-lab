# T3 evaluator test report

The optional expanded [finite-horizon audit](../t3-horizon-grid-audit.json) admits two preflight-selected 0.75-period synthetic trajectories under a 12,000 DOP853-call and 35,000 fixed-step budget. Both one-period stress cases cross the $0.5a$ close-approach threshold and are excluded from accuracy claims. Pinned SciPy `python scripts/verify_t3_horizon_grid.py --verify` recomputes the numerical receipt; core acceptance verifies its saved source bytes, scope, budget, and gates without importing SciPy. The inherited fixture `holdout` label is not untouched scientific validation.

- Command: `python scripts/verify_acceptance.py`
- Result: independently replayed by the portfolio verifier
- Evidence level: bounded local fixture
- Real-data claim: false
- Research-candidate claim: false
