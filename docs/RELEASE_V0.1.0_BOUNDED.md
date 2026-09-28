# `v0.1.0-bounded` release boundary

## Purpose

This release is a reviewable engineering preview of an offline scientific evidence
workbench. The release line combines the local implementation history with the remote
repository's initial MIT commit, runs from a clean checkout, and records the exact checks
needed before creating the tag.

## What is supported

- T1 is a deterministic Hohmann Mars-transfer fixture with dimensional checks,
  candidate selection, holdout/error gates, provenance fingerprints, replay, and report
  export.
- T2-T5 expose independent bounded evaluators, positive and negative cases, source or
  fixture fingerprints, and replayable evidence packages.
- The wheel contains the offline schemas, policies, fixtures, and documentation required
  by the CLI smoke path.
- CI exercises Python 3.11 and 3.12 tests on Ubuntu, a Windows test job, and the recorded
  Windows AMD64 CPython 3.12.3 environment for committed receipts and wheel replay.

## What the evidence does not support

The current receipts do not establish real-world scientific validity, external paper
reproduction, production solver quality, causal identification, long-horizon chaotic
accuracy, a general formal-proof backend, wet-lab execution, biosafety approval, or
publication readiness. T5 remains a text-reviewed demo and execution is disabled.
The external symbolic engine remains blocked pending a fixed revision, path, and license.
These boundaries are encoded in the portfolio status and acceptance receipts.

## Tag gate

Create `v0.1.0-bounded` only after all of the following are green on a fresh checkout:

1. `python -m pytest -q` on the supported test matrix.
2. Windows CPython 3.12.3 with `requirements-replay-win-py312.txt` passes `pip check`,
   `scripts/verify_replay_environment.py`, `scripts/verify_acceptance.py`, and
   `scripts/sync_optional_acceptance.py --verify`.
3. `scripts/verify_wheel_install.py` builds a wheel, installs it outside the checkout,
   and replays the generated and committed offline runs.
4. The draft integration PR is reviewed and the remote MIT license remains present.
5. `git diff --check` is clean and the untracked historical experiment outputs are not
   staged into the release commit.

The tag is a packaging milestone. It does not change any track's scientific status or
close the open data-rights, independent-source, human-review, compute, or biosafety gates.

## Next PR sequence

- **T2:** resolve measured `v0` semantics, the 30/82 experiment coverage mismatch, source
  rights, and a preregistered trial-level holdout before fitting real data.
- **T3:** add rights-cleared long-horizon/non-integrable validation, independent backends,
  and a fixed compute/error budget without converting finite trajectory agreement into a
  chaos claim.
- **T4:** integrate a genuine formal-proof backend and separately review the physical model
  and real-world validation obligations.
- **T5:** complete independent source/rights review, residual visual-omission audit, expert
  biosafety review, and human acceptance while keeping execution disabled.
