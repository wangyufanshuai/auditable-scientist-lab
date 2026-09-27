# Portfolio status

| Track | State | Acceptance | Open gates | Next step | Public release |
|---|---|---|---|---|---|
| T1 | `reproduced-within-scope` | `artifacts/acceptance.json` | external symbolic engine, real-data provenance, versioned console-script routing, dated mission ephemeris | route the console script to the versioned CLI without losing legacy replay, then seek a rights-cleared dated ephemeris | `False` |
| T2 | `reproduced-within-scope` | `artifacts/t2-causal/acceptance.json` | real interventions, causal identification, data rights, external algorithm source rights | add a rights-cleared physical intervention dataset and independently validated real-data estimator | `False` |
| T3 | `reproduced-within-scope` | `artifacts/t3-dynamics/acceptance.json` | long-horizon/nonintegrable multi-body validation, real-mission provenance, long-horizon compute budget | preregister a separate nonintegrable long-horizon suite and rights-cleared mission comparison | `False` |
| T4 | `reproduced-within-scope` | `artifacts/t4-proof/acceptance.json` | general formal proof backend, reviewed physical transition model, real-world validation | review a physical model and add independent source-backed validation | `False` |
| T5 | `text-demo-within-scope` | `artifacts/t5-protocol/acceptance.json` | independent protocol source and rights, biosafety review, human acceptance | add a rights-cleared document adapter with independent citation checks | `False` |

Remote is configured locally but not pushed. The bounded fixture results do not support real-data, novelty, publication, or production claims.
The core offline T1 orbit audit (`artifacts/t1-core-orbit-audit.json`) recomputes nine synthetic two-body transfers with a dependency-free RK4 propagator, bounded step refinement, invariant checks, and a repulsive-force negative control. Core acceptance dynamically reruns it. Its vis-viva departure state still comes from the analytic model, and the historical T1 CLI Run remains analytic; independent propagation has not yet been integrated into that Run.
A separate versioned offline Tool/Provider Run (`artifacts/t1-core-orbit-run-audit.json`) binds that numerical result to the shared Policy, Agent, Memory, Evaluator, Evidence, Event and Trace contracts. It verifies source and dataset snapshots, a moved replay, two tamper negatives and policy denials. This earlier companion Run remains independently replayable.
The versioned package CLI (`python -m auditable_scientist`) now creates a single T1 Run with the bounded analytic candidate tool and the independent RK4 propagation tool. The [combined CLI audit](t1-combined-cli-audit-v3.json) checks all five commands, legacy replay, relocation, and five tamper controls; the wheel audit repeats the new and old Run families outside the checkout. `inspect` and `export-report` verify v2 replay before showing or copying output, including when the numerical file is missing. The `auditable-scientist` console script still routes to the historical analytic CLI, so its explicit version-routing gate remains open.
An optional pinned-SciPy T1 audit integrates ten circular two-body transfers to an event-detected apoapsis, including one NASA-rounded-axis sensitivity case. A separate shared Tool/Policy/Provider Run binds this computation, moved replay, license snapshots and tamper negatives. Core acceptance checks saved provenance and replay statically; the separate `--verify` command recomputes in the pinned solver environment. It does not close mission, source-rights, or core CLI Run backend gates.
The separate SciPy audit records source tags, installed license notices, pinned wheel hashes,
and a nine-case oscillator cross-check. An optional versioned Tool/Provider Run now
replays that scope separately; the core T3 Run remains SciPy-free and multi-body gates remain open.

T3N is a bounded symmetric three-body subtrack with an analytic orbit and an independent local RK4 cross-check. A separate pinned-SciPy Tool/Provider Run replays two short perturbed trajectories and rejects altered result or license bytes; long-horizon/nonintegrable and real-mission gates remain open.
The [expanded finite-horizon audit](t3-horizon-grid-audit.json) admits two smooth, synthetic 0.75-period cases under a fixed 12,000 DOP853-call and 35,000 fixed-step budget. Both one-period stress cases trigger the $0.5a$ close-approach event and are excluded from accuracy claims. The grid was selected after a feasibility preflight, so its inherited holdout label does not mean untouched scientific validation.

T2P adds a 100-case planar ball-and-floor counterfactual suite with one shared initial state per pair, analytic impact checks, and an ignored-intervention negative control. It remains synthetic simulator evidence only.

An optional independent impact-to-impact endpoint estimator cross-checks the 100 T2P cases and 24 varied holdout states. The [audit](t2-independent-endpoint-audit.json) and mutation tests bind that synthetic computation; real interventions, observational identification, source rights, and external validation remain open.

An offline Tool/Policy/Provider Run now binds the estimator to both input snapshots, one guarded call, event chain, moved replay, and mutation controls. Its real-world Claim stays `unverified`; [the Run audit](t2-independent-run-audit.json) remains synthetic engineering evidence.

T4O adds an oscillator proof receipt tied to the T3 velocity-Verlet source and a fixed finite grid. A checker verifies units, hashes, boundaries, solver replay, analytic and RK4 references, and energy drift. The formal-prover obligation is not applicable; reviewed physics and external validation remain open.

T4 also has an optional exact rational linear-invariant proof slice: two coefficient-identity certificates are rechecked independently with `Fraction`, and a leaky system is rejected. This establishes the declared linear identities only. It does not validate a physical transition model or close the general formal-backend gate.

A separate offline Tool/Policy/Provider Run now binds that exact slice to a source and input snapshot, one guarded call, event chain, moved replay, and mutation controls. Its physical Claim stays `unverified`; [the audit](t4-linear-run-audit.json) is engineering evidence for the declared matrices only.

T5 is a synthetic text-review demonstration. Each field is located in an embedded LF document with a SHA-256 hash and exact character span. An altered document is rejected. Source rights, real materials, safety, and human acceptance are unverified; execution remains forbidden.
