# T3 evaluator test report

The optional expanded [finite-horizon audit](../t3-horizon-grid-audit.json) admits two preflight-selected 0.75-period synthetic trajectories under a 12,000 DOP853-call and 35,000 fixed-step budget. Both one-period stress cases cross the $0.5a$ close-approach threshold and are excluded from accuracy claims. Pinned SciPy `python scripts/verify_t3_horizon_grid.py --verify` recomputes the numerical receipt; core acceptance verifies its saved source bytes, scope, budget, and gates without importing SciPy. The inherited fixture `holdout` label is not untouched scientific validation.

The optional [published figure-eight audit](../t3-figure-eight-audit.json) dynamically checks one and ten approximate periods and a momentum-balanced ten-period perturbation in the pinned SciPy environment. Fixed-step Cartesian RK4 agrees with DOP853 at all three endpoints, and no pair crosses the predeclared separation event. Core acceptance checks the saved source, arithmetic and boundaries; it does not import SciPy. This special published orbit does not close chaotic-regime, scientific-holdout, general-N-body, or mission gates.

- Command: `python scripts/verify_acceptance.py`
- Result: independently replayed by the portfolio verifier
- Evidence level: bounded local fixture
- Real-data claim: false
- Research-candidate claim: false

The optional [Pythagorean close-encounter audit](../t3-pythagorean-audit.json) compares a published 3–4–5 three-body state and one authored perturbation with pinned DOP853 and independently implemented adaptive RK4. Both stop at the predeclared 0.001 pair-separation guard near t=15.8299. All 12 finite engineering checks pass within budget; no post-guard orbit, Lyapunov estimate, untouched scientific holdout, or mission validation is claimed. Pinned SciPy `python scripts/verify_t3_pythagorean.py --verify` recomputes the receipt; core acceptance checks saved arithmetic and scope.
