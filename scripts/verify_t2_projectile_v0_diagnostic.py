"""Audit the unresolved role of the projectile workbook's ``v0`` column.

The diagnostic is deliberately post-hoc: it compares the declared workbook
values with a trajectory-only no-drag estimate, but never treats that estimate
as an independent measurement or admits a fitted model result.
"""

from __future__ import annotations

import argparse
from collections import defaultdict
from datetime import datetime, timezone
from hashlib import sha256
import json
from math import cos, isfinite, pi, sqrt, tan
from pathlib import Path
from statistics import mean, median
from typing import Any

from openpyxl import load_workbook
from pypdf import PdfReader


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "docs/T2_PROJECTILE_V0_DIAGNOSTIC_CONTRACT.json"
SOURCE_CONTRACT = ROOT / "docs/T2_PROJECTILE_SOURCE_CONTRACT.json"
SOURCE_AUDIT = ROOT / "artifacts/t2-projectile-source-audit.json"
AUDIT = ROOT / "artifacts/t2-projectile-v0-diagnostic-audit.json"
DEFAULT_PDF = ROOT / "data/references/t2_projectile_wadsworth_2025/Wadsworth_2025_Phys_Educ_60_045024.pdf"
DEFAULT_WORKBOOK = ROOT / "data/references/t2_projectile_wadsworth_2025/pedadd2c5supp1.xlsx"


