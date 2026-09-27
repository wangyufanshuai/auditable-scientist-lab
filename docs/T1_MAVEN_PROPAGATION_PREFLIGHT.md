# T1 MAVEN short-arc propagation preflight

This optional engineering comparison was fixed in local Git before the two
MAVEN NAV endpoints were queried. The exact [protocol](T1_MAVEN_PROPAGATION_PREFLIGHT.json)
has SHA-256 `a37b11b983a9ea0765682d4457c8eed9b378566262fa3adc478d7d60ef9e5a47`
at commit `27cc842553d3ff888df092883ff9f50225e92aae`. That local commit
establishes the order of this project's work; it is not an independent
scientific preregistration service or proof that the NAV product was unseen.

The [PDS4 MAVEN cruise product](T1_MAVEN_MISSION_SOURCE.md) supplies only
the initial state and a 24-hour endpoint for each arc. The fixed TDB ET starts
are `452088000` and `457272000` seconds past J2000. Both SPK segments are
Sun-centered body `-202` in J2000. A separately implemented classical RK4
solver integrates $\ddot{\mathbf r}=-\mu_\odot\mathbf r/|\mathbf r|^3$
with the declared DE440 solar GM and 600-second steps. A 300-second run checks
step refinement; specific two-body energy is checked for drift. All vectors
use km and km/s. No online service is used by evaluation or verification.

| Arc start ET (s) | NAV endpoint position error (km) | Speed-vector error (km/s) | Wrong-sign position error (km) |
|---:|---:|---:|---:|
| 452088000 | 0.535837 | 0.00001234 | 26308.94 |
| 457272000 | 0.284835 | 0.00000664 | 22015.82 |

Both arcs pass the **predeclared engineering** limits of 100 km position,
0.01 km/s velocity, 0.001 km refinement difference, and $10^{-8}$ relative
two-body energy drift. The wrong-sign gravity control fails the position gate.
The exact states, thresholds, measured residuals and source hashes are in the
[snapshot](../artifacts/t1-maven-preflight-snapshot.json) and
[audit](../artifacts/t1-maven-preflight-audit.json). These are two short,
smooth, Sun-centered arcs. Their NAV states are a reconstructed mission
solution, not an independently measured ground truth. The initial condition
comes from that same solution. The small 24-hour residual does not demonstrate
an accurate launch window, Mars capture, full-mission transfer, ephemeris
independence, or a complete uncertainty model.

Planetary gravity, maneuvers, solar radiation pressure and relativity were
excluded by the fixed model. The scientific holdout and mission-validation
gates remain false; the Claim remains `unverified`. Subsequent work should
freeze a higher-fidelity force and maneuver model, choose a separately
reviewed time/mission split, compare against independently archived
observables where available, and obtain mission-domain review before any
validated-mission statement.

With the three checksum-pinned binaries already downloaded under `data/naif`,
run `python scripts/verify_t1_maven_preflight.py --verify` for the dynamic
SPICE and propagation check. Core acceptance may inspect the saved JSON
without those binaries; that static check must not be presented as a fresh
mission recomputation.
