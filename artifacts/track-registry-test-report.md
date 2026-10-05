# Track registry increment: local engineering validation

Recorded: 2026-10-05T04:52:21.817352+00:00
Base: `4dbb0ebe9910479000d44af39bcc1281e7c80d76` (`feature/t5-acceptance`).

| Gate | Local result |
| --- | --- |
| Focused registry, packaging, and artifact regeneration tests | 50 passed |
| Current CI-shaped suite | 294 passed, 14 skipped |
| Root acceptance verifier | verified |
| Optional acceptance projection | verified, 13 outputs |
| Saved registry recomputation and root binding | verified, 5 targets, 25 unique receipts |
| Fresh wheel installation outside checkout | passed; 34 bundled resources |
| Nine committed console replays | verified |
| Nine relocated replays | equal |
| Installed registry declaration and explicit evidence root | passed; declaration-only state remains explicit |
| Whitespace check | passed |

The test range follows the existing CI exclusions. Skipped and excluded tests are
not accepted as passed. The registry extension test uses an authored T6 fixture;
T6 is not a shipped scientific capability. Negative controls cover missing problem
fields/units/baselines/holdout, duplicate IDs and JSON keys, evidence changes,
evaluator substitution, promotion flags, unsafe paths, links, and root-row tampering.

Artifact regeneration deliberately invalidates the old audit when timestamps or
source snapshots change. Tests preserve that audit, explicitly generate its
replacement, synchronize, verify domain acceptance, and confirm that a later
receipt mutation prevents writes to proposed acceptance/status outputs.

## Bound source identities

- Registry SHA256: `96a7c230ccd6e4a6670826f0510911e413bc9d81c6210106455535209d272b20`
- Schema SHA256: `b85fef1d6be80aeab4d9d2a1e8afae341bb7487b9548a45819c1c948d303a54e`
- Wheel package source snapshot: `2018acc5c27c8c31d53355c77add3d01350f6765424fdcc21a2c8d659afb6314`
- Wheel audit recorded: `2026-10-05T04:46:51.854609+00:00`

The registry audit fingerprints its verifier, library, projection, portfolio
inputs, and all required receipts. The wheel receipt is retained in
`artifacts/wheel-audit.json`; it records a temporary wheel, not a committed binary.
Clean Git checkout and remote CI are subsequent publication gates and are not
claimed by this local report.

Scientific validity, real data, research-candidate status, rights clearance,
expert/human acceptance, operational execution, and publication remain open gates.
This report certifies bounded engineering checks only.
