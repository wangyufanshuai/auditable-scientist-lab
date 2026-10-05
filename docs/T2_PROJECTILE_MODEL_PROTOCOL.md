# T2 projectile trajectory model protocol

This is a local, blocked protocol draft for a future trial-level comparison of
the no-drag and spherical-drag projectile models. It is not an external
preregistration and it has no fitted result. The source intake found real
position/time measurements, but the supplementary workbook does not say whether
its `v0` column is the light-gate reading, a fitted value, or a processed copy.
The article also reports 82 experiments while the pinned measured workbook has
30 trial IDs. The official supplement rights language has been reviewed, but
direct redistribution of the raw XLSX files is still unconfirmed. The
provenance of the drag constants must also be reviewed before fitting.

The unit of holdout is a complete trial. The split is deterministic and frozen
by a SHA-256 rule: trial ID `i` is held out when the first byte of
`SHA256("t2-projectile-trial:" + str(i))` modulo five is zero. This yields
holdout IDs 4, 6, 7, 9, 13, 21, 22, 29, and 30 for the currently inventoried
IDs 2–31. No tuning or model selection may use those trials.

The source intake also finds exact duplicate observation payloads for trials 22
and 23. The current split places 22 in holdout and 23 in training, so the
whole-trial holdout is unsafe until the source identity and experiment
provenance are reviewed. The protocol verifier rejects this boundary and keeps
model fitting blocked.

Both models fit only the declared initial position and launch speed. The
no-drag equations use the declared gravity and angle. The drag model uses the
spherical quadratic-drag law and constants shown in the source workbook only
after their provenance is reviewed. The primary metric is the per-trial RMSE
of two-dimensional position, with maximum error, signed residuals, paired
model differences, and a fixed-seed whole-trial bootstrap reported alongside
the 1.5 cm position uncertainty stated by the article.

The protocol explicitly rejects shuffled angle/speed labels, wrong-sign
gravity, malformed time order, train/holdout overlap, and fitting while the
`v0` role is unresolved, or duplicate trial content crosses the split. Even after every engineering gate passes, this is a
predictive model comparison for observational launcher trials. It cannot
identify a causal pressure intervention, establish a general physical law, or
promote the project to a research or publication claim.

The machine-checkable contract is [T2_PROJECTILE_MODEL_PROTOCOL.json](T2_PROJECTILE_MODEL_PROTOCOL.json).
