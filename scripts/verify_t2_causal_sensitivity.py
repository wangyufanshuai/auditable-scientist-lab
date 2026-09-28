"""Verify the bounded T2 context-leakage sensitivity receipt."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path

from auditable_scientist.tracks.causal_sensitivity import (
    candidate_set_hash,
    evaluate_context_sensitivity,
    load_builtin_cases,
)


ROOT = Path(__file__).resolve().parents[1]
AUDIT = ROOT / "artifacts/t2-causal-sensitivity-audit.json"
SOURCE_PATHS = [
    Path(__file__).resolve(),
    ROOT / "src/auditable_scientist/tracks/causal_sensitivity.py",
    ROOT / "src/auditable_scientist/tracks/causal.py",
    ROOT / "src/auditable_scientist/tracks/common.py",
    ROOT / "src/auditable_scientist/runtime/canonical.py",
    ROOT / "src/auditable_scientist/runtime/paths.py",
    ROOT / "examples/causal/fixture.json",
    ROOT / "docs/T2_CAUSAL_SENSITIVITY.md",
]


def _sha(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def build_audit() -> dict:
    cases = load_builtin_cases()
    evaluation, receipt = evaluate_context_sensitivity(cases)
    if not evaluation.passed or not receipt.passed:
        raise ValueError("T2 context sensitivity gate failed")
    return {
        "schema_version": "t2-causal-sensitivity-audit-v1",
        "status": "verified-synthetic-context-sensitivity-only",
        "negative_case_rejected": evaluation.context_leakage_rejected,
        "candidate_set": {
            "ids": ["causal-intervention-v1", "causal-context-leak-v1"],
            "sha256": candidate_set_hash(),
        },
        "receipt": receipt.model_dump(mode="json"),
        "evaluation": evaluation.model_dump(mode="json"),
        "boundaries": {
            "synthetic_intervention_semantics": True,
            "context_leakage_negative_control": True,
            "real_intervention_data": False,
            "causal_identification": False,
            "source_rights_reviewed": False,
            "research_candidate": False,
            "publication_ready": False,
            "claim_status": "unverified",
        },
        "source_files": [
            {
                "path": path.relative_to(ROOT).as_posix(),
                "sha256": _sha(path),
                "bytes": path.stat().st_size,
            }
            for path in SOURCE_PATHS
        ],
    }


def verify_saved(saved: dict, current: dict) -> None:
    stamp = saved.get("recorded_at")
    if not isinstance(stamp, str):
        raise ValueError("T2 causal sensitivity audit has no timestamp")
    parsed = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("T2 causal sensitivity audit timestamp is naive")
    if {key: value for key, value in saved.items() if key != "recorded_at"} != current:
        raise ValueError("T2 causal sensitivity audit differs from current computation")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--write", action="store_true")
    group.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    current = build_audit()
    if args.write:
        current["recorded_at"] = datetime.now(timezone.utc).isoformat()
        AUDIT.write_text(json.dumps(current, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    else:
        verify_saved(json.loads(AUDIT.read_text(encoding="utf-8")), current)
    print(json.dumps({"status": current["status"], "candidate_set_sha256": current["candidate_set"]["sha256"]}, sort_keys=True))


if __name__ == "__main__":
    main()
