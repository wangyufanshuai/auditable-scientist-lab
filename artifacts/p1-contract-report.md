# P1 contract checkpoint

- Status: `implementing`
- Date: 2026-09-20
- Scope: domain models, JSON Schema validation, and invalid-state tests
- Scientific status: no scientific claim; this is engineering evidence only

## Commands

| Command | Result |
|---|---|
| `python -m pip install -e . --no-deps --no-build-isolation` | exit 0 |
| `python -c "from auditable_scientist.domain import ..."` | `import_check=pass` |
| `python -m pytest -q` | 7 passed |
| `Draft202012Validator.check_schema(...)` | `schema_check=pass` |

The test process emitted an existing `pytest-asyncio` configuration deprecation warning;
it did not affect the result and no async fixtures are used by P1.

## Covered contracts

- Required research records: `ResearchQuestion`, `Hypothesis`, `ExperimentPlan`,
  `Observation`, `Claim`, `Evidence`.
- Shared identity records: `Agent`, `Tool`, `Run`, `Event`, `Trace`, `Memory`,
  `Evaluator`, `Provider`, `Policy`.
- Rejected states: malformed SHA-256, train/holdout name collision, unknown claim
  evidence, non-contiguous event sequence/hash chain, and reproduced claim without a
  verified holdout.
- The hand-authored `schemas/run.schema.json` validates a complete representative Run.

## Remaining gate

P1 does not prove deterministic replay, numerical correctness, symbolic discovery, CLI
behavior, real-data provenance, or scientific validity. P2 must implement canonical
serialization, append-only event persistence, and tamper-evident replay tests.
