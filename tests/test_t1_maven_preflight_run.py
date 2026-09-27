"""Saved NAV short-arc Run must replay without promoting mission validity."""

from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import sys

import pytest

from auditable_scientist.runtime.canonical import canonical_hash
from auditable_scientist.runtime.replay import ReplayMismatch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from verify_t1_maven_preflight_run import (  # noqa: E402
    RUNS, SNAPSHOT, input_payload, recompute_preflight, replay_run,
)


def test_saved_nav_endpoint_change_fails_recomputation() -> None:
    snapshot = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    baseline = recompute_preflight(snapshot)
    assert baseline["arc_count"] == 2
    assert baseline["mission_claim_status"] == "unverified"
    assert baseline["dynamic_kernel_recomputed"] is False
    changed = deepcopy(snapshot)
    changed["arcs"][0]["held_nav_endpoint_sun_state_km_kms"][0] += 1.0
    with pytest.raises(ReplayMismatch, match="metric or negative"):
        recompute_preflight(changed)


def test_committed_maven_run_replays_and_keeps_claim_unverified() -> None:
    run_dir = RUNS / f"run-t1-maven-{canonical_hash(input_payload())[:16]}"
    receipt = replay_run(run_dir)
    assert receipt["verified"] is True
    saved = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
    assert saved["claims"][0]["status"] == "unverified"
    assert saved["claims"][0]["holdout_verified"] is False
    assert saved["observations"][0]["summary"]["scope"] == "precommitted-engineering-comparison-only"
