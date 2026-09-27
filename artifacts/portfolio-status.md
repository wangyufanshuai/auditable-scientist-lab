# Portfolio status

| Track | State | Acceptance | Open gates | Next step | Public release |
|---|---|---|---|---|---|
| T1 | `reproduced-within-scope` | `artifacts/acceptance.json` | external symbolic engine, real-data provenance, independent backend | decide local-only release boundary | `False` |
| T2 | `reproduced-within-scope` | `artifacts/t2-causal/acceptance.json` | real interventions, causal identification, data rights | add a rights-cleared intervention dataset | `False` |
| T3 | `reproduced-within-scope` | `artifacts/t3-dynamics/acceptance.json`; optional `artifacts/t3-external-scipy.json` | multi-body validation, external solver Run integration, compute budget | bind optional solver provenance to a versioned Tool/Provider | `False` |
| T4 | `reproduced-within-scope` | `artifacts/t4-proof/acceptance.json` | formal proof backend, obligation completeness | bind obligations to a formal checker | `False` |
| T5 | `reproduced-within-scope` | `artifacts/t5-protocol/acceptance.json` | real protocol provenance, biosafety review, human acceptance | rights and safety review before real-data use | `False` |

Remote is configured locally but not pushed. The bounded fixture results do not support real-data, novelty, publication, or production claims.
The separate SciPy audit records source tags, installed license notices, exact wheel hashes,
and a nine-case oscillator cross-check; it is not yet evidence inside the T3 Run.
