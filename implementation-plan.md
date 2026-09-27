# Auditable Scientist Lab implementation plan

## Material Passport

- Origin Skill: `academic-research-suite/experiment-agent`
- Origin Mode: `plan`
- Origin Date: `2026-09-20`
- Verification Status: `UNVERIFIED`
- Version Label: `code_plan_v1`
- Delivery boundary: implement against the public MIT repository, but do not push until
  the first acceptance package is complete

## Current implementation checkpoint (2026-09-27)

- P0–P7 T1 package: implemented locally. `artifacts/acceptance.json` records the CLI,
  policy receipt, replay checks, and bounded evidence boundary.
- T2–T5: each now has an independent offline evaluator, positive fixture, negative case,
  input hash, acceptance JSON, shared-kernel Run/Event/Trace package, and explicit open gates
  in `artifacts/track-portfolio.json`.
- The portfolio is still `implementing` locally. No claim of real-data validity, formal
  proof completeness, wet-lab authorization, production readiness, or public release is closed.
- Current mutation checks reject altered T1 input, experiment, Run, event log, and project-05
  snapshot, plus altered T2 acceptance boundaries, result, event log, and source hash. T2–T5
  acceptance packages record the evaluator's source SHA-256 and replay their negative cases.
- T2–T5 now use registered offline Tool/Policy calls for generated acceptance packages
  and `run-track` CLI runs. Their runtime bundles support deterministic `replay`, `inspect`,
  and `export-report`; the claim remains `unverified` outside the bounded fixture scope.
- An earlier fresh Python environment installed `.[test]` and passed 63 tests.
  The pinned Windows AMD64 / CPython 3.12.3 environment now passes 74 tests and
  matches all seven current Run manifests. Its exact dependency closure was installed
  from `requirements-replay-win-py312.txt` and passed `pip check`. The resulting
  `artifacts/replay-environment-audit.json` binds installed versions and manifest bytes.
  Replay in a mismatched environment fails closed; wheel and interpreter bytes are not locked.
- A standalone wheel now carries the offline schemas, evidence policy, and seven fixtures.
  In a fresh installation outside the checkout, T1 `init/run/replay/inspect/export-report`
  and T2–T5 plus T2P/T3N `init-track/run-track/replay` completed. The wheel smoke is an engineering
  portability check, not an external scientific validation or publication gate.
- T3 now compares Velocity-Verlet against a separately implemented fixed-step RK4,
  plus the analytic oscillator and Euler negative control. The method citation,
  source-rights boundary, and fixture scope are recorded in `docs/T3_METHOD.md`;
  an external production solver and broad multi-body validation remain open.
- The T3N subtrack compares two local numerical methods against a directly derived
  equilateral three-body circular orbit for equal and unequal masses. Conservation,
  barycenter, separation, and a repulsive-force negative control pass the declared
  dimensionless fixture gates in `docs/T3_NBODY_METHOD.md`. This does not validate
  nonintegrable trajectories or real missions.
- The T2P subtrack supplies a 100-case planar ball-and-floor simulator with paired
  parameter and policy counterfactuals, analytic first-impact and rebound references,
  a zero-effect negative estimator, and a full example trajectory. The local
  `CausalInference` folder was inspected read-only; its untracked revision and scoped
  license are unresolved, so no external code was imported. See `docs/T2_PHYSICAL_METHOD.md`.
- A 27-case T3 parameter/step-size sweep now checks second- and fourth-order
  convergence, normalized energy drift, backend agreement, and Euler rejection.
  `artifacts/t3-sweep.json` is independently recomputed by the acceptance verifier;
  it is still evidence only for the declared oscillator grid.
- A separate, optional SciPy 1.18.1 / NumPy 2.2.6 DOP853 cross-check passed nine
  oscillator cases and a wrong-sign negative control. Its Windows wheels, source
  tags, and installed license notices are recorded in `docs/T3_EXTERNAL_SOLVER.md`
  and `artifacts/t3-external-scipy.json`. A separate versioned Tool/Provider Run
  in `artifacts/t3-external-runs/` now replays this pinned computation, records
  license snapshots and a network-disabled policy, and rejects altered output
  and license bytes. SciPy remains outside the core dependency and T3 core Run;
  the optional Run does not close multi-body or mission gates.
- A separate optional audit now compares two momentum-balanced, perturbed three-body
  initial states over 0.35 unperturbed periods. Pinned SciPy DOP853, local Verlet
  at two resolutions, and independently coded RK4 pass the declared finite-horizon
  convergence, invariant, separation, and repulsive-force negative gates. See
  `docs/T3_PERTURBED_METHOD.md` and `artifacts/t3-perturbed-audit.json`. This audit
  is outside the core Run and does not validate chaotic long horizons or missions.
  An optional shared Tool/Provider Run in `artifacts/t3-perturbed-runs/` now binds
  the same grid to replay, source/license snapshots, network-disabled policy,
  moved-run verification, and altered-result/license rejection. Its claim stays
  unverified and does not expand the numerical scope.
