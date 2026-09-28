# P6 agent and policy checkpoint

- Status: `implementing`
- Date: 2026-09-21
- Scope: offline agent proposals and policy-enforced tool execution
- Scientific status: no scientific claim; policy tests establish execution boundaries only.

## Implemented

- `ToolRegistry` invokes only registered tools and enforces network mode, provider allowlists,
  path roots, call budgets, and wall-clock budgets.
- `OfflineAgent` can emit question, hypothesis, or explanation proposals and call registered
  tools; its proposal schema has no claim-status transition.
- Policy failures are explicit `PolicyDenied` errors and do not silently retry or widen scope.
- Tests cover offline success, network denial, provider denial, path denial, call budgets, and
  attempted claim fields.

## Commands

| Command | Result |
|---|---|
| `python -m pytest -q` | 25 passed |

## Remaining gate

The policy runtime is not yet wired into the CLI run transcript or a model provider. The final
acceptance package must show an end-to-end policy receipt, replay checks, and negative cases for
the T1 run, then define independent evaluators for T2–T5.
