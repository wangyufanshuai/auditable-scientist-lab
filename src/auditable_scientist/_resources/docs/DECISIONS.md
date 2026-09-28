# Decisions

## 2026-09-20 — First vertical slice

Use `E:/xuexi/projects/05_hohmann_mars_transfer` as the first benchmark. It is an
offline-friendly orbital-mechanics baseline with explicit formulas and units.

## 2026-09-20 — Missing external symbolic engine

Implement a small internal bounded symbolic candidate generator first. The requested
`symbolic-physics-engine` adapter is present as a protocol and manifest entry only; it
remains `blocked` until a real path/repository, revision, and license are supplied.

## 2026-09-27 — Located but non-operational symbolic engine

Read-only discovery found `E:/86137/myai/symbolic-physics-engine`. Its directory is
untracked beneath the parent Git repository, has no scoped LICENSE/COPYING file,
and `AIFeynmanEngine.discover` unconditionally raises `NotImplementedError`.
The exact file hashes are in `artifacts/symbolic-engine-audit.json`. Keep the
adapter blocked; the parent repository's commit is not a revision of these files.

## 2026-09-27 — Honest bounded grammar for T1

Replace the five hard-coded evaluator functions, including one that called the
analytic baseline directly, with a ten-expression radius/factor grammar. Rank on
training data and use the independent baseline and fixed holdout only for checks.
The correct form is predeclared in the grammar, so reports must call this a
bounded selection and reproduction, never open-ended law discovery.

## 2026-09-20 — Delivery shape

Ship CLI plus Markdown/JSON evidence first. Defer Web UI until deterministic replay,
failure-path tests, and claim-level evidence gates pass.

## 2026-09-20 — Remote repository boundary

Use `https://github.com/wangyufanshuai/auditable-scientist-lab` as the formal remote.
It is public and MIT-licensed, with only the initial commit at planning time. Keep
implementation changes local until the first acceptance package exists; then push a
reviewable commit or pull request rather than a partial release.

## 2026-09-27 — Historical CLI routing

The console and package-module commands use a version router. Runs bound to the
old `pyproject.toml` or `__main__.py` execute against a SHA-256-pinned source
bundle built from Git commit `8c26a26`; new Runs use current source bytes.
The router validates a copied historical Run before inspect or report export.
This preserves existing replay manifests without treating a changed source
fingerprint as equivalent.

## 2026-09-27 — Optional NAIF DE440s geometry source

NAIF explicitly permits use of its kernels and redistribution of unmodified
NAIF-distributed kernels. Keep the large `de440s.bsp` binary outside Git, pin
its official MD5 and downloaded SHA-256, and commit only a small derived
snapshot and bounded audit. DE440s supplies Mars-barycenter states, not a Mars
center or spacecraft trajectory; its mission Claim remains unverified.