- T4 now carries exact decimal transfer witnesses, contiguous steps, and a complete
  five-obligation set. A fixed-rule symbolic conservation identity and every finite
  transition are checked; a modified mass with a recomputed trajectory hash is rejected.
  The v2 package remains bounded to this declared rule and is not a general proof backend.
- Current v2 Run manifests use bounded `run://` and `root://` references and snapshot
  fixture inputs. T1–T5 plus T2P/T3N replayed from a copied checkout in the same dependency
  environment, and seven wheel-generated run directories replayed after relocation.
  `artifacts/relocation-audit.json` records the copied-checkout commands and hashes.
  Cross-OS and dependency-version drift remain unverified or fail closed; the
  project-05 upstream snapshot still records its original host path for provenance.
- Next engineering work is deeper independent backends and data/proof provenance.
  Scientific, rights, compute, and human-review gates remain open; public release
  remains a separate decision.

## Confirmed decisions

1. The first benchmark is `E:/xuexi/projects/05_hohmann_mars_transfer`.
2. The first symbolic-discovery implementation is an internal bounded candidate
   generator. The external `symbolic-physics-engine` adapter remains `blocked` until
   its real path or repository and license are provided.
3. The first release is an offline CLI with Markdown and JSON reports. Web UI follows
   only after the replay and evidence gates close.
4. The formal remote is `https://github.com/wangyufanshuai/auditable-scientist-lab`.
   Work stays local until acceptance evidence exists; no half-finished release is pushed.

## Objective and research boundary

The product accepts a scientific question, a declared data snapshot, and an allowlisted
tool set. It emits a replayable Run containing formalized question, hypotheses,
experiment plan, observations, candidate expressions, deterministic calculations,
falsification checks, claims, and evidence references.

The first scientific question is deliberately bounded:

> Given heliocentric two-body assumptions and $(r_1, r_2, \mu)$ with declared units,
> can a constrained symbolic search recover a candidate for a Hohmann-transfer
> observable that passes a fixed holdout and dimensional-consistency gate?

This is a reproducibility and auditability demonstration. Passing it does not establish
new physics, external scientific novelty, production readiness, or publication readiness.

## Current constraints and blockers

| Item | Status | Planning consequence |
|---|---|---|
| Target directory | resolved by this planning package | New files may be added here only |
| Remote repository | public MIT repository, `main`, initial commit `d3e4f1383df7b21aced7816f16df9cb9cce87140` | Reconcile local plan with this baseline before the first implementation push |
| 50-project index | present and lists projects 1–50 | Use project 05 as the first adapter |
| `symbolic-physics-engine` | local directory found at `E:/86137/myai/symbolic-physics-engine`, but untracked, unlicensed, and its `discover` entrypoint is a stub | External adapter remains `blocked`; use bounded internal generator and the read-only hash audit |
| `engineering-research-copilot` | local code exists, root license/revision not confirmed | Use contract-level adapter, no code copy |
| `paper2project` | evidence-ID workflow exists, root license/revision not confirmed | Map evidence IDs only after provenance manifest |
| `physics-programmable-learning` | MIT repository with a dirty worktree | Read-only reference and evidence-policy source |
| project 05 | deterministic Hohmann baseline, no project-level tests observed | Wrap through a declared adapter and add independent contract tests |

## Architecture

```text
src/auditable_scientist/
  domain/        pure models, enums, state transitions
  runtime/       run store, event log, trace, replay, snapshot verification
  tools/         dimensional check, numerical baseline, error/statistics
  adapters/      project-05, paper2project, copilot, symbolic provider protocol
  evaluation/    train/holdout gate, falsification, claim promotion rules
  reporting/     terminal, Markdown, JSON
  policy/        network, budget, timeout, file scope, provider allowlist
```

### Canonical records

- `ResearchQuestion`: question text, domain, observables, assumptions, dataset ref,
  allowed tools, and intended evidence level.
- `Hypothesis`: candidate expression, variables, units, source, status, and candidate
  set commitment.
- `ExperimentPlan`: train/holdout IDs, seed, tool versions, tolerances, budget, and
  falsification checks.
- `Observation`: dataset snapshot hash, row/column summary, split, units, and source.
- `Claim`: text, `candidate|reproduced|unverified|rejected`, evidence refs, and
  falsification checks.
- `Evidence`: stable ID, kind, path/URI, SHA-256, source revision, provenance status,
  and allowed use.

