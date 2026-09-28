# Changelog

All notable changes to this project are documented here. This project follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and uses Semantic Versioning
for the Python package version.

## [0.1.0] - 2026-09-28

This bounded engineering preview packages the offline, replayable five-track workbench.
It is suitable for code review and local reproduction within the stated fixtures; it is
not a scientific validity, publication, production-solver, wet-lab, or safety approval.

### Added

- T1 Hohmann Mars-transfer CLI with deterministic offline runs, provenance hashes,
  holdout/error gates, replay, inspection, and Markdown/JSON reports.
- Shared append-only Run/Event/Trace contracts and fail-closed replay checks for T1-T5.
- Bounded T2, T3, T4, and T5 evaluators with explicit evidence levels, negative cases,
  source fingerprints, and blocked boundaries.
- Exact rational velocity-Verlet invariant receipt with an explicit Euler counterexample.
- Windows CPython 3.12.3 replay constraints, clean wheel installation smoke tests, and
  GitHub Actions coverage for tests, acceptance, and wheel replay.
- Public release and evidence-boundary documentation for the `v0.1.0-bounded` tag.

### Changed

- The repository now carries the remote MIT license together with the local implementation
  on the `publish/integration` branch.

[0.1.0]: https://github.com/wangyufanshuai/auditable-scientist-lab/compare/d3e4f1383df7b21aced7816f16df9cb9cce87140...v0.1.0
