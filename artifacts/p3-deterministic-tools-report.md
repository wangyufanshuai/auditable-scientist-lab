# P3 deterministic tools checkpoint

- Status: `implementing`
- Date: 2026-09-20
- Scope: exact unit dimensions, Hohmann baseline computation, and explicit error/holdout gates
- Scientific status: the Hohmann function is a deterministic reference calculation; it is not
  evidence that a candidate scientific method has been discovered or validated.

## Implemented

- A bounded unit-dimension checker parses common SI-derived tokens without converting scale,
  checks additive compatibility, and verifies the Hohmann time-of-flight expression has units of
  seconds.
- `hohmann_baseline` computes the analytic transfer ellipse, time of flight, perihelion and
  aphelion velocity changes, and total heliocentric delta-v from positive inputs.
- Error statistics and a holdout gate return structured results; a failed threshold remains a
  failure instead of being promoted to a claim.

## Commands

| Command | Result |
|---|---|
| `python -m pytest -q` | 15 passed |
| `python -m pip install -e . --no-deps --no-build-isolation` | previously passed in P1/P2; rerun at P4 acceptance |

The test process emitted the existing `pytest-asyncio` configuration deprecation warning; no
async fixtures are used by this project.

## Remaining gate

P3 does not yet provide a scientific candidate, dataset split, or replayable CLI run. P4 must
bind these deterministic tools to the Hohmann benchmark, record an evidence package, and expose
`init`, `run`, `replay`, `inspect`, and `export-report` commands.