### Run and Event invariants

Every Run contains `run_id`, `task_id`, `created_at`, `input_hash`, `code_revision`,
`environment`, `seed`, `evidence_refs`, and `status`. Events are append-only and carry
sequence, event type, canonical payload hash, and previous-event hash. Replay compares
canonical computational payloads and candidate ordering; volatile timestamps are metadata.

Every candidate discovery record must contain:

```text
expression, train_split, holdout_split, residuals, complexity,
dimensional_status, seed, source_revision, failed_candidate_count
```

No holdout result means the claim cannot leave `candidate`.

## Long-term scientific portfolio

“All scientific goals” is interpreted as completing the five vertical slices in the
shared task contract, each with its own domain evaluator and acceptance package. It does
not mean one unrestricted agent is allowed to make universal scientific claims. The
shared kernel supplies provenance, replay, policy, and evidence; domain plugins supply
the scientific semantics and independent checks.

| Track | Scientific goal | First authoritative evaluator | Dependency | Completion boundary |
|---|---|---|---|---|
| T1 | Auditable scientific law discovery | analytic baseline + dimensional and holdout gates | project 05, bounded symbolic generator | one complete physics Run and acceptance package |
| T2 | Causal physical world lab | intervention semantics + simulation-based inference checks | T1 contracts; causal/simulation assets | at least one intervention task with negative/control cases |
| T3 | Physics dynamics foundation | independent numerical solver comparison and conservation/residual checks | T1 kernel; CAE/PINN/N-body assets | one dynamics family with replayable parameter sweep |
| T4 | Proof-carrying simulation | machine-checkable proof/obligation records plus numerical replay | T1/T3; physics-programmable-learning | one simulation whose claim is blocked when proof obligations fail |
| T5 | Bio-Chem protocol verifier | protocol constraint checks, provenance, and safe failure paths | shared evidence contract; paper2project; licensed bio/chem assets | one protocol verification slice; no autonomous wet-lab execution |

The sequence is `T1 → T3 → T4`, with `T2` parallel after the shared kernel, and `T5`
after evidence and provenance contracts stabilize. Each track must preserve the same
fields for `Agent`, `Tool`, `Run`, `Event`, `Trace`, `Memory`, `Evaluator`, `Evidence`,
`Provider`, and `Policy`, while its evaluator remains domain-specific.

### Portfolio-level completion gates

The portfolio is complete only when all five tracks have either a passing acceptance
package or a reproducible, explicitly documented `blocked` package. A track cannot be
promoted because another track passed. The final portfolio report must show, per track:

- latest `acceptance.json` and source revision;
- engineering status and scientific evidence level separately;
- independent backend or analytic reference where applicable;
- negative, inconclusive, and failed cases;
- open license, data-rights, compute, and human-review gates;
- whether the track is suitable for local demo, research candidate, or public release.

The shared kernel must remain small. Domain-specific solvers, datasets, and policies belong
in adapters or plugins; adding a second large agent framework is a stop condition.

## Benchmark design: project 05

The adapter exposes a side-effect-free table contract for the Hohmann calculation. The
initial table varies $(r_1, r_2, \mu)$ within a fixed domain and records target values
such as transfer time or heliocentric delta-v together with units. The split is fixed by
parameter strata so that holdout tests interpolation and bounded extrapolation rather
than memorization of shuffled rows.

The baseline is the declared Hohmann calculation from project 05. The internal symbolic
generator searches a small, versioned grammar of arithmetic operations, powers, and
square roots. It rejects dimensionally invalid expressions before scoring and applies a
complexity penalty. The adapter must record whether a result came from the baseline,
the internal generator, or an external provider.

The report must show:

1. assumptions and input snapshot;
2. baseline values and analytic checks;
3. committed candidate set and failed candidates;
4. train and holdout residuals;
5. complexity and dimensional status;
6. falsification outcomes;
7. evidence chain and unresolved items;
8. claim status and evidence level.

## Phases and gates

### P0 — provenance and source inventory

Create the source snapshot manifest, hash selected files, record local revision state,
license status, adapter mode, and known gaps. Gate G0 requires every source used by the
first Run to have a path, hash, and explicit provenance status. Also record the remote
repository URL, default branch, license, and starting commit.

### P1 — domain and schema contract

Implement Pydantic models and JSON Schema for the records above. Add invalid-state tests:
missing holdout, unknown evidence reference, unsupported claim status, duplicate event
sequence, and malformed hash.

Gate G1: schema validation and state-transition tests pass.

### P2 — deterministic Run and replay

Implement canonical JSON serialization, append-only event storage, environment capture,
seed handling, source snapshot verification, and replay comparison. Add explicit failure
events rather than silent retries.

