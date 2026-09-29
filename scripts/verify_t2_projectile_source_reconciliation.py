"""Reconcile the bounded T2 projectile source intake without promoting claims."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "docs/T2_PROJECTILE_SOURCE_RECONCILIATION_CONTRACT.json"
SOURCE_CONTRACT = ROOT / "docs/T2_PROJECTILE_SOURCE_CONTRACT.json"
SOURCE_AUDIT = ROOT / "artifacts/t2-projectile-source-audit.json"
V0_CONTRACT = ROOT / "docs/T2_PROJECTILE_V0_DIAGNOSTIC_CONTRACT.json"
V0_AUDIT = ROOT / "artifacts/t2-projectile-v0-diagnostic-audit.json"
INDEPENDENCE_CONTRACT = ROOT / "docs/T2_PROJECTILE_TRIAL_INDEPENDENCE_CONTRACT.json"
INDEPENDENCE_AUDIT = ROOT / "artifacts/t2-projectile-trial-independence-audit.json"
AUDIT = ROOT / "artifacts/t2-projectile-source-reconciliation-audit.json"


def _hash(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _source(path: Path) -> dict[str, object]:
    return {"path": path.relative_to(ROOT).as_posix(), "sha256": _hash(path), "bytes": path.stat().st_size}


def _expected_contract_dependencies(contract: dict[str, Any]) -> dict[str, str]:
    expected = {
        "source_contract_sha256": _hash(SOURCE_CONTRACT),
        "source_audit_sha256": _hash(SOURCE_AUDIT),
        "v0_diagnostic_contract_sha256": _hash(V0_CONTRACT),
        "v0_diagnostic_audit_sha256": _hash(V0_AUDIT),
        "trial_independence_contract_sha256": _hash(INDEPENDENCE_CONTRACT),
        "trial_independence_audit_sha256": _hash(INDEPENDENCE_AUDIT),
    }
    if any(contract.get(key) != value for key, value in expected.items()):
        raise ValueError("T2 reconciliation input hash differs")
    return expected


def _validate_contract(contract: dict[str, Any]) -> None:
    if (contract.get("schema_version") != "t2-projectile-source-reconciliation-contract-v1"
            or contract.get("status") != "reconciled-partial-source-intake-only"
            or contract.get("scope") != "machine-readable reconciliation of article coverage, workbook roles, provenance metadata, and blocked scientific boundaries"):
        raise ValueError("T2 reconciliation contract identity differs")
    _expected_contract_dependencies(contract)
    if contract.get("article") != {
        "reported_experiment_count": 82,
        "reported_launch_speed_upper_bound_m_s": 6.0,
        "measured_velocity_narrative": "The article says initial velocity is measured with an in-built light gate accurate to within 0.1 m/s.",
        "fitted_velocity_narrative": "The article also treats initial velocity as a least-squares fitting parameter and says the supplementary result uses measured initial velocity.",
        "narrative_is_semantic_mapping_for_workbook_v0": False,
    }:
        raise ValueError("T2 article reconciliation fields differ")
    workbook = contract.get("measured_workbook", {})
    metadata = workbook.get("metadata", {})
    if (workbook.get("sample_count") != 179 or workbook.get("trial_count") != 30
            or workbook.get("trial_id_range") != [2, 31]
            or workbook.get("v0_header") != "v0 (m/s)"
            or workbook.get("v0_role_status") != "unresolved"
            or workbook.get("raw_file_redistributed") is not False
            or metadata != {
                "package_part": "xl/workbook.xml",
                "part_sha256": "13adaa8abbe7fae0c8c318e7652659812e8aa6e032c6b0f081a699574ff81b8b",
                "absolute_path_element_present": True,
                "absolute_path_value_sha256": "4f600d0047a77f9340b33952b0aada3a3eacf4ed3d6da46ca81ae730dc081341",
                "metadata_role": "provenance-only",
                "semantic_column_mapping_proven": False,
            }):
        raise ValueError("T2 workbook reconciliation fields differ")
    if contract.get("numerical_workbook") != {"admitted_as_observations": False, "formula_cells": 3507}:
        raise ValueError("T2 numerical workbook boundary differs")
    if contract.get("reconciliation") != {
        "coverage_status": "partial-unaccounted",
        "unaccounted_experiment_count": 52,
        "declared_speed_above_article_bound_trial_ids": [4, 5, 6, 10, 11, 12, 13, 14, 15, 16, 17, 18, 22, 23, 24],
        "duplicate_trial_groups": [[22, 23]],
        "duplicate_crosses_holdout_boundary": True,
    }:
        raise ValueError("T2 source reconciliation fields differ")
    if contract.get("provenance") != {
        "source_rights_status": "rights-language-reviewed-raw-supplement-redistribution-not-confirmed",
        "local_path_metadata_is_semantic_proof": False,
        "source_file_identity_is_semantic_proof": False,
        "source_rights_cleared": False,
    }:
        raise ValueError("T2 provenance boundary differs")
    if contract.get("negative_controls") != {
        "coverage_count_spoof_rejected": True,
        "v0_role_forced_resolved_rejected": True,
        "source_hash_tamper_rejected": True,
        "duplicate_cross_split_ignored_rejected": True,
        "rights_promoted_to_cleared_rejected": True,
    }:
        raise ValueError("T2 reconciliation negative controls differ")
    if contract.get("boundaries") != {
        "complete_reported_experiment_set": False,
        "velocity_column_semantics_resolved": False,
        "physical_model_validated": False,
        "causal_effect_identified": False,
        "scientific_holdout": False,
        "research_candidate": False,
        "publication_ready": False,
        "claim_status": "unverified",
    }:
        raise ValueError("T2 reconciliation scientific boundary differs")


def evaluate() -> dict[str, Any]:
    contract = _load(CONTRACT)
    _validate_contract(contract)
    source = _load(SOURCE_CONTRACT)
    source_audit = _load(SOURCE_AUDIT)
    v0 = _load(V0_AUDIT)
    independence = _load(INDEPENDENCE_AUDIT)
    if (source.get("schema_version") != "t2-projectile-source-contract-v1"
            or source_audit.get("schema_version") != "t2-projectile-source-audit-v1"
            or source_audit.get("status") != "verified-30-trial-real-source-inventory-only"
            or source_audit.get("measured_inventory", {}).get("sample_count") != 179
            or source_audit.get("measured_inventory", {}).get("trial_count") != 30
            or source_audit.get("article", {}).get("paper_reported_experiments") != 82
            or source_audit.get("article", {}).get("paper_stated_launch_speed_upper_bound_m_s") != 6.0
            or v0.get("schema_version") != "t2-projectile-v0-diagnostic-audit-v1"
            or v0.get("boundaries", {}).get("v0_role_resolved") is not False
            or v0.get("boundaries", {}).get("source_rights_cleared") is not False
            or independence.get("schema_version") != "t2-projectile-trial-independence-audit-v1"
            or independence.get("boundaries", {}).get("whole_trial_holdout_safe") is not False):
        raise ValueError("T2 upstream receipt boundary differs")
    above_bound = source_audit["measured_inventory"]["observed_declared_speed_above_paper_bound_trials"]
    duplicate_groups = [group["trial_ids"] for group in independence["duplicate_groups"]]
    if (above_bound != [4, 5, 6, 10, 11, 12, 13, 14, 15, 16, 17, 18, 22, 23, 24]
            or duplicate_groups != [[22, 23]]
            or not any(group.get("crosses_holdout_boundary") is True for group in independence["duplicate_groups"])
            or source_audit["boundaries"].get("complete_reported_experiment_set") is not False
            or source_audit["boundaries"].get("claim_status") != "unverified"):
        raise ValueError("T2 upstream reconciliation evidence differs")
    return {
        "schema_version": "t2-projectile-source-reconciliation-audit-v1",
        "status": "verified-reconciled-partial-source-intake-only",
        "contract_sha256": _hash(CONTRACT),
        "input_hashes": _expected_contract_dependencies(contract),
        "article": contract["article"],
        "measured_workbook": contract["measured_workbook"],
        "numerical_workbook": contract["numerical_workbook"],
        "reconciliation": contract["reconciliation"],
        "provenance": contract["provenance"],
        "negative_controls": contract["negative_controls"],
        "boundaries": contract["boundaries"],
        "source_files": [_source(path) for path in (
            Path(__file__).resolve(), CONTRACT, SOURCE_CONTRACT, SOURCE_AUDIT,
            V0_CONTRACT, V0_AUDIT, INDEPENDENCE_CONTRACT, INDEPENDENCE_AUDIT,
        )],
    }


def verify_saved(audit: dict[str, Any] | None = None) -> dict[str, Any]:
    saved = audit if audit is not None else _load(AUDIT)
    stamp = saved.get("recorded_at")
    if not isinstance(stamp, str) or datetime.fromisoformat(stamp.replace("Z", "+00:00")).tzinfo is None:
        raise ValueError("T2 reconciliation timestamp is missing or naive")
    expected = evaluate()
    comparable = {key: value for key, value in saved.items() if key != "recorded_at"}
    if comparable != expected:
        raise ValueError("T2 source reconciliation receipt differs")
    return saved


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--write", action="store_true")
    action.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    current = evaluate()
    if args.write:
        if AUDIT.exists():
            raise FileExistsError(f"refusing to overwrite T2 reconciliation audit: {AUDIT}")
        current["recorded_at"] = datetime.now(timezone.utc).isoformat()
        AUDIT.write_text(json.dumps(current, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
        result = current
    else:
        result = verify_saved()
    print(json.dumps({"status": result["status"], "claim_status": result["boundaries"]["claim_status"],
                      "reported_experiments": result["article"]["reported_experiment_count"],
                      "measured_trials": result["measured_workbook"]["trial_count"],
                      "measured_samples": result["measured_workbook"]["sample_count"],
                      "unaccounted_experiments": result["reconciliation"]["unaccounted_experiment_count"]}, sort_keys=True))


if __name__ == "__main__":
    main()
