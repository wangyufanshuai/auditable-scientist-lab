"""Fail-closed verifier for the local T1–T5 acceptance receipts."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from jsonschema import Draft202012Validator

from auditable_scientist.cli import _replay
from auditable_scientist.domain import Run
from auditable_scientist.adapters import Project05Adapter, Project05Snapshot
from auditable_scientist.runtime.event_log import EventLog
from auditable_scientist.runtime.canonical import canonical_hash
from auditable_scientist.runtime.replay import ReplayReceipt, fingerprint_file
from auditable_scientist.tracks.causal import CausalCase, evaluate_causal_fixture
from auditable_scientist.tracks.common import TrackReceipt
from auditable_scientist.tracks.dynamics import DynamicsCase, evaluate_dynamics_fixture
from auditable_scientist.tracks.proof import ProofPackage, ProofState, verify_proof_package
from auditable_scientist.tracks.protocol import ProtocolSpec, ProtocolStep, verify_protocol


ROOT = Path(__file__).resolve().parents[1]


def load(path: str) -> dict:
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def verify_check_rows(checks: list[dict], *, root: Path, expected_input: str | None = None) -> None:
    if not checks:
        raise ValueError("acceptance package has no command receipts")
    for check in checks:
        if not check.get("name") or not check.get("command") or check.get("exit_code") != 0:
            raise ValueError("acceptance command is missing, failed, or unnamed")
        if not check.get("input_version") or not check.get("output_path") or not check.get("recorded_at"):
            raise ValueError("acceptance command is missing version, output path, or timestamp")
        timestamp = datetime.fromisoformat(check["recorded_at"].replace("Z", "+00:00"))
        if timestamp.tzinfo is None or timestamp.utcoffset() is None:
            raise ValueError("acceptance timestamp must include a timezone")
        output = Path(check["output_path"])
        if output.is_absolute() or ".." in output.parts or not (root / output).exists():
            raise ValueError("acceptance command result path is missing or unsafe")
        if expected_input is not None and check["input_version"] != expected_input:
            raise ValueError("acceptance command input version differs from fixture hash")


def verify_track_bundle(track_id: str, item: dict, bundle_dir: Path, *, root: Path = ROOT) -> None:
    receipt = TrackReceipt.model_validate(item)
    if receipt.track_id != track_id or not receipt.passed or not receipt.negative_case_passed:
        raise ValueError(f"track {track_id} evaluator gates or identity failed")
    if not receipt.evidence_files or not receipt.source_files:
        raise ValueError(f"track {track_id} has no evidence or source fingerprints")
    for record in [*receipt.evidence_files, *receipt.source_files]:
        relative = Path(record.path)
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError(f"track {track_id} has an unsafe source or evidence path")
        fingerprint = fingerprint_file(root / relative)
        if fingerprint.sha256 != record.sha256 or fingerprint.bytes != record.bytes:
            raise ValueError(f"track {track_id} source or evidence changed: {record.path}")
    for filename in ("acceptance.json", "test-report.md", "demo-transcript.md", "sample-run.json", "events.jsonl"):
        if not (bundle_dir / filename).is_file():
            raise ValueError(f"track {track_id} evidence package is missing: {filename}")
    acceptance = json.loads((bundle_dir / "acceptance.json").read_text(encoding="utf-8"))
    schema = json.loads((root / "schemas/track-acceptance-v1.json").read_text(encoding="utf-8"))
    Draft202012Validator(schema).validate(acceptance)
    verify_check_rows(acceptance["checks"], root=root, expected_input=receipt.input_hash)
    if acceptance["track"] != track_id or canonical_hash(acceptance["evaluator"]) != canonical_hash(item):
        raise ValueError(f"track {track_id} acceptance package differs from portfolio receipt")
    if acceptance["evidence_boundaries"] != {
        "demo": True,
        "validated_reproduction": item["evidence_level"] == "validated-reproduction",
        "real_data": False,
        "research_candidate": False,
    }:
        raise ValueError(f"track {track_id} evidence boundaries are incomplete")
    sample = json.loads((bundle_dir / "sample-run.json").read_text(encoding="utf-8"))
    if sample.get("track") != track_id or sample.get("input_hash") != item["input_hash"]:
        raise ValueError(f"track {track_id} sample identity differs from receipt")
    for key, expected in (
        ("evaluator", item["result"]),
        ("negative_case", acceptance["negative_case"]),
        ("evidence_files", item["evidence_files"]),
        ("source_files", item["source_files"]),
    ):
        if canonical_hash(sample.get(key)) != canonical_hash(expected):
            raise ValueError(f"track {track_id} sample {key} differs from receipt")
    run_schema = json.loads((root / "schemas/run.schema.json").read_text(encoding="utf-8"))
    Draft202012Validator(run_schema).validate(sample["run"])
    run = Run.model_validate(sample["run"])
    if run.input_hash != item["input_hash"] or run.run_id != f"run-{track_id.lower()}-{item['input_hash'][:16]}":
        raise ValueError(f"track {track_id} shared Run differs from receipt")
    if run.agent is None or not run.tools or not run.memories or not run.evaluators or not run.providers or run.policy is None:
        raise ValueError(f"track {track_id} shared kernel records are incomplete")
    if run.policy.network != "disabled" or run.providers[0].provider_id not in run.policy.allowed_providers:
        raise ValueError(f"track {track_id} policy/provider binding is inconsistent")
    if run.evaluators[0].evaluator_id != receipt.evaluator_id or len(run.claims) != 1 or run.claims[0].status.value != "unverified":
        raise ValueError(f"track {track_id} evaluator or claim boundary differs from receipt")
    if run.tools[0].parameter_schema_ref != "schemas/track-tool-call-v1.json":
        raise ValueError(f"track {track_id} tool schema reference is inconsistent")
    for evidence in run.evidence:
        path = Path(evidence.path_or_uri)
        if not path.resolve().is_relative_to(root.resolve()) or fingerprint_file(path).sha256 != evidence.sha256:
            raise ValueError(f"track {track_id} Run evidence changed: {evidence.evidence_id}")
    evaluator_sources = {record.sha256 for record in receipt.source_files if record.path.endswith(("causal.py", "dynamics.py", "proof.py", "protocol.py"))}
    if {evidence.sha256 for evidence in run.evidence if evidence.kind.value == "code"} != evaluator_sources:
        raise ValueError(f"track {track_id} Run code evidence differs from source receipt")
    events = EventLog(bundle_dir / "events.jsonl").verify()
    if canonical_hash(events) != canonical_hash(run.events):
        raise ValueError(f"track {track_id} Run events do not match events.jsonl")
    trace_entries = [{"seq": event.seq, "event_type": event.event_type, "payload_hash": event.payload_hash} for event in events]
    if len(run.traces) != 1 or canonical_hash(run.traces[0].entries) != canonical_hash(trace_entries):
        raise ValueError(f"track {track_id} trace differs from events.jsonl")
    required_events = {"run.initialized", "policy.applied", "evaluator.completed", "negative_case.checked", "run.completed"}
    by_type = {event.event_type: event for event in events}
    if not required_events.issubset(by_type):
        raise ValueError(f"track {track_id} event lifecycle is incomplete")
    if by_type["run.initialized"].payload != {"run_id": run.run_id, "input_hash": run.input_hash}:
        raise ValueError(f"track {track_id} initialization event differs from Run")
    if by_type["run.completed"].payload.get("status") != run.status.value:
        raise ValueError(f"track {track_id} completion event differs from Run")
    if by_type["evaluator.completed"].payload != {"evaluator_id": receipt.evaluator_id, "result": item["result"]}:
        raise ValueError(f"track {track_id} evaluator event differs from receipt")
    if by_type["negative_case.checked"].payload != {
        "negative_case": acceptance["negative_case"], "negative_case_passed": receipt.negative_case_passed
    }:
        raise ValueError(f"track {track_id} negative event differs from receipt")


def main() -> None:
    acceptance = load("artifacts/acceptance.json")
    if acceptance["status"] != "accepted-with-bounded-scope":
        raise SystemExit("T1 acceptance status is not bounded acceptance")
    verify_check_rows(acceptance["checks"], root=ROOT)

    run_dir = ROOT / "artifacts/acceptance-runs-v8/run-7a65020acaf83cfc"
    run_payload = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
    Draft202012Validator(load("schemas/run.schema.json")).validate(run_payload)
    run = Run.model_validate(run_payload)
    if run.agent is None or not run.tools or not run.memories or not run.evaluators or not run.providers or run.policy is None:
        raise SystemExit("T1 run is missing a shared kernel record")
    if run.policy.network != "disabled" or run.providers[0].provider_id not in run.policy.allowed_providers:
        raise SystemExit("T1 policy/provider binding is inconsistent")
    project05_snapshot = Project05Snapshot.model_validate(json.loads((run_dir / "project05-snapshot.json").read_text(encoding="utf-8")))
    if project05_snapshot.status != "blocked" and not Project05Adapter(project05_snapshot.source_path).verify_snapshot(project05_snapshot):
        raise SystemExit("project-05 source snapshot changed")
    t1_events = EventLog(run_dir / "events.jsonl").verify()
    if canonical_hash(t1_events) != canonical_hash(run.events):
        raise SystemExit("T1 run.json events do not match the append-only event log")
    required_t1_events = {
        "run.initialized",
        "plan.created",
        "policy.applied",
        "data.summarized",
        "tool.invoked",
        "candidate_set.committed",
        "holdout.evaluated",
        "calculation.completed",
        "failure.checked",
        "approval.recorded",
        "run.completed",
    }
    if not required_t1_events.issubset({event.event_type for event in t1_events}):
        raise SystemExit("T1 event log is missing a required lifecycle event")
    if not run.traces or canonical_hash(run.traces[0].entries) != canonical_hash(
        [{"seq": event.seq, "event_type": event.event_type, "payload_hash": event.payload_hash} for event in t1_events]
    ):
        raise SystemExit("T1 trace does not cover the event log")
    replay_receipt = ReplayReceipt.model_validate(_replay(run_dir))
    if not replay_receipt.verified:
        raise SystemExit("T1 replay receipt did not verify")
    if canonical_hash(load("artifacts/sample-run.json")) != canonical_hash(run_payload):
        raise SystemExit("T1 sample run differs from the accepted run")

    portfolio = load("artifacts/track-portfolio.json")
    status = load("artifacts/portfolio-status.json")
    if status.get("public_release_allowed") is not False or status.get("pushed") is not False:
        raise SystemExit("portfolio release boundary is not fail-closed")
    if [item["track_id"] for item in status.get("tracks", [])] != ["T1", "T2", "T3", "T4", "T5"]:
        raise SystemExit("portfolio status table is incomplete")
    if not (ROOT / "artifacts/portfolio-status.md").is_file():
        raise SystemExit("portfolio status markdown is missing")
    if [item["track_id"] for item in portfolio["tracks"]] != ["T1", "T2", "T3", "T4", "T5"]:
        raise SystemExit("portfolio track order or membership is incomplete")
    for track_id in ("T2", "T3", "T4", "T5"):
        item = next(entry for entry in portfolio["tracks"] if entry["track_id"] == track_id)
        directory = {
            "T2": "t2-causal",
            "T3": "t3-dynamics",
            "T4": "t4-proof",
            "T5": "t5-protocol",
        }[track_id]
        bundle_dir = ROOT / "artifacts" / directory
        verify_track_bundle(track_id, item, bundle_dir)

    t2_item = next(entry for entry in portfolio["tracks"] if entry["track_id"] == "T2")
    t2_fixture = load("examples/causal/fixture.json")
    t2_cases = [CausalCase.model_validate(item) for item in t2_fixture["cases"]]
    t2_eval, t2_receipt = evaluate_causal_fixture(t2_cases)
    if t2_eval.model_dump(mode="json") != t2_item["result"] or t2_receipt.input_hash != t2_item["input_hash"] or not t2_receipt.negative_case_passed:
        raise SystemExit("T2 evaluator replay mismatch")
    t2_negative = load("artifacts/t2-causal/acceptance.json")["negative_case"]
    t2_bad_eval, _ = evaluate_causal_fixture(t2_cases, negative_coefficient=t2_negative["wrong_coefficient"])
    if t2_negative != {"wrong_coefficient": t2_negative["wrong_coefficient"], "rejected": t2_bad_eval.negative_candidate_rejected} or t2_negative["wrong_coefficient"] == t2_eval.coefficient or not t2_bad_eval.negative_candidate_rejected:
        raise SystemExit("T2 negative case replay mismatch")

    t3_item = next(entry for entry in portfolio["tracks"] if entry["track_id"] == "T3")
    t3_fixture = load("examples/dynamics/fixture.json")
    t3_cases = [DynamicsCase.model_validate(item) for item in t3_fixture["cases"]]
    t3_eval, t3_receipt = evaluate_dynamics_fixture(t3_cases)
    if t3_eval.model_dump(mode="json") != t3_item["result"] or t3_receipt.input_hash != t3_item["input_hash"] or not t3_receipt.negative_case_passed:
        raise SystemExit("T3 evaluator replay mismatch")
    if load("artifacts/t3-dynamics/acceptance.json")["negative_case"] != {"solver": "explicit-euler", "rejected": t3_eval.negative_euler_rejected}:
        raise SystemExit("T3 negative case replay mismatch")

    t4_item = next(entry for entry in portfolio["tracks"] if entry["track_id"] == "T4")
    t4_package = ProofPackage.model_validate(load("examples/proof/fixture.json"))
    t4_result = verify_proof_package(t4_package)
    t4_tampered = t4_package.model_copy(update={"trajectory": [*t4_package.trajectory, ProofState(step=2, mass_a=0, mass_b=4)]})
    if t4_result.model_dump(mode="json") != t4_item["result"] or t4_item["input_hash"] != canonical_hash(t4_package.model_dump(mode="json")) or verify_proof_package(t4_tampered).passed:
        raise SystemExit("T4 proof evaluator replay mismatch")
    if load("artifacts/t4-proof/acceptance.json")["negative_case"] != verify_proof_package(t4_tampered).model_dump(mode="json"):
        raise SystemExit("T4 negative case replay mismatch")

    t5_item = next(entry for entry in portfolio["tracks"] if entry["track_id"] == "T5")
    t5_protocol = ProtocolSpec.model_validate(load("examples/protocol/fixture.json"))
    t5_result = verify_protocol(t5_protocol)
    t5_bad_steps = [t5_protocol.steps[0].model_copy(update={"provenance_status": "blocked"}), *t5_protocol.steps[1:]]
    t5_bad = t5_protocol.model_copy(update={"steps": t5_bad_steps})
    if t5_result.model_dump(mode="json") != t5_item["result"] or t5_item["input_hash"] != canonical_hash(t5_protocol.model_dump(mode="json")) or not t5_result.passed or verify_protocol(t5_bad).passed:
        raise SystemExit("T5 protocol evaluator replay mismatch")
    if load("artifacts/t5-protocol/acceptance.json")["negative_case"] != verify_protocol(t5_bad).model_dump(mode="json"):
        raise SystemExit("T5 negative case replay mismatch")
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
