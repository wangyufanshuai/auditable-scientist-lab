# T2 measurement admission: bounded engineering validation

Recorded: 2026-10-05T05:26:27.239112+00:00
Base: `0cf749d8f304e644b5333d191d1685dca128bc81` (Draft PR #14).
Selective T2 source diagnostics imported from `0a7bd5677333cd026947ea8f40892f1db559dbfa`.

| Local gate | Result |
| --- | --- |
| CI-shaped test suite | 340 passed, 14 skipped |
| T2 upstream/admission/packaging tests | 54 passed |
| Admission/registry/packaging/regeneration suite | 80 passed |
| Latest admission CLI/refusal tests | 30 passed |
| Full root acceptance | verified |
| Optional projection | verified, 13 outputs |
| Source-bound fit denial | verified, 7 blockers |
| Common registry binding | verified, 5 targets, 33 unique required receipts |
| Installed wheel | passed, 37 bundled resources |
| Historical/relocated Run replay | all nine committed verified; all nine relocated equal |
| Installed fit callback | refused before invocation |
| Tracked whitespace | passed |

Counts are overlapping test scopes, not additive. Skipped/excluded tests are not
claimed as passed. The default CI exclusions remain explicit in the workflow.
The denial API verifies pinned committed evidence and checks source fingerprints;
it does not dynamically reopen restricted raw PDF/XLSX source files. Upstream
`dynamic_verified_here` fields retain historical source-receipt metadata and do
not describe fresh raw-source reading in this increment.

The verified decision refuses unresolved velocity semantics, experiment coverage,
cross-split duplicate trials, source-use rights, drag constant provenance,
prospective split registration, and the blocked model protocol. Tests prove that
invalid evidence and the valid blocked snapshot never invoke a fitting callback;
raw measurements remain unopened. CLI assessment exits 0 for the valid denial,
required admission exits 3, and invalid evidence exits 1. No numerical fitter or
real-data model result is provided by this version.

- Admission policy SHA256: `885c5e780c41f27eb0ec60375f39c799685b6400abd0edd16195acc8da45930d`
- Admission input snapshot: `bf93c867e5f6862aa09ff7ac42fe775e146d59ae4e4ed0c3f6111ae188367a8e`
- Registry SHA256: `20ca6e6dfe6b3a850e9d5cf91814b15289677e35ca07df0db922a2c078f17f2d`
- Wheel package source snapshot: `ed6e83d52e95a21a09639db0b72e4204932c6e781c59506cc65bd2946bfce66b`
- Wheel source audit timestamp: `2026-10-05T05:20:51.127691+00:00`

The previous registry audit was preserved before explicit regeneration. The new
source-bound refusal and T2 reconciliation rows are root projections; historical
T2P bundle fingerprints are not changed. Clean Git checkout and remote CI are
subsequent gates and are not claimed by this local report.

Scientific validity, causal identification, independent holdout, rights clearance,
expert review, real-data fitting, research status, and publication remain open.
