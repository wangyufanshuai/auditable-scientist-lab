"""Reject altered SRP evidence even when an attacker recomputes its hash."""

from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json

import pytest

from scripts import verify_acceptance


@pytest.fixture
def saved_evidence() -> tuple[dict, dict]:
    audit = verify_acceptance.load("artifacts/t1-maven-srp-sensitivity-audit.json")
    snapshot = verify_acceptance.load("artifacts/t1-maven-srp-sensitivity-snapshot.json")
    assert verify_acceptance.verify_optional_t1_maven_srp_sensitivity(
        audit, snapshot, verify_dynamic=False)["dynamic_verified_here"] is False
    return deepcopy(audit), deepcopy(snapshot)


def _receipt_hash(snapshot: dict) -> str:
    payload = (json.dumps(snapshot, sort_keys=True, separators=(",", ":"),
                          allow_nan=False)+"\n").encode("utf-8")
    return sha256(payload).hexdigest()


@pytest.mark.parametrize("mutation", [
    "snapshot_hash", "source_fingerprint", "endpoint", "refined_endpoint",
    "response", "metric", "parameter", "budget", "claim_promotion",
])
def test_static_acceptance_rejects_srp_tampering(
        saved_evidence: tuple[dict, dict], mutation: str) -> None:
    audit, snapshot = saved_evidence
    case = snapshot["arcs"][0]["cases"][1]
    if mutation == "snapshot_hash":
        snapshot["reader"]["toolkit"] = "altered"
    elif mutation == "source_fingerprint":
        audit["source_files"][0]["sha256"] = "0"*64
    elif mutation == "endpoint":
        case["endpoint_state_km_kms"][0] += 0.001
    elif mutation == "refined_endpoint":
        case["refined_endpoint_state_km_kms"][0] += 0.001
    elif mutation == "response":
        case["response_position_km"][0] += 0.001
    elif mutation == "metric":
        case["response_position_norm_km"] += 0.01
    elif mutation == "parameter":
        case["effective_area_over_mass_m2_per_kg"] = 0.002
    elif mutation == "budget":
        snapshot["observed_budget"]["rk4_steps_total"] += 1
        audit["observed_budget"] = snapshot["observed_budget"]
    else:
        snapshot["scientific_boundaries"]["claim_status"] = "validated"
    if mutation != "snapshot_hash":
        audit["snapshot_sha256"] = _receipt_hash(snapshot)
    with pytest.raises(ValueError, match="MAVEN SRP"):
        verify_acceptance.verify_optional_t1_maven_srp_sensitivity(
            audit, snapshot, verify_dynamic=False)