Gate G2: two runs with identical inputs produce identical computational hashes; changing
input, source snapshot, dependency manifest, or evidence file fails closed.

### P3 — deterministic tools

Implement:

- `dimensional_check`: unit algebra, not token scanning;
- `numeric_baseline`: fixed solver, tolerance, analytic reference, and solver metadata;
- `error_statistics`: residual, MAE/RMSE, holdout summary, and declared thresholds.

Gate G3: tools work without network and expose versioned, JSON-serializable outputs.

### P4 — Hohmann vertical slice

Wire `init → run → replay → inspect → export-report`. Use a fixed seed and committed
train/holdout manifest. Keep the candidate generator bounded so runtime and candidate
count are auditable.

Gate G4: baseline, candidate ranking, holdout metrics, and report payload replay exactly.

### P5 — adapter boundary

Add manifests and contract tests for project 05, paper2project evidence IDs, and the
engineering copilot tool protocol. Add an external symbolic-provider interface but keep
its status `blocked` until the missing source and license are resolved.

Gate G5: adapters do not copy source code and all unverified provenance remains visible.

### P6 — minimal Agent and Policy layer

Permit an Agent to propose a question, hypothesis, or explanation only through registered
Tools. Validate arguments against schemas and enforce network, timeout, budget, and file
scope. The Agent cannot promote a Claim or override a failed gate.

Gate G6: offline deterministic execution remains possible with no model provider.

### P7 — acceptance package

Generate `artifacts/acceptance.json`, `test-report.md`, `demo-transcript.md`, and
`sample-run.json`. Add a terminal report first; defer Web UI until G4–G6 are stable.

Gate G7: all task-level acceptance checks have a command, exit code, timestamp, input
version, and output path.

## Test and evidence matrix

| Test class | Required evidence |
|---|---|
| Unit | domain transitions, canonical serialization, tool math |
| Contract | JSON Schema, adapter manifests, CLI argument validation |
| Replay | same-input equality and source/evidence hash verification |
| Failure path | tampered input/source/evidence, missing holdout, timeout, budget denial |
| CLI smoke | offline `init`, `run`, `replay`, `inspect`, `export-report` |
| Scientific boundary | separate `demo`, `validated-reproduction`, `real-data`, `research-candidate` labels |

Planned commands after implementation:

```powershell
python -m pytest -q
python -m auditable_scientist.cli init examples/hohmann/run.yaml
python -m auditable_scientist.cli run examples/hohmann/run.yaml --offline --seed 17
python -m auditable_scientist.cli replay artifacts/<run_id>
python -m auditable_scientist.cli inspect artifacts/<run_id>
python -m auditable_scientist.cli export-report artifacts/<run_id>
```

## Stop conditions

Stop and report instead of continuing when a source license or data right cannot be
confirmed, when a fixture is being used to support a real-data claim, when a second large
framework appears necessary, or when a change would require touching a dirty source
worktree. These are planning gates, not errors to hide.

## External design references

The following public repositories were checked through the GitHub/Exa connectors and
remain design references only:

- [NewtonBench](https://github.com/HKUST-KnowComp/NewtonBench): interactive scientific
  law discovery and memorization-resistant benchmark design.
- [audit-closed-ai-scientist](https://github.com/kadubon/audit-closed-ai-scientist):
  transparency logs, candidate-set commitment, deterministic replay, and tamper tests.
- [BioProAgent](https://github.com/YuyangSunshine/bioproagent): constrained design,
  verification, and correction workflow.
- [LeanDojo-v2](https://github.com/lean-dojo/LeanDojo-v2): proof-environment and
  verifier-boundary engineering reference.
- [LLM-SRBench](https://github.com/deep-symbolic-mathematics/llm-srbench): multi-domain
  equation-discovery benchmark and pluggable searcher interface reference.
- [SRBench](https://github.com/cavalab/srbench): reproducible symbolic-regression
  comparison and containerized evaluator reference.

The exact public URLs for `Fengrru/physicausal` and `Physics-Scaling/GeoPT` were not
resolved. They are not dependencies until their identity and license are confirmed.
The benchmark data and external model services from these references are not hidden
dependencies of the offline core. None of these references is evidence that this project
is scientifically correct.

## Next smallest implementation slice

1. Specify a broader nonintegrable validation set, independent references,
   numerical error budget, and compute ceiling before attempting long-horizon claims.
   Keep oscillator, symmetric fixture, and any real-mission claim separate.
2. Add rights-cleared real-data adapters only after source and data-use gates are closed;
   until then, keep all track claims at their current bounded fixture scope.
3. Reassess the local-only publication boundary from a fresh environment and user review;
   do not push or publish automatically.
