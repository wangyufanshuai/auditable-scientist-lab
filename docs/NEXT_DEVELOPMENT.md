# Development after the bounded release

Snapshot: 2026-10-05. Repository state and PR metadata were checked live.

The project is a bounded engineering preview with multiple scientific slices,
offline reports, deterministic replay, failure-path checks, source inventories,
and explicit open gates. It has useful engineering evidence. It has not achieved
general scientific discovery, real-world causal identification, long-time chaos
validation, general formal proof, operational protocol approval, or publication
readiness. Test counts measure engineering checks, not scientific progress.

## Current integration boundary

`main` was `c3f9b31`; the existing `v0.1.0-bounded` release remains bounded.
The registry branch starts at T5 acceptance `4dbb0eb`. It includes the T4/T5
stack but does not silently include the separate T2/T3 increments below.

| Stack | Open Draft PRs | Result represented |
| --- | --- | --- |
| T2 provenance and reconciliation | #7 -> #9 -> #10 | Intake/provenance and acceptance bindings; no admitted real-data model fit |
| T3 independent backend | #8 -> #11 | Backend contract and acceptance binding; no mission or long-time validation |
| T4 -> T5 | #5 -> #6 -> #13; #12 also branches from #5 | Finite floating conformance, T5 source/review boundaries, root acceptance bindings |
| Target registry | Current increment, based on #13 | Extensible declaration, evidence identity, and installed validation; no solver dispatch |

All nine prior PRs were open Drafts at this snapshot. Source inventories and
authored reviews remain separate from rights clearance and human approval.
The primary checkout's existing dirty and untracked artifacts are preserved.

## Dependency-ordered work

| Priority | Concrete deliverable | Required gate | Stop boundary |
| --- | --- | --- | --- |
| P0: complete this increment | Generic target contract, receipt hashes, audit projection without recursive hashes, packaged declaration/API, negative tests | Saved audit equals recomputation; stale receipts fail before synchronization writes; installed wheel validates declarations and explicit evidence; historical and relocated Runs replay | No registry entry can promote science, rights, human approval, execution, or release |
| P1: integrate accepted increments | A dedicated integration candidate combining the reviewed T2/T3/T4/T5 stacks and removing duplicate acceptance rows deliberately | Clean source snapshot; three-platform test matrix; pinned replay interpreter; all nine committed/relocated Runs; regenerated registry after reviewed receipt changes | PR merges and new release tags require their own authorization; preserve all topic branches and dirty source checkouts |
| P2: T2 measurement admission | Reconcile workbook/article definitions, every trial's velocity role, and the 30/82 coverage discrepancy; retain exclusion reasons | Inspectable primary-source statements, pinned source revision/hash, explicit permitted data use, complete intake reconciliation | No measured fit while velocity role or rights remains unresolved; observational data cannot establish interventions |
| P3: T2 prospective comparison | Implement the declared no-drag/drag comparison behind a checked admission gate; report per-trial residuals and uncertainty | Whole-trial split fixed before fitting, baseline and candidate on identical admitted trials, no holdout tuning, deterministic negative cases and replay | Stop if data is reclassified after inspecting holdout, uncertainty is unsupported, or evidence is only synthetic |
| P4: T3 independent finite campaign | Run an independently sourced, rights-cleared backend on declared initial conditions and guarded horizons | Provider version/license identity, convergence under refinement, conserved-quantity diagnostics, independent backend agreement, timeout/budget rejection | Finite agreement cannot establish chaos, unbounded stability, or mission fidelity |
| P5: T4 model/proof expansion | One reviewed physical transition model, one versioned proof backend adapter, and proof/counterexample receipts | Assumptions and units recorded; proof independently checked; deliberately invalid transition rejected; floating conformance retained separately | Symbolic invariants and finite tests cannot certify an entire floating implementation or real-world model |
| P6: T5 review handoff | Read-only source comparison and explicit omissions, rights scope, reviewer identity, and biosafety/human decisions | Independent source/reference resolution; traceable expert review; human acceptance recorded as its own evidence | Keep operational execution disabled; agent observations cannot substitute for experts |
| P7: extend scientific targets | Add a target contract plus a domain-specific evaluator/runtime adapter | Problem, units, candidates, baselines, split, stopping rules, rights, negative controls, acceptance, and replay | Registration alone cannot count as a new working scientific capability |

Independent work may resolve primary-source questions while engineering gates run.
Do not create a general-purpose agent framework to avoid domain-specific blockers.
CLI and Markdown/JSON remain the first delivery surface; Web work follows stable
evidence contracts and a demonstrated user need.

## Scientific acceptance rules

- T1: independent mission observables, reviewed forces/maneuvers, a predeclared
  holdout and uncertainty model, and externally checked comparisons are required
  before any mission-domain claim. Reconstructed navigation endpoints and generic
  sensitivity grids are insufficient.
- T2: rights and measured-column semantics must be resolved before fitting. Real
  intervention evidence and identification assumptions are additional requirements
  for causal claims. Freeze the numerical/statistical thresholds prospectively.
- T3: record the finite regime, horizon, close-approach guards, refinement rates,
  tolerances, and compute budget before execution. Long-time and nonintegrable
  behavior need distinct campaigns; they are not inherited from a finite receipt.
- T4: review the transition assumptions and proof scope. A checked theorem, finite
  floating conformance, and physical validation are different evidence categories.
- T5: retain source restrictions and all omissions. Source availability, text
  consistency, visual observations, biosafety, and human approval remain separate.

Each increment must have a source-bound receipt, relevant negative cases,
acceptance projection, documentation, fresh-checkout validation, and installed
replay evidence before it is proposed for integration. If two rounds add no new
verifiable evidence, return to the blocking contract or replay failure before
expanding feature scope. A green CI run is never a scientific or publication gate.
