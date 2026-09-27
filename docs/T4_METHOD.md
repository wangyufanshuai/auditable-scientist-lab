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
