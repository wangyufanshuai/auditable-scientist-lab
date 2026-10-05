# T2 projectile source reconciliation

The [reconciliation contract](T2_PROJECTILE_SOURCE_RECONCILIATION_CONTRACT.json)
binds the article-level experiment count, the locally pinned workbook inventory,
the unresolved `v0` column role, workbook package metadata, and the existing
post-hoc diagnostics into one fail-closed receipt. The article reports 82
experiments, while the measured workbook contains 179 rows from 30 trial IDs;
the remaining 52 experiments are unaccounted for by this intake and are not
treated as missing observations that may be silently reconstructed.

The article's light-gate and least-squares statements are recorded as separate
source claims. The workbook header is only `v0 (m/s)`, so those statements do
not resolve whether the column contains a light-gate reading, a fitted value,
or a processed copy. Fifteen declared values exceed the article's stated 6 m/s
launcher bound. The workbook's `xl/workbook.xml` contains an absolute local-path
metadata element; its package-part and value hashes are retained as provenance
signals only and do not establish column semantics or source authorship.

The reconciliation also preserves the existing finding that trials 22 and 23
have identical observation payloads across the current training/holdout split.
The supplementary rights language has been reviewed, but direct redistribution
of the raw XLSX files is not confirmed. The receipt therefore keeps all model,
causal, holdout, rights-clearance, research-candidate, and publication claims
blocked.

Run `python scripts/verify_t2_projectile_source_reconciliation.py --verify` in a
clean checkout. It uses only committed JSON receipts and does not require the
ignored PDF or XLSX files. `--write` is reserved for creating a new receipt and
refuses to overwrite an existing one.
