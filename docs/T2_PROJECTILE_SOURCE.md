# T2: real projectile measurement intake

Wadsworth and colleagues' [2025 Physics Education article](https://doi.org/10.1088/1361-6552/add2c5)
describes camera-tracked steel-ball trajectories with varied launcher angle and
pressure, and reports 82 experiments. Its official
[supplement page](https://beta.iopscience.iop.org/article/10.1088/1361-6552/add2c5/data)
links two XLSX files. The first locally pinned workbook contains 179 measured
position/time rows from **30** trial IDs, numbered 2–31, at seven declared
angles and twelve declared initial speeds. It contains no blank numeric cells,
formulas, external links, or macros; time increases within each trial. The
second workbook contains 3,507 formulas and is classified as a numerical
example, not an observation source. This audit cannot account for the other
52 experiments mentioned by the article.

The article says the launcher operated below 6 m/s, measures initial velocity
with an in-built light gate accurate to 0.1 m/s, and also treats `v0` as a
least-squares fitting parameter. It says the supplementary file presents the
results using the measured initial velocity. The first workbook's `v0 (m/s)`
header does not identify whether each row stores the light-gate reading, the
fitted value, or a processed copy. Fifteen of the 30 trial IDs have a `v0`
value above 6 m/s, including 11 trials whose value is exactly 6.4 m/s and four
more between 6.2 and 6.35 m/s. This pattern makes the column-level mapping and
the range discrepancy a source-review issue rather than evidence for either a
light-gate reading or a fitted parameter. No model fit or causal effect is
inferred from that discrepancy.

The [source audit](../artifacts/t2-projectile-source-audit.json) binds the
article PDF and both supplement workbooks by size and SHA-256, records each
trial's row count, declared inputs, time range, and ordered-row hash, and
rejects missing rows, nonfinite measurements, duplicate times, or changing
inputs within a trial. Run `python scripts/verify_t2_projectile_source.py
--verify` with the pinned local files and `openpyxl` 3.1.5 / `pypdf` 6.15.0
to recompute it. The original PDF and XLSX files remain locally ignored and
are not redistributed in Git.

The PDF declares CC BY 4.0 for the article. The official supplement page says
the files are published under license by IOP Publishing and that rights belong
to the authors unless otherwise specified; it also says original content may
be used under CC BY 4.0 with attribution. This rights language has been
reviewed, but the page does not unambiguously confirm direct redistribution of
the raw XLSX files, so redistribution remains blocked. These are source-tracked real measurements, but their
experimental coverage, `v0` semantics, uncertainty mapping, dataset rights,
physical-model validity, and causal identification remain open. The Claim
stays `unverified` and no scientific holdout is claimed.
