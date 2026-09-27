# T1 MAVEN planetary-force short-arc result

The locally [precommitted protocol](T1_MAVEN_PLANETARY_FORCE_PROTOCOL.json) at
`4b98a57` fixed the force law, GM values, two already-inspected arcs, and
engineering gates before evaluating this model. Its SHA-256 is
`15095d28e9f74896edbd41b3edb1ef9e5eb82d469a29d1a6a70fd3ec3528a394`.
The NAIF `gm_de440.tpc` source was fetched and checksum-pinned, but the large
SPK binaries and GM kernel remain outside Git. The small
[snapshot](../artifacts/t1-maven-planetary-force-snapshot.json) and
[audit](../artifacts/t1-maven-planetary-force-audit.json) bind their hashes,
source code, model, and exact numeric output.

| Start ET, TDB s | Sun-only position error, km | Sun + Earth-Moon/Mars barycenter error, km | Change, km | New velocity error, km/s | 600/300 s difference, km |
|---:|---:|---:|---:|---:|---:|
| 452088000 | 0.535837 | 0.067658 | -0.468179 | 0.000001571 | 0.000000128 |
| 457272000 | 0.284835 | 0.217095 | -0.067740 | 0.000005042 | 0.000000217 |

Both engineering gates pass. The direct and indirect planetary terms cancel
at the Sun, while a deliberately wrong indirect sign fails that identity.
Dynamic `--verify` checks the four pinned local NAIF files and independently
recomputes both arcs. The core acceptance verifier checks saved bytes, vectors,
gate arithmetic, scientific boundaries, and source manifests without requiring
those local kernels; when present, it also runs the dynamic check.

These differences are descriptive. The two endpoints were already inspected
in the Sun-only preflight and come from one reconstructed NAV solution. The
three-body force still omits maneuvers, solar radiation pressure, relativity,
and other bodies. DE440 data may also be upstream of that NAV solution, so this
is no independent-observable validation. A mission-level error budget and
untouched scientific holdout do not exist here. The Claim is `unverified`.

Run `python scripts/verify_t1_maven_planetary_force.py --verify` when the four
pinned local NAIF files are available.
