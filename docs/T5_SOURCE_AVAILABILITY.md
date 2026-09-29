# T5 source availability and rights boundary

The T5 PBS source contract records the DOI, the official PDF URL, the expected
byte length, and the expected SHA-256 for the rights-declared protocols.io
document. The PDF is intentionally excluded from the repository because the
bounded project stores a source inventory and citation contract rather than a
redistributed document.

`python scripts/verify_t5_source_availability.py --verify` checks that the
clean checkout contains no local PDF at
`data/references/t5_pbs/protocols_io_p4rdqv6.pdf`, while the DOI, expected byte
length, expected SHA-256, and source-contract hash remain pinned. The resulting
status is `blocked-local-source-not-redistributed`: dynamic PDF extraction and
replay cannot run in this checkout.

The existing source and cross-reader receipts remain useful as committed
inventory evidence. They do not substitute for the missing PDF, and they do
not authorize an independent procedure validation, protocol execution,
biosafety review, human acceptance, or a scientific claim. The source's
license declaration is recorded separately from a decision to redistribute the
document. The Claim therefore remains `unverified`.

This receipt is attached to the bounded T5 evaluator input only to preserve
acceptance-package identity. It does not promote the evaluator's synthetic
fixture or the historical read-only source Run.
