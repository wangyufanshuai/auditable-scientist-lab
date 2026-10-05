# T2 projectile `v0` provenance diagnostic

The optional [diagnostic receipt](../artifacts/t2-projectile-v0-diagnostic-audit.json)
compares the workbook's declared `v0` values with a trajectory-only no-drag
estimate computed from each trial's $y(x)$ samples. All 30 trials and 179
samples are included. The estimate is within 0.1 m/s of the declared value for
28 trials and within 0.25 m/s for all 30.

This agreement is a provenance warning, not validation. The article says the
initial velocity was measured with a light gate and also treated as a fitted
parameter; the workbook header only says `v0 (m/s)`. The declared values exceed
the article's stated $v_0 < 6$ m/s operating bound in 15 trial IDs. The
trajectory-only comparison therefore cannot establish whether the column is an
independent light-gate input, a fitted value, or a processed copy. The diagnostic
does not admit a model fit, causal effect, scientific holdout, or Claim.

`python scripts/verify_t2_projectile_v0_diagnostic.py --verify` checks the
committed diagnostic without the excluded source files. When both local source
files are available, `--article-pdf` and `--measured-workbook` rerun the
comparison and require exact agreement with the receipt. The source files remain
outside Git and their rights and revision gates are unchanged.
