# T5 evaluator test report

- Command: `python scripts/verify_acceptance.py`
- Result: independently replayed by the portfolio verifier
- Evidence level: bounded local fixture
- Real-data claim: false
- Research-candidate claim: false

The optional [T5 source-availability receipt](../t5-source-availability-audit.json) records that the rights-declared PBS PDF is intentionally absent from a clean checkout. Its DOI, expected byte length, and SHA-256 remain pinned, but dynamic PDF replay is blocked locally. The receipt preserves the bounded T5 evaluator input identity and leaves source redistribution, independent procedure validation, biosafety review, human acceptance, execution, and the Claim unverified.

The [agent-authored visual review](../t5-pbs-visual-review-audit.json) records page-level observations against the same PDF hash. It flags possible export UI residue inside the page-2 safety box and chemical-glyph/separator ambiguity on page 3, while material cards remain unstructured. These are review leads, not a machine-readable recipe, safety review, human acceptance, or scientific validation; the Claim stays `unverified`.
