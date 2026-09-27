# Decisions

## 2026-09-20 — First vertical slice

Use `E:/xuexi/projects/05_hohmann_mars_transfer` as the first benchmark. It is an
offline-friendly orbital-mechanics baseline with explicit formulas and units.

## 2026-09-20 — Missing external symbolic engine

Implement a small internal bounded symbolic candidate generator first. The requested
`symbolic-physics-engine` adapter is present as a protocol and manifest entry only; it
remains `blocked` until a real path/repository, revision, and license are supplied.

## 2026-09-20 — Delivery shape

Ship CLI plus Markdown/JSON evidence first. Defer Web UI until deterministic replay,
failure-path tests, and claim-level evidence gates pass.

## 2026-09-20 — Remote repository boundary

Use `https://github.com/wangyufanshuai/auditable-scientist-lab` as the formal remote.
It is public and MIT-licensed, with only the initial commit at planning time. Keep
implementation changes local until the first acceptance package exists; then push a
reviewable commit or pull request rather than a partial release.
