# T1 MAVEN planetary-force diagnostic protocol

This protocol freezes one next engineering comparison before evaluating its
Sun-plus-two-planet model. It reuses the two NAV arcs and endpoints already
inspected in the [Sun-only preflight](T1_MAVEN_PROPAGATION_PREFLIGHT.md), so it
is not an untouched holdout or independent observation. There is no parameter
fit or post-hoc epoch choice. A worsening against the Sun-only model will be
reported as measured.

The model uses the point-mass Sun, Earth-Moon barycenter (NAIF 3), and Mars
barycenter (NAIF 4), with the indirect planetary acceleration required by a
Sun-relative frame. Planetary positions come from checksum-pinned DE440s at
each RK4 stage. The three GM values come from NAIF's
[DE440 GM kernel](https://naif.jpl.nasa.gov/pub/naif/generic_kernels/pck/gm_de440.tpc),
whose fetched bytes have SHA-256
`924ddf4fb9ead9fe8a1aa55780bcabde40b09d00065d58226e24b68d8092f140`.
The [machine-readable protocol](T1_MAVEN_PLANETARY_FORCE_PROTOCOL.json) fixes
the coordinates, source hashes, time points, force law, integration steps,
engineering gates, and scientific boundaries.

This is still a deliberately incomplete force model. It excludes maneuvers,
solar radiation pressure, relativity, and other bodies. The NAV trajectory is
a reconstructed solution, and the same DE440 family may influence that
solution. Passing the numeric gates would not validate the MAVEN mission
trajectory or close the scientific holdout, independent observable, uncertainty
budget, or expert review gates. The Claim must remain `unverified`.
