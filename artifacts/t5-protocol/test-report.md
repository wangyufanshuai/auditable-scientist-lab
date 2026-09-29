# T5 evaluator test report

- Command: `python scripts/verify_acceptance.py`
- Result: independently replayed by the portfolio verifier
- Evidence level: bounded local fixture
- Real-data claim: false
- Research-candidate claim: false

The optional [T5 source-availability receipt](../t5-source-availability-audit.json) records that the rights-declared PBS PDF is intentionally absent from a clean checkout. Its DOI, expected byte length, and SHA-256 remain pinned, but dynamic PDF replay is blocked locally. The receipt preserves the bounded T5 evaluator input identity and leaves source redistribution, independent procedure validation, biosafety review, human acceptance, execution, and the Claim unverified.
