# Bounded scientific target registry

The registry declares the problem, observables and units, bounded candidate
families, baselines, evaluation scope, holdout limitations, stopping conditions,
evaluator identity, acceptance package, open gates, and evidence references for
each scientific target. The shipped snapshot describes T1-T5. Identifiers are
extensible; the contract does not enumerate those five IDs.

Registration is a declaration and evidence-binding capability. It does not
register a runtime tool, enforce a solver's candidate budget, dispatch an
experiment, certify units, or prove scientific correctness. The candidate ceiling
is a declared limit for future bounded tooling. Existing runtime tools retain
their own policies. In particular, the registry grants no additional execution
permission and T5 remains read-only.

## Offline commands and installed API

```text
python -m auditable_scientist.track_registry
python -m auditable_scientist.track_registry --registry docs/TRACK_REGISTRY.json
python -m auditable_scientist.track_registry --registry docs/TRACK_REGISTRY.json --root .
python scripts/verify_track_registry.py --verify
python scripts/sync_optional_acceptance.py --verify
```

The first two commands validate declarations only and print
`valid-declaration-only`, with `evidence_checked=false`. They work from an
installed wheel without a checkout. The wheel includes the registry snapshot,
schema, and this document; it does not bundle required acceptance receipts or
restricted source documents. The third command requires an explicit evidence
root and checks portfolio alignment and receipt fingerprints. Missing evidence
fails. The script command additionally compares the recomputed results with the
saved audit and checks the root acceptance row. No command grants scientific,
rights, human-review, execution, or publication approval.

Python callers can use `bundled_registry()`, `validate_contract(registry)`, and
`validate_evidence(registry, evidence_root)` from
`auditable_scientist.track_registry`. Results from `validate_evidence` describe the
current supplied files; comparison to the committed audit is performed by
`scripts/verify_track_registry.py`. The module CLI does not claim saved-audit
verification.

## Adding a target

1. Define the scientific question, units, candidate families and ceiling,
   baselines, evaluation scope, holdout limitations, and stop conditions.
2. Supply a unique ID, versioned evaluator ID, bounded acceptance package, required
   receipt references, and unresolved gates. Keep all global and per-target
   promotion permissions closed under this v1 contract.
3. Add matching entries to the supplied portfolio status and evaluator portfolio.
   A declaration without those entries and a matching acceptance package cannot
   pass evidence validation. The extension contract test registers a fixture T6;
   T6 is not a shipped scientific result.
4. Implement the domain evaluator and its runtime adapter separately, with
   meaningful negative controls and replay evidence. The current portfolio
   generator remains specific to T1-T5 and must be extended deliberately.
5. Review the diff, preserve any previous audit before regenerating it, synchronize
   optional acceptance, and rerun domain, installed-wheel, and clean-checkout gates.
   Copy the updated registry snapshot into the packaged resource path. Packaging
   tests require byte equality.

`source_rights_status` and `human_review_status` are authored annotations with
references, not machine-certified decisions. Partial review annotations require
bound evidence references; approved rights and completed human approval states
are unavailable in v1. Rights and human references must also be required
receipts. Hashing an authored review does not turn it into independent approval.
T5's agent visual observations do not satisfy human acceptance or biosafety.

## Audit and regeneration

The audit binds registry/schema bytes, validator and verifier source bytes,
portfolio inputs, and each unique required receipt. Shared references are allowed
and fingerprinted once. Evidence paths must be canonical, relative paths within
the supplied root. Traversal, Windows aliases/streams, symlinks, junctions,
hard links, missing files, duplicate JSON keys, duplicate IDs, and ambiguous
acceptance check names fail validation.

All required receipts use byte hashes except root-style acceptance packages.
For those packages, the verifier hashes canonical JSON containing every field
except the single `bounded-track-registry` check row. This avoids recursive
hashing: the audit is referenced by that row. The verifier separately requires
the row to equal a projection containing the canonical SHA256 of the entire saved
audit, its timestamp, verifier command, success code, and output path. Other
acceptance rows remain in the canonical hash. Duplicate registry rows fail.

Optional acceptance synchronization constructs its complete proposed outputs in
memory, recomputes the registry against those bytes, compares the saved audit,
and only then inserts the registry row and writes outputs. This permits the base
artifact generator to omit optional rows temporarily without accepting stale or
modified evidence. Verification never regenerates an audit silently. The base generator may change
receipt timestamps and source snapshots: synchronization must then reject the old
audit. After reviewing those changes and preserving the old audit outside its
canonical path, run `python scripts/verify_track_registry.py --write`, then
`python scripts/sync_optional_acceptance.py --write`, and finally both verifiers.
The explicit audit writer fingerprints the complete proposed optional projection;
it does not bypass domain verification or overwrite a different existing audit.

Receipt hashes attest to file identity. Domain verifiers still establish bounded
engineering behavior; scientific holdout, source rights, expert review, and
publication remain separate gates. Historical Run fingerprints remain pinned:
this capability lives in a new module and an optional acceptance projection.
