# T4 finite floating output conformance

This optional receipt compares the repository's floating-point velocity-Verlet
kernel with an independently coded exact rational map over three finite
protocol cases (850 total steps). The checker computes exact `Fraction`
trajectories and compares the existing T3 evaluator's final position and
maximum physical-energy drift with the exact rational map. The saved envelope
is `1e-12` for both output errors. Explicit Euler and a deliberately perturbed
Verlet update are negative controls and must exceed the declared `1e-6`
final-position-error floor.

`python scripts/verify_t4_floating_conformance.py --verify` binds the protocol,
the checker, and `tracks/dynamics.py` source bytes. It rejects stale receipts,
noncanonical rational inputs, changed boundaries, and failed controls. The
checker is independent in its exact arithmetic and negative controls; it calls
the unchanged T3 `_verlet` evaluator only for the positive replay. Historical
T3 source-bound Runs remain replayable because that evaluator is not edited.

This is finite output conformance evidence with an explicit numerical
envelope. It does not inspect every intermediate floating state or prove all
binary floating-point executions, does not
constitute a formal proof of the implementation, and does not validate the
harmonic physical model or real data. The external formal-backend, reviewed
physical-model, real-world validation, and publication gates remain open.
