"""Recompute the T2 measurement denial and test refusal before fitting."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path

from auditable_scientist.track_registry import canonical_bytes, load_json, safe_file
from auditable_scientist.tracks.measurement_admission import (
    MeasurementAdmissionDenied, evaluate as evaluate_admission, guarded_fit,
)


ROOT = Path(__file__).resolve().parents[1]
AUDIT = ROOT / "artifacts/t2-measurement-admission-audit.json"
POLICY = ROOT / "docs/T2_MEASUREMENT_ADMISSION_POLICY.json"
SOURCE_PATHS = (
    "scripts/verify_t2_measurement_admission.py",
    "src/auditable_scientist/tracks/measurement_admission.py",
    "src/auditable_scientist/track_registry.py",
    "docs/T2_MEASUREMENT_ADMISSION_POLICY.json",
    "schemas/t2-measurement-admission-v1.json",
)


def evaluate() -> dict:
    policy = load_json(POLICY.read_text(encoding="utf-8"))
    decision = evaluate_admission(ROOT, policy=policy)
    upstream_verified = []
    for relative in (
        "scripts/verify_t2_projectile_v0_diagnostic.py",
        "scripts/verify_t2_projectile_trial_independence.py",
        "scripts/verify_t2_projectile_source_reconciliation.py",
    ):
        spec = importlib.util.spec_from_file_location("admission_" + Path(relative).stem, ROOT / relative)
        if spec is None or spec.loader is None:
            raise ValueError("upstream T2 verifier is unavailable")
        upstream = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(upstream)
        verified = upstream.verify_saved()
        upstream_verified.append({"path": relative, "status": verified["status"]})
    invoked = []

    def forbidden_fit() -> None:
        invoked.append(True)
        raise AssertionError("measurement fitting must not be invoked")

    try:
        guarded_fit(ROOT, forbidden_fit, policy=policy)
    except MeasurementAdmissionDenied as denial:
        if canonical_bytes(denial.decision) != canonical_bytes(decision) or invoked:
            raise ValueError("guarded fit denial differs from assessment")
    else:
        raise ValueError("guarded fit failed to refuse unresolved evidence")
    sources = []
    for relative in SOURCE_PATHS:
        content = safe_file(ROOT, relative).read_bytes()
        sources.append({"path": relative, "sha256": hashlib.sha256(content).hexdigest(), "bytes": len(content)})
    return {
        "schema_version": "t2-measurement-admission-audit-v1",
        "status": "verified-evidence-bound-fit-denial",
        "decision": decision,
        "fit_callback_not_invoked": True,
        "raw_observations_not_opened": decision["raw_observations_opened"] is False,
        "source_files": sources,
        "upstream_receipts_recomputed": upstream_verified,
        "boundaries": decision["boundaries"],
        "limitations": [
            "Assessment checks pinned committed receipts and source bytes; it does not re-read restricted raw observations.",
            "Refusal protects calls through guarded_fit; arbitrary external Python code is not sandboxed by this API.",
            "The current version has no approval state; independently reviewed successor evidence is required to admit fitting.",
            "No predictive fit, causal effect, physical validation, rights clearance, or scientific holdout is produced.",
        ],
    }


def verify_saved(audit: dict | None = None) -> dict:
    saved = audit if audit is not None else load_json(AUDIT.read_text(encoding="utf-8"))
    stamp = saved.get("recorded_at")
    if not isinstance(stamp, str) or datetime.fromisoformat(stamp.replace("Z", "+00:00")).tzinfo is None:
        raise ValueError("T2 admission audit timestamp is missing or naive")
    comparable = {key: value for key, value in saved.items() if key != "recorded_at"}
    if canonical_bytes(comparable) != canonical_bytes(evaluate()):
        raise ValueError("T2 admission audit differs from current evidence")
    return saved


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--write", action="store_true")
    action.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    if args.write:
        payload = evaluate()
        payload["recorded_at"] = datetime.now(timezone.utc).isoformat()
        if AUDIT.exists():
            raise FileExistsError("refusing to overwrite an existing T2 admission audit")
        AUDIT.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    else:
        payload = verify_saved()
    print(json.dumps({"status": payload["status"], "fit_permitted": False,
                      "blocking_reason_count": len(payload["decision"]["blocking_reasons"]),
                      "fit_callback_not_invoked": payload["fit_callback_not_invoked"]}, sort_keys=True))


if __name__ == "__main__":
    main()
