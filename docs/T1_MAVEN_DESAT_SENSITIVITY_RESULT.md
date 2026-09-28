# T1 MAVEN conditional desaturation sensitivity result

The [protocol](T1_MAVEN_DESAT_SENSITIVITY_PROTOCOL.json) was committed locally
at `25a4e20` before computing any impulse endpoint. Its SHA-256 is
`cc6d520386505f73a2850d3dcee7dc8d3ba08f2e0901e924360c56eb3c78237d`.
The [snapshot](../artifacts/t1-maven-desat-sensitivity-snapshot.json) and
[audit](../artifacts/t1-maven-desat-sensitivity-audit.json) bind the source
paper PDF hash, prior planetary-force result, NAIF kernels, implementation,
every scenario state, controls, and call budget. The paper and kernels remain
outside Git.

| Frozen NAV arc start, ET TDB s | Existing NAV residual | Maximum start-impulse response | Midpoint-impulse response scale |
|---:|---:|---:|---:|
| 452088000 | 67.7 m | 40.61 m | 20.30 m |
| 457272000 | 217.1 m | 40.61 m | 20.30 m |

The impulse is the paper's **estimated average** cruise desaturation
translation, `0.47 mm/s`. Each response is the change in the model's 24-hour
endpoint when that hypothetical impulse is inserted at the arc start or
midpoint, in a radial, transverse, or orbit-normal direction with either sign.
The table gives response magnitudes, not corrected NAV residuals. No direction
or time was selected to improve agreement with NAV. The largest opposite-sign
oddness is about `4.84e-7 km` and the largest 600/300-second response
difference is about `5.07e-7 km`. All eight engineering checks passed using
10,368 RK4 steps and 2,308 unique SPICE planet-position queries, under the
frozen 15,000 and 30,000 limits.

The source paper says TCM-2 was the last executed trajectory-correction burn
before Mars arrival, but also documents roughly weekly attitude-control
desaturations. It does **not** provide event times or vectors for these two
fixed arcs. `0.47 mm/s` is not a worst-case bound or a confidence interval.
The response grid therefore quantifies one omitted-force scale only; it does
not prove that an impulse occurred in either arc, explain either residual,
validate the reconstructed NAV states, or complete an uncertainty budget.
Solar radiation pressure, actual desaturation history, independent tracking
measurements, and scientific holdout remain open. The Claim stays
`unverified`.

`python scripts/verify_t1_maven_desat_sensitivity.py --verify` recomputes the
snapshot from pinned local sources. Core acceptance also checks its saved
arithmetic, source fingerprints, budgets, and boundaries; on a host with the
paper and kernels present, it runs the dynamic check. Static acceptance alone
does not authenticate a fresh SPICE computation.
