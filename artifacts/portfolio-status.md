# Portfolio status

| Track | State | Acceptance | Open gates | Next step | Public release |
|---|---|---|---|---|---|
| T1 | `reproduced-within-scope` | `artifacts/acceptance.json` | external symbolic engine, real-data provenance, independent backend | decide local-only release boundary | `False` |
| T2 | `reproduced-within-scope` | `artifacts/t2-causal/acceptance.json` | real interventions, causal identification, data rights, external algorithm source rights | add a rights-cleared physical intervention dataset and independent estimator | `False` |
| T3 | `reproduced-within-scope` | `artifacts/t3-dynamics/acceptance.json` | long-horizon/nonintegrable multi-body validation, real-mission provenance, compute budget | bind the finite-horizon perturbed audit to a Run and specify a wider validation set | `False` |
| T4 | `reproduced-within-scope` | `artifacts/t4-proof/acceptance.json` | general formal proof backend, transition model coverage | extend the fixed transfer witness to reviewed transition systems | `False` |
| T5 | `reproduced-within-scope` | `artifacts/t5-protocol/acceptance.json` | real protocol provenance, biosafety review, human acceptance | rights and safety review before real-data use | `False` |

Remote is configured locally but not pushed. The bounded fixture results do not support real-data, novelty, publication, or production claims.
The separate SciPy audit records source tags, installed license notices, pinned wheel hashes,
and a nine-case oscillator cross-check. An optional versioned Tool/Provider Run now
replays that scope separately; the core T3 Run remains SciPy-free and multi-body gates remain open.

T3N is a bounded symmetric three-body subtrack with an analytic orbit and an independent local RK4 cross-check. A separate pinned-SciPy audit checks two short perturbed trajectories; long-horizon/nonintegrable and real-mission gates remain open.

T2P adds a 100-case planar ball-and-floor counterfactual suite with one shared initial state per pair, analytic impact checks, and an ignored-intervention negative control. It remains synthetic simulator evidence only.
