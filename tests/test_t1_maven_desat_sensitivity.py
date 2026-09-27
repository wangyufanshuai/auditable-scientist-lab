"""Reject altered conditional impulse evidence even with a recomputed receipt hash."""

from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json

import pytest

from scripts import verify_acceptance


@pytest.fixture
def saved_evidence(monkeypatch: pytest.MonkeyPatch) -> tuple[dict, dict]:
    # Exercise the offline static contract independently of the optional SPICE run.
    original_find_spec = verify_acceptance.importlib.util.find_spec
    monkeypatch.setattr(
        verify_acceptance.importlib.util, "find_spec",
        lambda name: None if name == "spiceypy" else original_find_spec(name),
    )
    audit = verify_acceptance.load("artifacts/t1-maven-desat-sensitivity-audit.json")
    snapshot = verify_acceptance.load("artifacts/t1-maven-desat-sensitivity-snapshot.json")
    assert verify_acceptance.verify_optional_t1_maven_desat_sensitivity(audit, snapshot)[
        "dynamic_verified_here"] is False
    return deepcopy(audit), deepcopy(snapshot)


def _receipt_hash(snapshot: dict) -> str:
    payload = (json.dumps(snapshot, sort_keys=True, separators=(",", ":"),
                          allow_nan=False)+"\n").encode("utf-8")
    return sha256(payload).hexdigest()


@pytest.mark.parametrize("mutation", [
    "snapshot_hash", "source_fingerprint", "endpoint", "direction",
    "injection", "budget", "scenario_metric", "claim_promotion",
])
def test_static_acceptance_rejects_desat_tampering(
        saved_evidence: tuple[dict, dict], mutation: str) -> None:
    audit, snapshot = saved_evidence
    arc = snapshot["arcs"][0]
    middle_cases = arc["step_data"]["600.0"]["cases"]
    if mutation == "snapshot_hash":
        snapshot["reader"]["toolkit"] = "altered"
    elif mutation == "source_fingerprint":
        audit["source_files"][0]["sha256"] = "0"*64
    elif mutation == "endpoint":
        middle_cases["0.5:radial:1"]["endpoint_state_km_kms"][0] += 0.001
    elif mutation == "direction":
        impulse = middle_cases["0.5:radial:1"]["impulse_vector_km_s"]
        middle_cases["0.5:radial:1"]["impulse_vector_km_s"] = impulse[1:] + impulse[:1]
    elif mutation == "injection":
        middle_cases["0.5:radial:1"]["injection_state_km_kms"][0] += 100
    elif mutation == "budget":
        snapshot["observed_budget"]["rk4_steps_total"] += 1
        audit["observed_budget"] = snapshot["observed_budget"]
    elif mutation == "scenario_metric":
        arc["scenario_pairs"][0]["positive_response_norm_km"] += 0.01
    else:
        snapshot["scientific_boundaries"]["claim_status"] = "validated"
    if mutation != "snapshot_hash":
        audit["snapshot_sha256"] = _receipt_hash(snapshot)
    with pytest.raises(ValueError, match="MAVEN desat"):
        verify_acceptance.verify_optional_t1_maven_desat_sensitivity(audit, snapshot)