def _hash(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _json_hash(value: Any) -> str:
    return sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()


def _source(path: Path) -> dict[str, object]:
    return {"path": path.relative_to(ROOT).as_posix(), "sha256": _hash(path), "bytes": path.stat().st_size}


def _fit_v0(rows: list[tuple[Any, ...]]) -> float:
    theta = float(rows[0][4]) * pi / 180.0
    c = cos(theta)
    x2 = [float(row[2]) ** 2 for row in rows]
    z = [float(row[2]) * tan(theta) - float(row[3]) for row in rows]
    denominator = sum(value * value for value in x2)
    coefficient = sum(left * right for left, right in zip(x2, z)) / denominator
    if coefficient <= 0 or not isfinite(coefficient):
        raise ValueError("trajectory-only v0 estimate is not finite and positive")
    return sqrt(9.81 / (2 * coefficient * c * c))


def _dynamic(pdf: Path, workbook: Path) -> dict[str, object]:
    source = json.loads(SOURCE_CONTRACT.read_text(encoding="utf-8"))
    files = source["files"]
    if _hash(pdf) != files["article_pdf"]["sha256"] or _hash(workbook) != files["measured_trajectories"]["sha256"]:
        raise ValueError("T2 v0 diagnostic source bytes differ")
    pages = [page.extract_text() for page in PdfReader(str(pdf)).pages]
    if len(pages) != files["article_pdf"]["pages"]:
        raise ValueError("T2 v0 diagnostic article page count differs")
    book = load_workbook(workbook, read_only=True, data_only=True, keep_links=False)
    try:
        header, *rows = list(book.active.values)
    finally:
        book.close()
    if list(header) != files["measured_trajectories"]["columns"]:
        raise ValueError("T2 v0 diagnostic workbook columns differ")
    groups: dict[int, list[tuple[Any, ...]]] = defaultdict(list)
    for row in rows:
        if len(row) != 6 or not isinstance(row[0], int):
            raise ValueError("T2 v0 diagnostic workbook row is malformed")
        groups[row[0]].append(row)
    trial_ids = sorted(groups)
    if trial_ids != list(range(2, 32)):
        raise ValueError("T2 v0 diagnostic trial coverage differs")
    comparisons = []
    for trial_id in trial_ids:
        trial = groups[trial_id]
        declared = float(trial[0][5])
        estimate = _fit_v0(trial)
        comparisons.append({
            "trial_id": trial_id,
            "declared_v0_m_s": round(declared, 12),
            "trajectory_only_v0_m_s": round(estimate, 12),
            "difference_m_s": round(estimate - declared, 12),
            "sample_count": len(trial),
        })
    diffs = [abs(row["difference_m_s"]) for row in comparisons]
    above_bound = [row["trial_id"] for row in comparisons if row["declared_v0_m_s"] > 6.0]
    return {
        "article_page_text_sha256": [_hash_bytes(page.encode("utf-8")) for page in pages],
        "measured_workbook_sha256": _hash(workbook),
        "trial_count": len(comparisons),
        "sample_count": sum(row["sample_count"] for row in comparisons),
        "declared_speed_above_paper_bound_trials": above_bound,
        "comparison": {
            "method": "trajectory-only-no-drag-y-of-x-through-origin",
            "absolute_difference_mae_m_s": round(mean(diffs), 12),
            "absolute_difference_median_m_s": round(median(diffs), 12),
            "absolute_difference_max_m_s": round(max(diffs), 12),
            "within_0_1_m_s": sum(value <= 0.1 for value in diffs),
            "within_0_25_m_s": sum(value <= 0.25 for value in diffs),
        },
        "trial_comparisons": comparisons,
    }


def evaluate(*, pdf: Path | None = None, workbook: Path | None = None) -> dict[str, object]:
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    source = json.loads(SOURCE_CONTRACT.read_text(encoding="utf-8"))
    source_audit = json.loads(SOURCE_AUDIT.read_text(encoding="utf-8"))
    expected_boundaries = {
        "posthoc_diagnostic_only": True,
        "v0_role_resolved": False,
        "independent_input_verified": False,
        "model_fit_admitted": False,
        "scientific_holdout": False,
        "causal_effect_identified": False,
        "source_rights_cleared": False,
        "claim_status": "unverified",
    }
    if (contract.get("schema_version") != "t2-projectile-v0-diagnostic-contract-v1"
            or contract.get("source_pdf_sha256") != source["files"]["article_pdf"]["sha256"]
            or contract.get("source_workbook_sha256") != source["files"]["measured_trajectories"]["sha256"]
            or contract.get("source_contract_sha256") != _hash(SOURCE_CONTRACT)
            or source_audit.get("status") != "verified-30-trial-real-source-inventory-only"
            or contract.get("boundaries") != expected_boundaries):
        raise ValueError("T2 v0 diagnostic contract or boundary differs")
    dynamic = None
    if pdf is not None or workbook is not None:
        if pdf is None or workbook is None:
            raise ValueError("T2 v0 diagnostic requires both source paths")
        dynamic = _dynamic(pdf, workbook)
        if dynamic["declared_speed_above_paper_bound_trials"] != contract["declared_speed_above_paper_bound_trials"]:
            raise ValueError("T2 v0 diagnostic speed discrepancy differs")
    result = {
        "schema_version": "t2-projectile-v0-diagnostic-audit-v1",
        "status": "verified-posthoc-v0-provenance-diagnostic-only",
        "contract_sha256": _hash(CONTRACT),
        "source_contract_sha256": _hash(SOURCE_CONTRACT),
        "source_pdf_sha256": contract["source_pdf_sha256"],
        "source_workbook_sha256": contract["source_workbook_sha256"],
        "evaluator_input_hash": contract["evaluator_input_hash"],
        "declared_speed_above_paper_bound_trials": contract["declared_speed_above_paper_bound_trials"],
        "comparison": contract["comparison"],
        "boundaries": expected_boundaries,
        "dynamic_verified_here": dynamic is not None,
        "source_files": [_source(path) for path in (Path(__file__).resolve(), CONTRACT, SOURCE_CONTRACT, SOURCE_AUDIT)],
    }
    if dynamic is not None:
        if dynamic["comparison"] != contract["comparison"] or dynamic["trial_comparisons"] != contract["trial_comparisons"]:
            raise ValueError("T2 v0 diagnostic comparison differs from pinned result")
        result["article_page_text_sha256"] = dynamic["article_page_text_sha256"]
        result["trial_count"] = dynamic["trial_count"]
        result["sample_count"] = dynamic["sample_count"]
        result["trial_comparisons"] = dynamic["trial_comparisons"]
    else:
        result["article_page_text_sha256"] = contract["article_page_text_sha256"]
        result["trial_count"] = contract["trial_count"]
        result["sample_count"] = contract["sample_count"]
        result["trial_comparisons"] = contract["trial_comparisons"]
    return result


def verify_saved(audit: dict[str, object] | None = None) -> dict[str, object]:
    saved = audit if audit is not None else json.loads(AUDIT.read_text(encoding="utf-8"))
    stamp = saved.get("recorded_at")
    if not isinstance(stamp, str) or datetime.fromisoformat(stamp.replace("Z", "+00:00")).tzinfo is None:
        raise ValueError("T2 v0 diagnostic timestamp is missing or naive")
    expected = evaluate()
    comparable = {key: value for key, value in saved.items() if key not in {"recorded_at", "dynamic_verified_here"}}
    expected = {key: value for key, value in expected.items() if key != "dynamic_verified_here"}
    if comparable != expected:
        raise ValueError("T2 v0 diagnostic receipt differs")
    return saved


def _hash_bytes(data: bytes) -> str:
    return sha256(data).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--write", action="store_true")
    action.add_argument("--verify", action="store_true")
    parser.add_argument("--article-pdf", type=Path)
    parser.add_argument("--measured-workbook", type=Path)
    args = parser.parse_args()
    if args.write:
        current = evaluate(pdf=args.article_pdf, workbook=args.measured_workbook) if args.article_pdf else evaluate()
        if AUDIT.exists():
            raise FileExistsError(f"refusing to overwrite T2 v0 diagnostic audit: {AUDIT}")
        current["recorded_at"] = datetime.now(timezone.utc).isoformat()
        AUDIT.write_text(json.dumps(current, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
        result = current
    else:
        if args.article_pdf:
            evaluate(pdf=args.article_pdf, workbook=args.measured_workbook)
        result = verify_saved()
    print(json.dumps({"status": result["status"], "claim_status": result["boundaries"]["claim_status"],
                      "dynamic_verified_here": result["dynamic_verified_here"]}, sort_keys=True))


if __name__ == "__main__":
    main()
