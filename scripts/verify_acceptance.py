"""Fail-closed verifier for the local T1–T5 acceptance receipts."""

from __future__ import annotations

import json
from pathlib import Path

from auditable_scientist.domain import Run
from auditable_scientist.runtime.environment import capture_environment
from auditable_scientist.runtime.event_log import EventLog
from auditable_scientist.runtime.canonical import canonical_hash
from auditable_scientist.runtime.replay import ReplayManifest, fingerprint_file
from auditable_scientist.tracks.causal import CausalCase, evaluate_causal_fixture
from auditable_scientist.tracks.common import TrackReceipt
from auditable_scientist.tracks.dynamics import DynamicsCase, evaluate_dynamics_fixture
from auditable_scientist.tracks.proof import ProofPackage, ProofState, verify_proof_package
from auditable_scientist.tracks.protocol import ProtocolSpec, ProtocolStep, verify_protocol


ROOT = Path(__file__).resolve().parents[1]


def load(path: str) -> dict:
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def main() -> None:
    acceptance = load("artifacts/acceptance.json")
    if acceptance["status"] != "accepted-with-bounded-scope":
        raise SystemExit("T1 acceptance status is not bounded acceptance")
    if any(item.get("exit_code") != 0 for item in acceptance["checks"]):
        raise SystemExit("an acceptance command did not pass")

    run_dir = ROOT / "artifacts/acceptance-runs-v4/run-7a65020acaf83cfc"
    run = Run.model_validate(json.loads((run_dir / "run.json").read_text(encoding="utf-8")))
    EventLog(run_dir / "events.jsonl").verify()
    input_payload = json.loads((run_dir / "input.json").read_text(encoding="utf-8"))
    manifest = ReplayManifest.load(run_dir / "replay-manifest.json")
    experiment = json.loads((run_dir / "experiment.json").read_text(encoding="utf-8"))
    replay_receipt = manifest.verify(
        input_payload=input_payload,
        code_revision=manifest.code_revision,
        environment=capture_environment(manifest.environment.get("packages", {}).keys()),
        seed=input_payload["seed"],
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

    t2_item = next(entry for entry in portfolio["tracks"] if entry["track_id"] == "T2")
    t2_fixture = load("examples/causal/fixture.json")
    t2_cases = [CausalCase.model_validate(item) for item in t2_fixture["cases"]]
    t2_eval, t2_receipt = evaluate_causal_fixture(t2_cases)
    if t2_eval.model_dump(mode="json") != t2_item["result"] or t2_receipt.input_hash != t2_item["input_hash"] or not t2_receipt.negative_case_passed:
        raise SystemExit("T2 evaluator replay mismatch")

    t3_item = next(entry for entry in portfolio["tracks"] if entry["track_id"] == "T3")
    t3_fixture = load("examples/dynamics/fixture.json")
    t3_cases = [DynamicsCase.model_validate(item) for item in t3_fixture["cases"]]
    t3_eval, t3_receipt = evaluate_dynamics_fixture(t3_cases)
    if t3_eval.model_dump(mode="json") != t3_item["result"] or t3_receipt.input_hash != t3_item["input_hash"] or not t3_receipt.negative_case_passed:
        raise SystemExit("T3 evaluator replay mismatch")

    t4_item = next(entry for entry in portfolio["tracks"] if entry["track_id"] == "T4")
    t4_package = ProofPackage.model_validate(load("examples/proof/fixture.json"))
    t4_result = verify_proof_package(t4_package)
    t4_tampered = t4_package.model_copy(update={"trajectory": [*t4_package.trajectory, ProofState(step=2, mass_a=0, mass_b=4)]})
    if t4_result.model_dump(mode="json") != t4_item["result"] or t4_item["input_hash"] != canonical_hash(t4_package.model_dump(mode="json")) or verify_proof_package(t4_tampered).passed:
        raise SystemExit("T4 proof evaluator replay mismatch")

    t5_item = next(entry for entry in portfolio["tracks"] if entry["track_id"] == "T5")
    t5_protocol = ProtocolSpec.model_validate(load("examples/protocol/fixture.json"))
    t5_result = verify_protocol(t5_protocol)
    t5_bad_steps = [t5_protocol.steps[0].model_copy(update={"provenance_status": "blocked"}), *t5_protocol.steps[1:]]
    t5_bad = t5_protocol.model_copy(update={"steps": t5_bad_steps})
    if t5_result.model_dump(mode="json") != t5_item["result"] or t5_item["input_hash"] != canonical_hash(t5_protocol.model_dump(mode="json")) or not t5_result.passed or verify_protocol(t5_bad).passed:
        raise SystemExit("T5 protocol evaluator replay mismatch")
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
        "track_evaluators_replayed": ["T2", "T3", "T4", "T5"],
        "scientific_boundaries": portfolio["global_boundaries"],
    }
    destination = ROOT / "artifacts/acceptance-verification.json"
    destination.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
