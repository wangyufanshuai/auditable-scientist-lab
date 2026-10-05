"""Evidence-bound T2 intake gate, evaluated before any model-fitting callback."""

from __future__ import annotations

import argparse
from copy import deepcopy
from datetime import datetime
import hashlib
from importlib.resources import files
import json
from pathlib import Path
from typing import Callable, TypeVar

from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError

from auditable_scientist.track_registry import canonical_bytes, load_json, safe_file


T = TypeVar("T")
BOUNDARIES = {
    "model_fit_admitted": False, "physical_model_validated": False,
    "causal_effect_identified": False, "scientific_holdout": False,
    "source_rights_cleared": False, "research_candidate": False,
    "publication_ready": False, "claim_status": "unverified",
}


class MeasurementAdmissionDenied(ValueError):
    """A valid intake receipt remains blocked; no fit function has been invoked."""

    def __init__(self, decision: dict) -> None:
        self.decision = deepcopy(decision)
        codes = ", ".join(item["code"] for item in decision["blocking_reasons"])
        super().__init__(f"T2 measurement fit is blocked: {codes}")


def bundled_policy() -> dict:
    return load_json(files("auditable_scientist").joinpath(
        "_resources/examples/measurement-admission/policy.json").read_text(encoding="utf-8"))


def bundled_schema() -> dict:
    return load_json(files("auditable_scientist").joinpath(
        "_resources/schemas/t2-measurement-admission-v1.json").read_text(encoding="utf-8"))


def _validate_policy(policy: dict) -> None:
    Draft202012Validator(bundled_schema()).validate(policy)
    # The policy is a versioned, shipped intake snapshot, not a caller's permission flag.
    if canonical_bytes(policy) != canonical_bytes(bundled_policy()):
        raise ValueError("admission policy differs from the shipped source-bound snapshot")


