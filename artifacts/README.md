# Evidence artifacts

The acceptance package is maintained here as bounded local evidence:

- `acceptance.json` — command receipts with exit code, timestamp, input/version,
  and result path, plus explicit scope and remaining scientific gates.
- `test-report.md` — unit, contract, replay, and failure-path results.
- `demo-transcript.md` — a bounded offline CLI transcript.
- `sample-run.json` — a complete replayable Run with claims and evidence refs.

The current T1 package is `acceptance.json`, `test-report.md`, `demo-transcript.md`, and
`sample-run.json`; T2–T5 have the same four files in their track-specific subdirectories.
These artifacts do not establish real-data validity, publication readiness, or scientific novelty.
