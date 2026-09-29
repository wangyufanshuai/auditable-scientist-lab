"""Verify the shared engineering contract for bounded nonintegrable T3 audits."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "docs/T3_BACKEND_CONTRACT.json"
OUTPUT = ROOT / "artifacts/t3-backend-contract-audit.json"


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _lookup(mapping: dict[str, Any], key: str) -> Any:
    value: Any = mapping
    for part in key.split("."):
        if not isinstance(value, dict) or part not in value:
            raise ValueError(f"missing field: {key}")
        value = value[part]
    return value


def _verify_entry(entry: dict[str, Any]) -> dict[str, Any]:
    artifact_path = ROOT / entry["artifact"]
    artifact = _load(artifact_path)
    if artifact.get("status") != entry["status"]:
        raise ValueError(f"{entry['id']}: status differs from contract")
    protocol_path = ROOT / entry["protocol"]
    if not protocol_path.is_file():
        raise ValueError(f"{entry['id']}: protocol is missing")
    protocol = _load(protocol_path) if protocol_path.suffix == ".json" else {}

    source_records = {item.get("path"): item for item in artifact.get("source_files", [])}
    required_sources = set(entry["required_source_paths"])
    if set(source_records) != required_sources:
        missing = sorted(required_sources - set(source_records))
        extra = sorted(set(source_records) - required_sources)
        raise ValueError(f"{entry['id']}: source inventory differs; missing={missing}, extra={extra}")
    source_hashes: dict[str, str] = {}
    for source in sorted(required_sources):
        path = ROOT / source
        if not path.is_file():
            raise ValueError(f"{entry['id']}: source is missing: {source}")
        record = source_records[source]
        actual_hash = _sha256(path)
        if record.get("sha256") != actual_hash or record.get("bytes") != path.stat().st_size:
            raise ValueError(f"{entry['id']}: source fingerprint differs: {source}")
        source_hashes[source] = actual_hash

    solver = artifact.get("solver", artifact.get("solvers", protocol.get("solvers", {})))
    for field, expected in entry["solver_fields"].items():
        if solver.get(field) != expected:
            raise ValueError(f"{entry['id']}: solver field differs: {field}")
    budget_source = artifact.get("compute_budget", artifact.get("budget", protocol.get("compute_budget", {})))
    for observed_key, maximum_key in entry["budget_fields"].items():
        observed = _lookup(artifact, f"observed_budget.{observed_key}")
        maximum = _lookup(budget_source, maximum_key)
        if not isinstance(observed, int) or not isinstance(maximum, int) or observed < 0 or maximum <= 0 or observed > maximum:
            raise ValueError(f"{entry['id']}: compute ceiling failed: {observed_key}")
    checks = artifact.get("checks")
    for check in entry["required_checks"]:
        if checks.get(check) is not True:
            raise ValueError(f"{entry['id']}: required check is not true: {check}")
    boundary = artifact.get("scientific_boundaries", artifact.get("boundaries", {}))
    if any(boundary.get(key) != expected for key, expected in entry["boundary_equals"].items()):
        raise ValueError(f"{entry['id']}: scientific boundary differs")
    return {
        "id": entry["id"],
        "artifact": entry["artifact"],
        "protocol": entry["protocol"],
        "status": artifact["status"],
        "source_files": source_hashes,
        "budget": {
            observed_key: _lookup(artifact, f"observed_budget.{observed_key}")
            for observed_key in entry["budget_fields"]
        },
        "checks": {check: True for check in entry["required_checks"]},
        "claim_status": boundary.get("claim_status", "unverified"),
    }


def build_receipt() -> dict[str, Any]:
    contract = _load(CONTRACT)
    if contract.get("schema_version") != "t3-backend-contract-v1":
        raise ValueError("unexpected T3 backend contract schema")
    entries = [_verify_entry(entry) for entry in contract.get("audits", [])]
    if len(entries) != 3:
        raise ValueError("T3 backend contract must cover exactly three audits")
    return {
        "schema_version": "t3-backend-contract-audit-v1",
        "status": "verified-bounded-independent-backend-contract",
        "contract_sha256": _sha256(CONTRACT),
        "audit_count": len(entries),
        "audits": entries,
        "boundaries": {
            "finite_engineering_contract": True,
            "independent_backend_quality_generalized": False,
            "chaotic_regime_validated": False,
            "general_nbody_validated": False,
            "real_mission_validated": False,
            "scientific_claim_verified": False,
            "publication_ready": False,
        },
    }


def verify_saved_receipt(path: Path = OUTPUT) -> dict[str, Any]:
    saved = _load(path)
    recorded_at = saved.pop("recorded_at", None)
    if not isinstance(recorded_at, str):
        raise ValueError("T3 backend audit timestamp is missing")
    timestamp = datetime.fromisoformat(recorded_at.replace("Z", "+00:00"))
    if timestamp.tzinfo is None or timestamp.utcoffset() is None:
        raise ValueError("T3 backend audit timestamp is naive")
    expected = build_receipt()
    if saved != expected:
        raise ValueError("T3 backend audit differs from the current contract or source bytes")
    return {**expected, "recorded_at": recorded_at}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    if args.write == args.verify:
        parser.error("choose exactly one of --write or --verify")
    if args.write:
        result = build_receipt()
        result["recorded_at"] = datetime.now(timezone.utc).isoformat()
        OUTPUT.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    else:
        result = verify_saved_receipt()
    print(json.dumps({"status": result["status"], "audit_count": result["audit_count"]}, indent=2))


if __name__ == "__main__":
    main()
