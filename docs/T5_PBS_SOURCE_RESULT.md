# T5: rights-declared PBS source intake

The [source contract](T5_PBS_SOURCE_CONTRACT.json) fixes the official
[protocols.io PDF](https://www.protocols.io/view/phosphate-buffered-saline-pbs-p4rdqv6.pdf),
DOI [10.17504/protocols.io.p4rdqv6](https://doi.org/10.17504/protocols.io.p4rdqv6),
author Katy M Monteith, publication and last-modified date 2018-05-14,
protocol ID 12145, byte length 458,059, and SHA-256
`184b4d211aa8c1a2fcde0eb06a2fd8ae57727c28f1a2b41e5fbfd94b5f8c1271`.
The PDF itself says it is offered under a Creative Commons Attribution
License and requires credit to the author and source. It does not specify a
license version. The external PDF remains ignored locally; the project stores
only its manifest, short citation anchors, page-text hashes, and step hashes.

The [audit](../artifacts/t5-pbs-source-audit.json) checks all three PDF pages
with the pinned `pypdf` reader, including 11 text anchors, six ordered
numbered steps, document/license identity, and source hashes. Pages 1–3 were
also visually inspected against the extraction, because PDF text can reorder
or misrender glyphs. The page-3 extraction contains private-use glyphs around
some chemical notation, so it is **not** an approved machine-readable recipe.

The document contains a 1×/10× concentration choice, a pH alternative,
concentrated acid, optional DEPC, an SDS warning, and autoclaving. Its “we use
this protocol and it’s working” line is the author's self-report, not an
independent reproduction. The current T5 teaching parser cannot faithfully
map these branches, materials, and safety constraints into its five-field
line grammar. The audit therefore records a real, rights-declared **source
inventory** only. It does not generate a protocol, authorize execution,
perform biosafety review, or raise the Claim above `unverified`.

`python scripts/verify_t5_pbs_source.py --verify` reopens the pinned local
PDF. The portfolio acceptance verifier independently checks the committed
source and citation inventory and dynamically reruns the PDF check when that
file and the optional reader are available. Mutated PDF bytes, citation
locations, step hashes, license metadata, or execution/Claim flags are
rejected.
