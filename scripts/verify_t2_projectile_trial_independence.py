"""Audit exact duplicate projectile trials without admitting a holdout."""

from __future__ import annotations

import argparse
from collections import defaultdict
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "docs/T2_PROJECTILE_TRIAL_INDEPENDENCE_CONTRACT.json"
SOURCE_CONTRACT = ROOT / "docs/T2_PROJECTILE_SOURCE_CONTRACT.json"
SOURCE_AUDIT = ROOT / "artifacts/t2-projectile-source-audit.json"
PROTOCOL = ROOT / "docs/T2_PROJECTILE_MODEL_PROTOCOL.json"
AUDIT = ROOT / "artifacts/t2-projectile-trial-independence-audit.json"


def _hash(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _source(path: Path) -> dict[str, object]:
    return {"path": path.relative_to(ROOT).as_posix(), "sha256": _hash(path), "bytes": path.stat().st_size}


def _signature(rows: list[tuple[Any, ...]]) -> str:
    payload = [list(row[1:]) for row in rows]
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return sha256(encoded).hexdigest()


def _dynamic(workbook: Path, contract: dict[str, Any]) -> dict[str, object]:
    # Keep receipt replay dependency-minimal; import the excluded reader only
    # when the caller explicitly supplies the local workbook.
    from openpyxl import load_workbook

    source = json.loads(SOURCE_CONTRACT.read_text(encoding="utf-8"))
    if _hash(workbook) != source["files"]["measured_trajectories"]["sha256"]:
        raise ValueError("T2 trial independence workbook bytes differ")
    book = load_workbook(workbook, read_only=True, data_only=True, keep_links=False)
    try:
        header, *rows = list(book.active.values)
    finally:
        book.close()
    if list(header) != source["files"]["measured_trajectories"]["columns"]:
        raise ValueError("T2 trial independence workbook columns differ")
    groups: dict[int, list[tuple[Any, ...]]] = defaultdict(list)
    for row in rows:
        if len(row) != 6 or not isinstance(row[0], int):
            raise ValueError("T2 trial independence workbook row is malformed")
        groups[row[0]].append(row)
    trial_ids = sorted(groups)
    if trial_ids != list(range(2, 32)) or sum(len(rows) for rows in groups.values()) != contract["sample_count"]:
        raise ValueError("T2 trial independence trial coverage differs")
    by_signature: dict[str, list[int]] = defaultdict(list)
    for trial_id, trial in groups.items():
        by_signature[_signature(trial)].append(trial_id)
    duplicates = []
    holdout = set(contract["split"]["holdout_trial_ids"])
    training = set(contract["split"]["training_trial_ids"])
    for signature, trial_ids_for_signature in sorted(by_signature.items()):
        if len(trial_ids_for_signature) < 2:
            continue
        ids = sorted(trial_ids_for_signature)
        duplicates.append({
            "trial_ids": ids,
            "sample_count": len(groups[ids[0]]),
            "signature_sha256": signature,
            "holdout_trial_ids": sorted(holdout.intersection(ids)),
            "training_trial_ids": sorted(training.intersection(ids)),
            "crosses_holdout_boundary": bool(holdout.intersection(ids) and training.intersection(ids)),
        })
    return {"trial_count": len(groups), "sample_count": sum(len(rows) for rows in groups.values()), "duplicate_groups": duplicates}


def evaluate(*, workbook: Path | None = None) -> dict[str, object]:
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    source = json.loads(SOURCE_CONTRACT.read_text(encoding="utf-8"))
    source_audit = json.loads(SOURCE_AUDIT.read_text(encoding="utf-8"))
    protocol = json.loads(PROTOCOL.read_text(encoding="utf-8"))
    expected_boundaries = {
        "posthoc_diagnostic_only": True,
        "trial_independence_verified": False,
        "duplicate_trial_content_found": True,
        "whole_trial_holdout_safe": False,
        "model_fit_admitted": False,
        "scientific_holdout": False,
        "causal_effect_identified": False,
        "source_rights_cleared": False,
        "claim_status": "unverified",
    }
    if (contract.get("schema_version") != "t2-projectile-trial-independence-contract-v1"
            or contract.get("status") != "posthoc-duplicate-trial-diagnostic-only"
            or contract.get("source_contract_sha256") != _hash(SOURCE_CONTRACT)
            or contract.get("source_audit_sha256") != _hash(SOURCE_AUDIT)
            or contract.get("protocol_sha256") != _hash(PROTOCOL)
            or contract.get("source_workbook_sha256") != source["files"]["measured_trajectories"]["sha256"]
            or source_audit.get("status") != "verified-30-trial-real-source-inventory-only"
            or protocol.get("status") != "draft-blocked-before-model-fit"
            or contract.get("boundaries") != expected_boundaries):
        raise ValueError("T2 trial independence contract or boundary differs")
    dynamic = _dynamic(workbook, contract) if workbook is not None else None
    expected_duplicates = contract["duplicate_groups"]
    if dynamic is not None and (dynamic["duplicate_groups"] != expected_duplicates
                                or dynamic["trial_count"] != contract["trial_count"]
                                or dynamic["sample_count"] != contract["sample_count"]):
        raise ValueError("T2 trial independence duplicate result differs")
    return {
        "schema_version": "t2-projectile-trial-independence-audit-v1",
        "status": "verified-posthoc-duplicate-trial-diagnostic-only",
        "contract_sha256": _hash(CONTRACT),
        "source_contract_sha256": _hash(SOURCE_CONTRACT),
        "source_audit_sha256": _hash(SOURCE_AUDIT),
        "protocol_sha256": _hash(PROTOCOL),
        "source_workbook_sha256": contract["source_workbook_sha256"],
        "trial_count": contract["trial_count"],
        "sample_count": contract["sample_count"],
        "split": contract["split"],
        "duplicate_groups": expected_duplicates,
        "boundaries": expected_boundaries,
        "dynamic_verified_here": dynamic is not None,
        "source_files": [_source(path) for path in (Path(__file__).resolve(), CONTRACT, SOURCE_CONTRACT, SOURCE_AUDIT, PROTOCOL)],
    }


def verify_saved(audit: dict[str, object] | None = None) -> dict[str, object]:
    saved = audit if audit is not None else json.loads(AUDIT.read_text(encoding="utf-8"))
    stamp = saved.get("recorded_at")
    if not isinstance(stamp, str) or datetime.fromisoformat(stamp.replace("Z", "+00:00")).tzinfo is None:
        raise ValueError("T2 trial independence timestamp is missing or naive")
    expected = evaluate()
    comparable = {key: value for key, value in saved.items() if key not in {"recorded_at", "dynamic_verified_here"}}
    expected = {key: value for key, value in expected.items() if key != "dynamic_verified_here"}
    if comparable != expected:
        raise ValueError("T2 trial independence receipt differs")
    return saved


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--write", action="store_true")
    action.add_argument("--verify", action="store_true")
    parser.add_argument("--measured-workbook", type=Path)
    args = parser.parse_args()
    if args.write:
        current = evaluate(workbook=args.measured_workbook) if args.measured_workbook else evaluate()
        if AUDIT.exists():
            raise FileExistsError(f"refusing to overwrite T2 trial independence audit: {AUDIT}")
        current["recorded_at"] = datetime.now(timezone.utc).isoformat()
        AUDIT.write_text(json.dumps(current, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
        result = current
    else:
        if args.measured_workbook:
            evaluate(workbook=args.measured_workbook)
        result = verify_saved()
    print(json.dumps({"status": result["status"], "claim_status": result["boundaries"]["claim_status"],
                      "duplicate_groups": result["duplicate_groups"],
                      "dynamic_verified_here": result["dynamic_verified_here"]}, sort_keys=True))


if __name__ == "__main__":
    main()
