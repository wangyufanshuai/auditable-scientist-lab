"""The portable ephemeris Run must not promote saved geometry to a mission claim."""

from __future__ import annotations

from copy import deepcopy
import json

import pytest

from auditable_scientist.runtime.canonical import canonical_hash
from auditable_scientist.runtime.replay import ReplayMismatch
from scripts.verify_t1_de440s_run import (
    RUNS, SNAPSHOT, input_payload, recompute_geometry, replay_run,
)


def test_saved_state_geometry_rejects_changed_arrival_gap() -> None:
    snapshot = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    baseline = recompute_geometry(snapshot)
    assert baseline["case_count"] == 2
    assert baseline["mission_claim_status"] == "unverified"
    assert baseline["dynamic_kernel_recomputed"] is False
    changed = deepcopy(snapshot)
    changed["cases"][0]["arrival_position_gap_km"] += 1.0
    with pytest.raises(ReplayMismatch, match="arrival_position_gap_km"):
        recompute_geometry(changed)


def test_committed_snapshot_run_replays_without_kernel() -> None:
    run_dir = RUNS / f"run-t1-de440s-{canonical_hash(input_payload())[:16]}"
    receipt = replay_run(run_dir)
    assert receipt["verified"] is True
    saved = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
    assert saved["claims"][0]["status"] == "unverified"
    assert saved["claims"][0]["holdout_verified"] is False
    assert saved["observations"][0]["summary"]["scope"] == "ephemeris-model-geometry-only"
