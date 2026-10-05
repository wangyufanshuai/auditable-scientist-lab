# T2 measurement admission and refusal before fitting

This increment connects the common target registry to the existing T2 source
intake diagnostics. It adds an executable refusal boundary for the supported
`guarded_fit` entry point, before raw measurements are opened or a fitting
callback is invoked. It does not add a projectile fitter or certify a scientific
model. The current source snapshot remains blocked and has no approval state.

## Sources integrated into this branch

The source diagnostic files, contracts, receipts, and their tests were imported
byte-for-byte from this project's `feature/t2-reconciliation-acceptance` commit
`0a7bd5677333cd026947ea8f40892f1db559dbfa` (Draft PRs #7, #9, #10).
The model protocol and verifier use that stack's duplicate-trial boundary.
No upstream PR was merged. Source directories, raw PDF/XLSX files, and the dirty
primary checkout were preserved. T4/T5 and registry changes remain inherited
from the separate PR #14 base.

## Offline interface

```text
python -m auditable_scientist.tracks.measurement_admission --root .
python -m auditable_scientist.tracks.measurement_admission --root . --require-admission
python scripts/verify_t2_measurement_admission.py --verify
```

The assessment command exits 0 only when the evidence is valid enough to produce
an inspectable denial. It prints `blocked-before-model-fit`, with every promotion
boundary false. `--require-admission` prints the same decision and exits 3 for
that denial. Missing, changed, unsafe, or malformed inputs exit 1. Neither zero
exit status nor a verified denial means fitting was admitted.

The installed wheel bundles the admission policy, JSON Schema, and this document;
it requires an explicit evidence checkout. Required receipt bytes and restricted
raw documents are not bundled. No network is required.

Python callers may use `evaluate(evidence_root)` for the decision and
`guarded_fit(evidence_root, fit_callback)` to guard a future numerical fitter.
`guarded_fit` raises `MeasurementAdmissionDenied` with a deep-copied decision and
never invokes the callback on this source snapshot. This is an API boundary for
callers that use the entry point, not an operating-system sandbox for arbitrary
external Python code. The current version cannot be turned into an approval by
setting a caller flag or editing a receipt: policies must equal the shipped,
versioned source-bound snapshot. A successor needs independently reviewed evidence,
a new policy, meaningful approval/denial tests, and a fitted-model implementation.

## Seven independently described blockers

| Blocker | Current inspectable evidence | Required next evidence |
| --- | --- | --- |
| Velocity role | Workbook header is ambiguous; article describes both a light gate and fitting | Column-level mapping tied to each trial, inspectable primary-source statements, and uncertainty role |
| Coverage | 30 inventoried trials versus 82 reported experiments | Account for the selected scope and every exclusion; do not invent the other 52 trials |
| Independence | Identical 22/23 observation payloads cross the current split | Source identity review and a prospectively frozen independent split; no silent deduplication |
| Source use rights | Reconciliation explicitly leaves rights clearance unresolved | Confirm permitted analysis use separately from redistribution; an article licence or byte hash is insufficient |
| Drag constants | Constant provenance has not been reviewed | Inspectable source and unit/uncertainty review for diameter, mass, density, and viscosity |
| Prospective split | The local whole-trial draft is not externally registered | Precommitted scope/split and comparison rules before fitting; no holdout tuning |
| Protocol | Both velocity input modes explicitly deny fitting | A reviewed successor protocol only after the earlier blockers are closed |

The dataset remains observational; closing these predictive admission gates would
not supply real intervention evidence or causal identification. No model is fitted
in this increment. Numerical values in the decision are previously committed
inventory metadata, not new raw-data fitting or scientific validation.

## Evidence and validation

The policy binds fourteen input files by exact bytes/SHA256: the source, v0,
independence and reconciliation contracts/audits, model protocol, and five verifier
sources. The admission API also rechecks each upstream audit's committed source
fingerprints, unique trial inventory, split partition, duplicate classification,
and coverage arithmetic. It never opens the ignored PDF/XLSX files.

The verifier recomputes all three upstream committed diagnostics and the decision,
then calls the guard with a forbidden fitting callback. Its audit records the
refusal only when the callback remains untouched. Saved-audit verification compares
canonical JSON so numeric/boolean type substitutions cannot forge false flags.
Root acceptance dynamically verifies the decision; the registry binds the new
receipts and contracts. Future receipt changes require deliberate audit regeneration.

Unit/contract tests cover missing/changed input files, caller flag and hash spoofing,
mutated denial reasons, callback side effects, raw-source reads, relocation, policy
resources, CLI exits, and refusal before synchronization writes. Installed-wheel
validation repeats the CLI denial and a guarded callback rejection outside the
checkout, along with all historical and relocated Run replays.
