# P5 adapter boundary checkpoint

- Status: `implementing`
- Date: 2026-09-20
- Scope: source manifests, contract-only evidence mapping, and blocked symbolic provider
- Scientific status: no new scientific claim; this checkpoint records provenance and refusal
  behavior.

## Implemented

- Five inventory-derived `AdapterManifest` records describe project 05, the engineering copilot,
  paper2project, physics-programmable-learning, and the missing symbolic-physics-engine source.
- Every adapter is read-only and has `code_reuse_allowed=false`; MIT on the policy reference is
  recorded separately from implementation readiness.
- External evidence IDs can be mapped without importing source code or treating an unverified
  reference as data.
- The external symbolic provider protocol validates requests and fails closed with
  `AdapterBlocked` while its path, revision, and license are unresolved.

## Commands

| Command | Result |
|---|---|
| `python -m pytest -q` | 21 passed |
| `python -m pip install -e . --no-deps --no-build-isolation` | exit 0 in P4; package unchanged since then |

## Remaining gate

The internal bounded generator remains the only executable symbolic searcher. P5 does not grant
permission to copy external code, resolve missing licenses, or claim that any external adapter
works. P6 must add the minimal Agent and Policy layer around these contracts.
