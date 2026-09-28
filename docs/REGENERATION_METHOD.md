# Regenerating bounded portfolio artifacts

The base `scripts/generate_track_artifacts.py` file is fingerprinted by seven committed track Runs. Editing it solely to list later optional receipts would invalidate those historical source snapshots. Keep it pinned when refreshing this accepted generation.

In a disposable copy of the repository, run these commands in order with the pinned replay environment:

```powershell
python scripts/generate_track_artifacts.py
python scripts/sync_optional_acceptance.py --write
python scripts/verify_acceptance.py
```

The second command projects the saved T2 independent-endpoint, T3 finite-horizon, T4 exact-linear, and T4 exact-Verlet receipts into the track acceptance packages and rebuilds portfolio status from `docs/PORTFOLIO_STATUS_CONTRACT.json` and `docs/PORTFOLIO_STATUS_NARRATIVE.md`. It checks receipt schema, status, source hashes, timezone, and bounded-claim flags before writing. The final command performs deeper source and replay checks, including a fresh exact-Verlet certificate check. Core tests run this complete sequence in a copied checkout so historical CLI Runs must still replay.

Use `python scripts/sync_optional_acceptance.py --verify` for a read-only check of current artifacts. This regeneration establishes engineering consistency only; it does not close real-data, source-rights, scientific, biosafety, or human-review gates.
