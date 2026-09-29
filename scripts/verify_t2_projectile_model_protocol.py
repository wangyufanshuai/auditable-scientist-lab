"""Fail-closed checks for the blocked T2 projectile model protocol draft."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = ROOT / "docs/T2_PROJECTILE_MODEL_PROTOCOL.json"
SOURCE_CONTRACT = ROOT / "docs/T2_PROJECTILE_SOURCE_CONTRACT.json"
SOURCE_AUDIT = ROOT / "artifacts/t2-projectile-source-audit.json"
TRIAL_INDEPENDENCE_CONTRACT = ROOT / "docs/T2_PROJECTILE_TRIAL_INDEPENDENCE_CONTRACT.json"


def evaluate() -> dict:
    protocol = json.loads(PROTOCOL.read_text(encoding="utf-8"))
    contract = json.loads(SOURCE_CONTRACT.read_text(encoding="utf-8"))
    audit = json.loads(SOURCE_AUDIT.read_text(encoding="utf-8"))
    trial_independence = json.loads(TRIAL_INDEPENDENCE_CONTRACT.read_text(encoding="utf-8"))
    expected_holdout = [4, 6, 7, 9, 13, 21, 22, 29, 30]
    all_trials = list(range(2, 32))
    expected_training = [trial for trial in all_trials if trial not in expected_holdout]
    expected_gates = {
        "supplement_rights_reviewed": True,
        "supplement_redistribution_rights_confirmed": False,
        "complete_reported_experiment_set": False,
        "velocity_column_semantics_reviewed": False,
        "drag_constant_provenance_reviewed": False,
        "external_preregistration": False,
        "trial_independence_verified": False,
        "physical_model_validated": False,
        "scientific_holdout": False,
        "causal_effect_identified": False,
        "research_candidate": False,
        "publication_ready": False,
        "claim_status": "unverified",
    }
    if (
        protocol.get("schema_version") != "t2-projectile-model-protocol-v1"
        or protocol.get("status") != "draft-blocked-before-model-fit"
        or protocol.get("source_contract_sha256")
        != hashlib.sha256(SOURCE_CONTRACT.read_bytes()).hexdigest()
        or protocol.get("source_audit_sha256")
        != hashlib.sha256(SOURCE_AUDIT.read_bytes()).hexdigest()
        or contract.get("schema_version") != "t2-projectile-source-contract-v1"
        or audit.get("status") != "verified-30-trial-real-source-inventory-only"
        or trial_independence.get("status") != "posthoc-duplicate-trial-diagnostic-only"
        or trial_independence.get("boundaries", {}).get("whole_trial_holdout_safe") is not False
        or trial_independence.get("duplicate_groups", [{}])[0].get("crosses_holdout_boundary") is not True
        or protocol.get("split", {}).get("holdout_trial_ids") != expected_holdout
        or protocol.get("split", {}).get("training_trial_ids") != expected_training
        or protocol.get("split", {}).get("tuning_on_holdout") is not False
        or protocol.get("split", {}).get("split_registered") is not False
        or protocol.get("gates") != expected_gates
        or protocol.get("negative_controls", {}).get("duplicate_trial_content_cross_split_rejected") is not True
        or protocol.get("result_artifact") is not None
        or protocol.get("models", {}).get("no_drag", {}).get("v0_input_mode")
        != "blocked-until-column-role-resolved"
        or protocol.get("models", {}).get("spherical_drag", {}).get("v0_input_mode")
        != "blocked-until-column-role-resolved"
    ):
        raise ValueError("T2 projectile model protocol is missing a blocked boundary")
    derived = [
        trial for trial in all_trials
        if hashlib.sha256(f"t2-projectile-trial:{trial}".encode()).digest()[0] % 5 == 0
    ]
    if derived != expected_holdout:
        raise ValueError("T2 projectile holdout rule changed")
    return {
        "schema_version": "t2-projectile-model-protocol-audit-v1",
        "status": "verified-blocked-protocol-only",
        "holdout_trial_count": len(expected_holdout),
        "training_trial_count": len(expected_training),
        "fit_permitted": False,
        "causal_effect_identified": False,
        "physical_model_validated": False,
        "claim_status": "unverified",
    }


def main() -> None:
    print(json.dumps(evaluate(), sort_keys=True))


if __name__ == "__main__":
    main()
