# T2 projectile trial independence diagnostic

The optional [diagnostic receipt](../artifacts/t2-projectile-trial-independence-audit.json)
checks exact duplicate trial content before any model fit. It canonicalizes each
trial's time, position, angle, and declared speed columns, then compares the
resulting trial signatures with the frozen whole-trial split.

Trials 22 and 23 have identical six-row observation payloads. The current split
places 22 in holdout and 23 in training, so the duplicate crosses the split
boundary. This makes the current split unsafe as an independent scientific
holdout until the source identity and experiment provenance are reviewed.

This is a post-hoc source diagnostic. It does not deduplicate, remove, or alter
the local source, and it does not admit a model fit, causal effect, scientific
holdout, or Claim. The raw workbook remains outside Git because direct
redistribution rights are unconfirmed.

`python scripts/verify_t2_projectile_trial_independence.py --verify` checks the
committed receipt without the excluded workbook. Add
`--measured-workbook PATH` only when the pinned local source is available; the
dynamic check requires `openpyxl` 3.1.5.
