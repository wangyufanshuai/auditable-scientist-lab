# T5 synthetic protocol text review

T5 v2 parses a deliberately small, line-oriented teaching fixture. The parser
records an exact character span for each step's action, reagent, volume,
temperature, and duration. The fixture embeds its source text and SHA-256 hash;
the shared Run also fingerprints the complete fixture and evaluator source.
The checker re-hashes the embedded UTF-8 text, resolves every span and excerpt,
compares extracted numbers and units with the structured fields, binds each
citation to its own step line, and rejects missing, duplicate, inferred,
reused, or altered citations. Every source line must be parsed and every
parsed step must be represented exactly once. Malformed or extra lines fail
closed rather than being partially ignored.

The domain checker also enforces contiguous step IDs, unique IDs, declared
temperature and total-volume bounds, finite numeric fields, and a narrowly
bounded teaching vocabulary: `mix`/`wait` and `buffer`/`water`. Other actions
or reagents produce `requires-expert-review` and block the result. These are
textual checks against the supplied declaration, not physical or biosafety
validation. The fixture is synthetic, and its source provenance is explicitly
`unverified`; the checker does not accept a self-declared `verified` source.

A passing result means only `text-reviewed` by this deterministic checker and
has evidence level `demo`. `requires_human_review` is always true and
`execution_allowed` is always false. It is not an executable protocol,
experimental validation, citation-rights clearance, or human acceptance.
The committed negative case changes the embedded source text without updating
its hash or field citations; both the hash and location checks reject it.

Future source adapters must independently establish a document revision,
license and allowed use, extraction method, and citation location before a
real-source claim can be considered. Real materials, equipment, safety review,
and human approval remain blocked.

The companion [source-availability receipt](T5_SOURCE_AVAILABILITY.md) records a
clean-checkout fact separately from source-content inventory. It requires the
contract, DOI, expected byte length, and expected SHA-256 to remain present while
the PDF itself is absent. This makes the missing local input an explicit
`blocked-local-source-not-redistributed` state; it is not a failed source hash,
an implicit network fetch, or permission to execute the protocol.
