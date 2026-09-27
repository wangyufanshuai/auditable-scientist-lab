# T4 evaluator test report

- Command: `python scripts/verify_acceptance.py`
- Result: independently replayed by the portfolio verifier
- Evidence level: bounded local fixture
- Real-data claim: false
- Research-candidate claim: false

The optional exact linear-invariant audit proves two declared rational linear
identities for all states and controls, and rejects a leaky negative control.
`python scripts/verify_t4_linear_formal.py --verify` and the independent
`python scripts/check_t4_linear_certificate.py` both passed. Twelve targeted
tests cover a new matrix and malformed or forged certificates. This is a
mathematical statement about declared matrices, not physical-model validation.

The separate `python scripts/verify_t4_linear_run.py --verify` binds the exact
certificate to one policy-guarded Tool/Provider Run. Replay checks its input,
source, environment, seed, event chain, and output; relocation and tamper controls
pass. The Run's physical Claim remains `unverified`.
