# T2 context-leakage sensitivity audit

The bounded T2 fixture declares an intervention outcome as a function of
`do(intervention_value)` and intentionally includes unrelated context values.
The sensitivity evaluator keeps the baseline candidate and evaluates a fixed
negative candidate that adds `context_value` to the prediction. The baseline
must pass the holdout RMSE gate while the context-leaking candidate must fail it.

Run the receipt with:

```powershell
python scripts/verify_t2_causal_sensitivity.py --verify
```

The receipt commits both candidate IDs, the candidate-set hash, train/holdout
metrics, source hashes, and fail-closed boundaries. This is a semantic negative
control over a synthetic fixture. It does not establish exchangeability,
causal identification, real intervention effects, source rights, or a research
candidate claim.
