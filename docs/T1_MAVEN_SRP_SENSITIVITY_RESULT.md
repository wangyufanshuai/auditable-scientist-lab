# T1 MAVEN conditional solar-pressure response

The [protocol](T1_MAVEN_SRP_SENSITIVITY_PROTOCOL.json) was committed as
`199ecc4` before any scenario endpoint was computed. Its SHA-256 is
`68352f9158755dca98baeffe51bd08c65112c2542548ff503ec7a62bdae5e470`.
The [snapshot](../artifacts/t1-maven-srp-sensitivity-snapshot.json) and
[audit](../artifacts/t1-maven-srp-sensitivity-audit.json) bind the protocol,
official source page/PDF hashes, NAIF kernels, implementation, all eight
scenario endpoints, controls, and compute budget. External source bytes remain
ignored locally.

| Frozen NAV arc start, ET TDB s | $A_\mathrm{eff}/m=0$ | $0.001$ m²/kg | $0.01$ m²/kg | $0.1$ m²/kg |
|---:|---:|---:|---:|---:|
| 452088000 | 0 m | 10.071 m | 100.708 m | 1007.075 m |
| 457272000 | 0 m | 8.427 m | 84.276 m | 842.756 m |

Each value is the change in the modeled 24-hour endpoint position relative to
the same run with zero SRP coefficient. The four coefficients are **generic
scenarios**, not measured MAVEN properties. The NASA irradiance value is a
solar-flux scale, and the IAU astronomical unit is exact; no spacecraft plate
areas, mass history, attitude, optical coefficients, or mission-fitted SRP
scale factor were supplied. The simple radial model therefore cannot replace
MAVEN's documented flat-plate navigation model. These values are not errors
against NAV or a fitted residual improvement.

The zero-coefficient case reproduces the earlier planetary-force endpoint.
Both 600- and 300-second integrations pass the fixed response-refinement
limit, and the response norms grow across the fixed scenario grid. All seven
engineering checks pass with 3,456 RK4 steps and 2,308 unique SPICE position
queries, under the precommitted budgets of 4,000 and 5,000. This does not
establish a statistical uncertainty interval or an upper bound on actual
MAVEN SRP. Mission-calibrated force history, independent radiometric
measurements, an untouched scientific holdout, and uncertainty review remain
open; the T1 mission Claim stays `unverified`.

`python scripts/verify_t1_maven_srp_sensitivity.py --verify` recomputes the
source-pinned grid locally. The core acceptance verifier checks saved
arithmetic, provenance, and boundaries without those large external files;
when all pinned sources are available it also runs the dynamic check.
