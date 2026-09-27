# T1 offline MAVEN short-arc Run

This optional Run binds the precommitted [MAVEN propagation preflight](T1_MAVEN_PROPAGATION_PREFLIGHT.md)
to one offline Tool/Policy/Provider call. It copies the small NAV state snapshot
into the Run directory and stores the input, source inventory, environment,
seed, tool version, append-only events, trace, evidence references, report and
portable replay manifest. Replay recomputes the two Sun-only RK4 arcs from
saved initial states and checks the held NAV endpoints, step refinement,
energy drift, wrong-sign gravity negative, predeclared limits and Claim status.
Relocation, output tampering, snapshot tampering, wrong-provider and out-of-scope
path controls must fail closed.

The multi-megabyte PDS/NAIF kernels are not copied into the Run. Replay never
queries SPICE; a fresh source check requires
`python scripts/verify_t1_maven_preflight.py --verify` with the three pinned
local kernels. The saved NAV endpoints are reconstructed mission states and
were used as engineering comparison targets. The Run proves deterministic
recomputation of that bounded comparison, not independent flight truth,
full force and maneuver dynamics, a scientific holdout, encounter accuracy,
or mission validity. Its mission Claim remains `unverified`.

Run `python scripts/verify_t1_maven_preflight_run.py --verify` to check the
committed Run, moved replay, mutation controls and policy denials offline.
