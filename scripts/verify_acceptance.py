"""Fail-closed verifier for the local T1–T5 acceptance receipts."""

from __future__ import annotations

import json
from pathlib import Path

from auditable_scientist.domain import Run
from auditable_scientist.runtime.event_log import EventLog
from auditable_scientist.runtime.replay import ReplayManifest, fingerprint_file
from auditable_scientist.tracks.common import TrackReceipt


ROOT = Path(__file__).resolve().parents[1]


def load(path: str) -> dict:
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def main() -> None:
    acceptance = load("artifacts/acceptance.json")
    if acceptance["status"] != "accepted-with-bounded-scope":
        raise SystemExit("T1 acceptance status is not bounded acceptance")
    if any(item.get("exit_code") != 0 for item in acceptance["checks"]):
        raise SystemExit("an acceptance command did not pass")

    run_dir = ROOT / "artifacts/acceptance-runs-v3/run-7a65020acaf83cfc"
    run = Run.model_validate(json.loads((run_dir / "run.json").read_text(encoding="utf-8")))
    EventLog(run_dir / "events.jsonl").verify()
    input_payload = json.loads((run_dir / "input.json").read_text(encoding="utf-8"))
    manifest = ReplayManifest.load(run_dir / "replay-manifest.json")
    experiment = json.loads((run_dir / "experiment.json").read_text(encoding="utf-8"))
    replay_receipt = manifest.verify(
        input_payload=input_payload,
        source_paths=[item.path for item in manifest.source_files],
        evidence_paths=[item.path for item in manifest.evidence_files],
        candidate_order=experiment["candidate_order"],
        computational_output=experiment,
    )
    if not replay_receipt.verified:
        raise SystemExit("T1 replay receipt did not verify")

    portfolio = load("artifacts/track-portfolio.json")
    if [item["track_id"] for item in portfolio["tracks"]] != ["T1", "T2", "T3", "T4", "T5"]:
        raise SystemExit("portfolio track order or membership is incomplete")
    for track_id in ("T2", "T3", "T4", "T5"):
        item = next(entry for entry in portfolio["tracks"] if entry["track_id"] == track_id)
        track_receipt = TrackReceipt.model_validate(item)
        if not track_receipt.evidence_files:
            raise SystemExit(f"track {track_id} has no file-level evidence receipt")
        for evidence in track_receipt.evidence_files:
            path = ROOT / evidence.path
            fingerprint = fingerprint_file(path)
            if fingerprint.sha256 != evidence.sha256 or fingerprint.bytes != evidence.bytes:
                raise SystemExit(f"track {track_id} evidence changed: {evidence.path}")
        if not item["passed"] or not item["negative_case_passed"]:
            raise SystemExit(f"track {track_id} did not pass its positive and negative gates")
    t1 = next(entry for entry in portfolio["tracks"] if entry["track_id"] == "T1")
    for evidence in t1["evidence_files"]:
        path = ROOT / evidence["path"]
        fingerprint = fingerprint_file(path)
        if fingerprint.sha256 != evidence["sha256"] or fingerprint.bytes != evidence["bytes"]:
            raise SystemExit(f"T1 evidence changed: {evidence['path']}")
    t5 = load("artifacts/t5-protocol/acceptance.json")
    if t5["evaluator"]["result"]["execution_allowed"] is not False:
        raise SystemExit("T5 execution boundary was widened")

    result = {
        "schema_version": "acceptance-verification-v1",
        "status": "verified",
        "t1_replay": replay_receipt.model_dump(mode="json"),
        "run_status": run.status.value,
        "tracks": [item["track_id"] for item in portfolio["tracks"]],
        "scientific_boundaries": portfolio["global_boundaries"],
    }
    destination = ROOT / "artifacts/acceptance-verification.json"
    destination.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
