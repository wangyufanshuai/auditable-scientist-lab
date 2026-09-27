# Portfolio status

| Track | State | Acceptance | Open gates | Next step | Public release |
|---|---|---|---|---|---|
| T1 | `reproduced-within-scope` | `artifacts/acceptance.json` | external symbolic engine, real-data provenance, independent backend in the core Run, dated mission ephemeris | attach the optional numerical cross-check to a policy-guarded Run and seek a rights-cleared ephemeris | `False` |
| T2 | `reproduced-within-scope` | `artifacts/t2-causal/acceptance.json` | real interventions, causal identification, data rights, external algorithm source rights | add a rights-cleared physical intervention dataset and independent estimator | `False` |
| T3 | `reproduced-within-scope` | `artifacts/t3-dynamics/acceptance.json` | long-horizon/nonintegrable multi-body validation, real-mission provenance, compute budget | specify a wider validation grid and finite compute budget before long-horizon claims | `False` |
| T4 | `reproduced-within-scope` | `artifacts/t4-proof/acceptance.json` | general formal proof backend, reviewed physical transition model, real-world validation | review a physical model and add independent source-backed validation | `False` |
| T5 | `text-demo-within-scope` | `artifacts/t5-protocol/acceptance.json` | independent protocol source and rights, biosafety review, human acceptance | add a rights-cleared document adapter with independent citation checks | `False` |

Remote is configured locally but not pushed. The bounded fixture results do not support real-data, novelty, publication, or production claims.
An optional pinned-SciPy T1 audit now integrates ten circular two-body transfers to an event-detected apoapsis, including one NASA-rounded-axis sensitivity case. Its core acceptance check is static; the separate `--verify` command recomputes in the pinned solver environment. It does not close mission, source-rights, or core-Run backend gates.
The separate SciPy audit records source tags, installed license notices, pinned wheel hashes,
and a nine-case oscillator cross-check. An optional versioned Tool/Provider Run now
replays that scope separately; the core T3 Run remains SciPy-free and multi-body gates remain open.

T3N is a bounded symmetric three-body subtrack with an analytic orbit and an independent local RK4 cross-check. A separate pinned-SciPy Tool/Provider Run replays two short perturbed trajectories and rejects altered result or license bytes; long-horizon/nonintegrable and real-mission gates remain open.

T2P adds a 100-case planar ball-and-floor counterfactual suite with one shared initial state per pair, analytic impact checks, and an ignored-intervention negative control. It remains synthetic simulator evidence only.

T4O adds an oscillator proof receipt tied to the T3 velocity-Verlet source and a fixed finite grid. A checker verifies units, hashes, boundaries, solver replay, analytic and RK4 references, and energy drift. The formal-prover obligation is not applicable; reviewed physics and external validation remain open.

T5 is a synthetic text-review demonstration. Each field is located in an embedded LF document with a SHA-256 hash and exact character span. An altered document is rejected. Source rights, real materials, safety, and human acceptance are unverified; execution remains forbidden.
