# T1 offline DE440s snapshot Run

This optional Run copies the two-case fixed-date geometry snapshot into its own
directory and binds it to an offline Tool/Policy/Provider call, a source inventory,
an event chain, and a portable replay manifest. The tool independently recomputes
the ideal Hohmann arrival time and position gap from the saved Earth and
Mars-barycenter state vectors. It also rejects a changed snapshot and a changed
result during moved-run replay.

The NAIF kernel is not copied into the Run. Replay checks the saved state-vector
calculations and the original source audit, but does not query DE440s again. A
dynamic kernel check remains a separate `verify_t1_de440s_ephemeris.py --verify`
step where the pinned kernel and `spiceypy` are installed. The state vectors are
model-derived ephemeris data, not measurements of a spacecraft. No spacecraft
propagation, Mars-center encounter, independent mission comparison, scientific
holdout, or human scientific review is supplied. The mission Claim stays
`unverified` and this Run does not authorize a mission-validity claim.

Run `python scripts/verify_t1_de440s_run.py --verify` to check the committed Run
and its moved-run and mutation controls without the 31 MiB kernel.