def evaluate(root: Path, *, policy: dict | None = None) -> dict:
    """Check pinned receipts and derive denial reasons without opening raw observations.

    The current policy deliberately has no approval state. A reviewed, versioned
    successor and independently inspectable evidence are needed to add one.
    """
    policy = bundled_policy() if policy is None else deepcopy(policy)
    _validate_policy(policy)
    inputs = []
    payloads = {}
    for binding in policy["inputs"]:
        path = safe_file(root, binding["path"])
        content = path.read_bytes()
        if (len(content) != binding["bytes"]
                or hashlib.sha256(content).hexdigest() != binding["sha256"]):
            raise ValueError(f"admission input fingerprint differs: {binding['path']}")
        inputs.append(deepcopy(binding))
        if binding["role"] != "verifier-source":
            payloads[binding["role"]] = load_json(content.decode("utf-8"))
    for role, expectation in policy["receipt_identities"].items():
        receipt = payloads[role]
        if any(receipt.get(key) != value for key, value in expectation.items()):
            raise ValueError(f"admission receipt identity differs: {role}")
        stamp = receipt.get("recorded_at")
        if not isinstance(stamp, str) or datetime.fromisoformat(stamp.replace("Z", "+00:00")).tzinfo is None:
            raise ValueError(f"admission receipt timestamp is missing or naive: {role}")
        for source in receipt.get("source_files", []):
            content = safe_file(root, source["path"]).read_bytes()
            if (hashlib.sha256(content).hexdigest() != source["sha256"]
                    or len(content) != source["bytes"]):
                raise ValueError(f"upstream receipt source fingerprint differs: {source['path']}")

    source = payloads["source-audit"]
    source_contract = payloads["source-contract"]
    v0 = payloads["v0-audit"]
    independence = payloads["independence-audit"]
    reconciliation = payloads["reconciliation-audit"]
    protocol = payloads["model-protocol"]
    inventory = source["measured_inventory"]
    trial_ids = [item["trial_id"] for item in inventory["trials"]]
    if len(trial_ids) != len(set(trial_ids)) or len(trial_ids) != inventory["trial_count"]:
        raise ValueError("admission inventory trial IDs are duplicate or incomplete")
    training = protocol["split"]["training_trial_ids"]
    holdout = protocol["split"]["holdout_trial_ids"]
    if (len(training) != len(set(training)) or len(holdout) != len(set(holdout))
            or set(training) & set(holdout) or set(training) | set(holdout) != set(trial_ids)):
        raise ValueError("admission split does not partition the inventoried trials")
    duplicate_groups = []
    for group in independence["duplicate_groups"]:
        ids = group["trial_ids"]
        crossed = bool(set(ids) & set(training) and set(ids) & set(holdout))
        if crossed is not group["crosses_holdout_boundary"]:
            raise ValueError("admission duplicate split classification differs")
        duplicate_groups.append({"trial_ids": ids, "crosses_holdout_boundary": crossed})
    reported = source["article"]["paper_reported_experiments"]
    observed = inventory["trial_count"]
    if reported - observed != reconciliation["reconciliation"]["unaccounted_experiment_count"]:
        raise ValueError("admission experiment coverage arithmetic differs")

    reasons = []

    def blocked(code: str, condition: bool, refs: list[str], details: dict) -> None:
        if condition:
            reasons.append({"code": code, "evidence_refs": refs, "details": details})

    blocked("velocity-role-unresolved",
            v0["boundaries"].get("v0_role_resolved") is not True
            or reconciliation["measured_workbook"].get("v0_role_status") == "unresolved",
            ["artifacts/t2-projectile-v0-diagnostic-audit.json", "artifacts/t2-projectile-source-reconciliation-audit.json"],
            {"affected_trial_ids": trial_ids, "column": "v0 (m/s)",
             "source_narrative_is_column_mapping": False})
    blocked("experiment-coverage-unaccounted", reported != observed,
            ["artifacts/t2-projectile-source-audit.json", "artifacts/t2-projectile-source-reconciliation-audit.json"],
            {"reported_experiments": reported, "inventoried_trials": observed,
             "unaccounted_experiments": reported - observed})
    blocked("duplicate-content-crosses-split", any(group["crosses_holdout_boundary"] for group in duplicate_groups),
            ["artifacts/t2-projectile-trial-independence-audit.json", "docs/T2_PROJECTILE_MODEL_PROTOCOL.json"],
            {"duplicate_groups": duplicate_groups, "posthoc_diagnostic_only": True})
    blocked("source-use-rights-unresolved", reconciliation["provenance"].get("source_rights_cleared") is not True,
            ["docs/T2_PROJECTILE_SOURCE_CONTRACT.json", "artifacts/t2-projectile-source-reconciliation-audit.json"],
            {"review_status": source_contract["rights_review"]["review_status"],
             "redistribution_rights_confirmed": source_contract["article"]["supplement_redistribution_rights_confirmed"],
             "analysis_permission_independently_confirmed": False})
    blocked("drag-constants-unreviewed", protocol["gates"].get("drag_constant_provenance_reviewed") is not True,
            ["docs/T2_PROJECTILE_MODEL_PROTOCOL.json"],
            {"constants": protocol["models"]["spherical_drag"]["constants"]})
    blocked("prospective-split-not-registered", protocol["split"].get("split_registered") is not True
            or protocol["gates"].get("external_preregistration") is not True,
            ["docs/T2_PROJECTILE_MODEL_PROTOCOL.json"],
            {"split_unit": protocol["split"]["unit"], "training_trial_ids": training,
             "holdout_trial_ids": holdout, "tuning_on_holdout": protocol["split"]["tuning_on_holdout"]})
    blocked("protocol-explicitly-denies-fit", protocol["status"] == "draft-blocked-before-model-fit",
            ["docs/T2_PROJECTILE_MODEL_PROTOCOL.json"],
            {"v0_input_modes": [model["v0_input_mode"] for model in protocol["models"].values()]})
    if not reasons:
        raise ValueError("current admission version has no approval path; review a versioned successor")
    return {
        "schema_version": "t2-measurement-admission-decision-v1",
        "status": "blocked-before-model-fit",
        "dataset_id": policy["dataset_id"],
        "input_hash": hashlib.sha256(canonical_bytes(inputs)).hexdigest(),
        "policy_sha256": hashlib.sha256(canonical_bytes(policy)).hexdigest(),
        "input_files": inputs, "blocking_reasons": reasons,
        "inventoried_trial_ids": trial_ids,
        "raw_observations_opened": False, "fit_invoked": False,
        "boundaries": deepcopy(BOUNDARIES),
        "scope": "source-bound intake denial; no measurement fit or scientific validation",
    }


def guarded_fit(root: Path, fit: Callable[[], T], *, policy: dict | None = None) -> T:
    """The supported fitting entry point evaluates evidence before invoking fit."""
    decision = evaluate(root, policy=policy)
    if decision["boundaries"]["model_fit_admitted"] is not True:
        raise MeasurementAdmissionDenied(decision)
    # No current policy can reach this line; a successor must add tested admission.
    return fit()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, type=Path, help="explicit evidence checkout")
    parser.add_argument("--require-admission", action="store_true",
                        help="exit 3 for a verified denial; assessment alone exits 0")
    args = parser.parse_args()
    try:
        decision = evaluate(args.root)
    except (ValueError, OSError, KeyError, ValidationError) as error:
        parser.exit(1, f"T2 admission evidence invalid: {error}\n")
    print(json.dumps(decision, sort_keys=True))
    if args.require_admission:
        parser.exit(3)


if __name__ == "__main__":
    main()
