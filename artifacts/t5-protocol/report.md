# T5 bio-chem protocol verifier checkpoint

- Evaluator: `bio-chem-protocol-v1`
- Status: `validated-reproduction` for declarative constraints in a local fixture
- Positive gate: ordered steps, temperature bounds, volume budget, and provenance checks pass
- Negative gate: blocked reagent provenance fails verification
- Execution: permanently `false` in this slice

This component verifies protocol text and metadata only. It does not schedule, control, or
authorize wet-lab work; real data, biosafety review, and human acceptance remain blocked.
