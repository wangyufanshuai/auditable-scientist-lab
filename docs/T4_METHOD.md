# T4 fixed-rule proof witness

The bounded T4 package declares `conservative-transfer-v1`: for each step,
an exact decimal transfer amount `d` moves from `mass_a` to `mass_b`, with
`0 <= d <= mass_a`. The next state must satisfy `a' = a - d` and
`b' = b + d`, and step numbers must be contiguous. The initial and every
recorded state are checked for nonnegative mass. Decimal inputs are converted
to exact rational values for mass and transition comparisons, so neither
floating-point nor decimal-context rounding can erase a small difference.

Each package must carry exactly one of five checker IDs with their declared
statements: mass conservation, nonnegative state, trajectory hash, transition
rule, and symbolic invariant. Missing, repeated, or mislabeled obligations
block the package. The symbolic check uses SymPy to reduce
`(a-d) + (b+d) - (a+b)` to zero for this fixed rule. The trajectory hash binds
the serialized states, while the transfer witnesses bind each transition.
The input claim status must remain `blocked`; the evaluator alone can return
`bounded-verified` after all checks pass. The shared Run Claim stays
`unverified` because a passing local fixture is not a broad scientific proof.

The committed negative case changes one mass by one unit and recomputes the
trajectory hash. It must still fail mass conservation and the transition
rule. Tests also reject a missing checker, duplicate checker, wrong transfer,
and a change of `1e-13` in the mass, which the earlier rounded check could
have accepted. A separate large-magnitude case checks that the default
decimal arithmetic context cannot erase a one-unit difference either.

This is a machine-checkable witness for one declared transfer rule and a
finite trajectory. It is not a general formal proof backend, a verified
physics model, or evidence of correctness for arbitrary simulation code.
The general proof and transition-model coverage gates remain open.

## T4O oscillator adapter

`T4O` attaches a separate proof receipt to the T3 velocity-Verlet harmonic
oscillator. Its declared input is one finite case (`0 < omega <= 2`,
`0 < dt <= 0.02`, `1 <= steps <= 1000`, `|x0|, |v0| <= 2`) and a seed. The
seed is recorded in the input hash, but the solver itself has no randomness.
The declared output contains the initial state, final position, and maximum
specific-energy drift. The package binds the input, output, and exact bytes of
the local T3 solver source with SHA-256. These hashes detect accidental or
adversarial changes to a saved package; the checker still recomputes the
numerical result rather than accepting a recomputed hash as proof.

The checker requires nine uniquely identified, correctly stated obligations:
input and output hashes, solver-source hash, SI units, initial boundary,
velocity-Verlet replay, closed-form harmonic position, independent fixed-step
RK4 position, and specific-energy drift. The numerical bounds are fixed in
checker code: `2e-3` for closed-form position error, RK4 position difference,
and maximum specific-energy drift. The declared SI units are `m`, `m/s`, `s`,
`s^-1`, and `m^2/s^2`; the acceleration and energy expressions are also
dimension-checked. A missing required obligation is `inconclusive`, a bad or
duplicated one is `failed`, and only all-passed required obligations permit a
`bounded-verified` evaluator result. The optional external formal-prover
obligation is `not_applicable`, because no formal backend is configured. The
shared Run Claim remains `unverified`.

The committed negative control changes the reported final position and
recomputes its output hash. The solver replay must still reject it. This is a
finite, synthetic, machine-checkable numerical witness for a known oscillator
equation. The local RK4 and closed form are independent checks of numerical
agreement, not a proof of the solver implementation, of the physical model,
or of applicability to real data. The physical-model review, external formal
backend, real-data provenance, and human acceptance gates remain open.
