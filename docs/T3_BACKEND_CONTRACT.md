# T3 independent-backend contract

`T3_BACKEND_CONTRACT.json` is a small meta-audit for the finite, nonintegrable
T3 receipts already in the repository. It freezes the minimum engineering
evidence expected from a complex dynamics comparison:

- a named reference method and an independently implemented method;
- explicit error/conservation and negative-control checks;
- a finite compute ceiling with recorded usage below that ceiling;
- source paths whose recorded byte hashes still match the checkout; and
- an explicit `unverified` scientific boundary.

The contract is checked by `scripts/verify_t3_backend_contract.py`. It does not
rerun SciPy, certify chaotic trajectories, or turn agreement before a collision
guard into a general N-body result. The three receipts remain bounded to their
declared published or synthetic initial states and finite horizons. A failed
contract is a release-gate failure, even when an individual numerical receipt
is otherwise marked passed.

Run the dependency-free check from the repository root:

```powershell
python scripts/verify_t3_backend_contract.py --verify
```

The optional pinned SciPy environment is still required for fresh dynamic
recomputation of the underlying numerical receipts.
