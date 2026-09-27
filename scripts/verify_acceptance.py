"""Fail-closed verifier for the local T1–T5 acceptance receipts."""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from jsonschema import Draft202012Validator

from auditable_scientist.cli import _replay
from auditable_scientist.domain import Run
from auditable_scientist.adapters import Project05Adapter, Project05Snapshot
from auditable_scientist.runtime.event_log import EventLog
from auditable_scientist.runtime.canonical import canonical_hash
from auditable_scientist.runtime.replay import BoundPaths, ReplayManifest, ReplayReceipt, fingerprint_file
from auditable_scientist.runtime.run_integrity import verify_run_record
from auditable_scientist.tracks.causal import CausalCase, evaluate_causal_fixture
from auditable_scientist.tracks.common import TrackReceipt
from auditable_scientist.tracks.dynamics import DynamicsCase, evaluate_dynamics_fixture
from auditable_scientist.tracks.proof import ProofPackage, verify_proof_package
from auditable_scientist.tracks.protocol import ProtocolSpec, ProtocolStep, verify_protocol
from auditable_scientist.tracks.runner import run_registered_track
from auditable_scientist.track_cli import replay_track_run


ROOT = Path(__file__).resolve().parents[1]


def load(path: str) -> dict:
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def wheel_source_snapshot_hash(root: Path = ROOT) -> str:
    digest = hashlib.sha256()
    paths = [root / "pyproject.toml", *sorted(
        path for path in (root / "src/auditable_scientist").rglob("*")
        if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc"
    )]
    for path in paths:
        digest.update(path.relative_to(root).as_posix().encode("utf-8") + b"\0")
        digest.update(hashlib.sha256(path.read_bytes()).digest())
    return digest.hexdigest()


def verify_optional_t3_run_static() -> dict:
    """Bind optional solver evidence without importing SciPy into the core environment."""

    audit = load("artifacts/t3-external-run-audit.json")
    input_path = audit.get("run_path", "")
    if (
        audit.get("schema_version") != "t3-external-run-audit-v1"
        or audit.get("status") != "verified-within-pinned-oscillator-grid"
        or not isinstance(input_path, str)
        or not input_path.startswith("artifacts/t3-external-runs/run-t3-scipy-")
        or Path(input_path).is_absolute()
        or ".." in Path(input_path).parts
        or audit.get("relocated_replay_equal") is not True
        or audit.get("result_tamper_rejected") is not True
        or audit.get("license_tamper_rejected") is not True
        or audit.get("policy_denials") != {"wrong_provider_rejected": True, "out_of_scope_path_rejected": True}
        or audit.get("boundaries") != {"oscillator_fixture": True, "multi_body": False, "real_mission": False, "scientific_validity": False, "publication_ready": False}
    ):
        raise ValueError("optional T3 external Run audit is missing or exceeds its boundary")
    recorded_at = datetime.fromisoformat(audit["recorded_at"].replace("Z", "+00:00"))
    if recorded_at.tzinfo is None or recorded_at.utcoffset() is None:
        raise ValueError("optional T3 external Run audit timestamp is naive")
    run_dir = (ROOT / input_path).resolve()
    if not run_dir.is_relative_to((ROOT / "artifacts/t3-external-runs").resolve()):
        raise ValueError("optional T3 external Run escaped its artifact directory")
    bindings = BoundPaths(root=ROOT, run_dir=run_dir)
    saved_input = json.loads((run_dir / "input.json").read_text(encoding="utf-8"))
    saved_result = json.loads((run_dir / "result.json").read_text(encoding="utf-8"))
    receipt = saved_result.get("receipt")
    if (
        saved_input.get("schema_version") != "t3-scipy-run-input-v1"
        or saved_input.get("provider_id") != "scipy-dop853-v1"
        or saved_result.get("provider_id") != "scipy-dop853-v1"
        or run_dir.name != f"run-t3-scipy-{canonical_hash(saved_input)[:16]}"
        or audit.get("run_id") != run_dir.name
        or not isinstance(receipt, dict)
        or receipt.get("status") != "passed-optional-oscillator-cross-check"
        or receipt.get("summary", {}).get("case_count") != 9
        or not all(receipt.get("checks", {}).values())
        or len(receipt.get("checks", {})) != 7
        or receipt.get("environment") != saved_input.get("provider_provenance")
        or receipt.get("grid") != saved_input.get("grid")
        or receipt.get("gates") != saved_input.get("gates")
        or receipt.get("solver") != saved_input.get("solver")
    ):
        raise ValueError("optional T3 external Run input or solver receipt differs")
    static_audit = load("artifacts/t3-external-scipy.json")
    static_audit.pop("recorded_at", None)
    if receipt != static_audit:
        raise ValueError("optional T3 Run differs from independently recorded SciPy audit")
    manifest = ReplayManifest.load(run_dir / "replay-manifest.json")
    if manifest.schema_version != "replay-manifest-v2":
        raise ValueError("optional T3 external Run manifest is not portable")
    required_sources = {
        "root://scripts/verify_t3_external_run.py", "root://scripts/verify_t3_external_scipy.py",
        "root://docs/T3_EXTERNAL_SOLVER.md", "root://requirements-t3-scipy-win-py312.txt",
        "root://schemas/t3-external-tool-call-v1.json",
    }
    source_refs = {item.path for item in manifest.source_files}
    if (
        not required_sources.issubset(source_refs)
        or any(not ref.startswith("root://") for ref in source_refs)
        or {item.path for item in manifest.evidence_files} != {"run://scipy-license.txt", "run://numpy-license.txt"}
        or saved_input.get("source_snapshot_hash") != canonical_hash([
            (item.path.removeprefix("root://"), item.sha256) for item in manifest.source_files
        ])
    ):
        raise ValueError("optional T3 external Run source or license inventory differs")
    run = verify_run_record(run_dir / "run.json", run_dir / "events.jsonl", root=ROOT, bindings=bindings)
    if (
        run.run_id != run_dir.name or run.input_hash != canonical_hash(saved_input)
        or run.status.value != "completed" or run.claims[0].status.value != "unverified"
        or run.policy is None or run.policy.network != "disabled"
        or run.policy.allowed_providers != ["scipy-dop853-v1"]
        or len(run.tools) != 1 or run.tools[0].tool_id != "t3-scipy-dop853-crosscheck-v1"
        or len(run.providers) != 1 or run.providers[0].provider_id != "scipy-dop853-v1"
        or run.environment.get("pinned_wheel_sha256") != audit.get("pinned_wheel_sha256")
        or run.environment.get("installed_license_sha256") != audit.get("license_sha256")
    ):
        raise ValueError("optional T3 external shared Run widened its scope")
    replay = manifest.verify(
        input_payload=saved_input, code_revision=run.code_revision, environment=run.environment,
        seed=run.seed, source_paths=[bindings.resolve(item.path) for item in manifest.source_files],
        evidence_paths=[bindings.resolve(item.path) for item in manifest.evidence_files],
        candidate_order=[], computational_output=receipt, bindings=bindings,
    ).model_dump(mode="json")
    if audit.get("replay") != replay or len(replay["checks"]) != 8:
        raise ValueError("optional T3 external Run audit replay binding differs")
    return replay


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
    verify_check_rows(acceptance["checks"], root=root)
    for check in acceptance["checks"]:
        special_inputs = {
            "bounded-parameter-step-sweep": "t3-sweep-v1",
            "optional-external-solver-run": "t3-external-run-audit-v1",
        } if track_id == "T3" else {}
        expected_input = special_inputs.get(check.get("name"), receipt.input_hash)
        if check["input_version"] != expected_input:
            raise ValueError(f"track {track_id} acceptance command input version differs")
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
        path = BoundPaths(root=root, run_dir=bundle_dir).resolve(evidence.path_or_uri)
        if fingerprint_file(path).sha256 != evidence.sha256:
            raise ValueError(f"track {track_id} Run evidence changed: {evidence.evidence_id}")
    evaluator_sources = {record.sha256 for record in receipt.source_files if record.path.endswith(("causal.py", "dynamics.py", "reference_rk4.py", "proof.py", "protocol.py"))}
    if {evidence.sha256 for evidence in run.evidence if evidence.kind.value == "code"} != evaluator_sources:
        raise ValueError(f"track {track_id} Run code evidence differs from source receipt")
    events = EventLog(bundle_dir / "events.jsonl").verify()
    if canonical_hash(events) != canonical_hash(run.events):
        raise ValueError(f"track {track_id} Run events do not match events.jsonl")
    trace_entries = [{"seq": event.seq, "event_type": event.event_type, "payload_hash": event.payload_hash} for event in events]
    if len(run.traces) != 1 or canonical_hash(run.traces[0].entries) != canonical_hash(trace_entries):
        raise ValueError(f"track {track_id} trace differs from events.jsonl")
    required_events = {"run.initialized", "policy.applied", "tool.invoked", "evaluator.completed", "negative_case.checked", "run.completed"}
    by_type = {event.event_type: event for event in events}
    if not required_events.issubset(by_type):
        raise ValueError(f"track {track_id} event lifecycle is incomplete")
    if by_type["run.initialized"].payload != {"run_id": run.run_id, "input_hash": run.input_hash}:
        raise ValueError(f"track {track_id} initialization event differs from Run")
    if by_type["run.completed"].payload.get("status") != run.status.value:
        raise ValueError(f"track {track_id} completion event differs from Run")
    if by_type["tool.invoked"].payload != {"tool_id": run.tools[0].tool_id, "calls_used": 1}:
        raise ValueError(f"track {track_id} did not record one registered evaluator call")
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

    run_dir = ROOT / "artifacts/acceptance-runs-v15/run-02a00f229aabd3d2"
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
        live = run_registered_track(track_id, ROOT / item["evidence_files"][0]["path"])
        if canonical_hash(live.receipt) != canonical_hash(item) or live.calls_used != 1:
            raise SystemExit(f"track {track_id} registered evaluator replay differs from receipt")

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
    t3_checks = load("artifacts/t3-dynamics/acceptance.json")["checks"]
    if not any(item.get("name") == "bounded-parameter-step-sweep" and item.get("output_path") == "artifacts/t3-sweep.json" for item in t3_checks):
        raise SystemExit("T3 parameter sweep is missing from acceptance")
    sweep = subprocess.run(
        [sys.executable, str(ROOT / "scripts/verify_t3_sweep.py"), "--verify"],
        cwd=ROOT, capture_output=True, text=True, check=False,
    )
    if sweep.returncode != 0:
        raise SystemExit(f"T3 parameter sweep replay failed: {sweep.stderr.strip()}")
    if not any(item.get("name") == "optional-external-solver-run" and item.get("output_path") == "artifacts/t3-external-run-audit.json" for item in t3_checks):
        raise SystemExit("optional T3 external Run is missing from acceptance")
    optional_t3_static_replay = verify_optional_t3_run_static()

    t4_item = next(entry for entry in portfolio["tracks"] if entry["track_id"] == "T4")
    t4_package = ProofPackage.model_validate(load("examples/proof/fixture.json"))
    t4_result = verify_proof_package(t4_package)
    changed_state = t4_package.trajectory[-1].model_copy(update={"mass_b": t4_package.trajectory[-1].mass_b + 1})
    changed_trajectory = [*t4_package.trajectory[:-1], changed_state]
    t4_tampered = t4_package.model_copy(update={
        "trajectory": changed_trajectory,
        "trajectory_hash": canonical_hash([item.model_dump(mode="json") for item in changed_trajectory]),
    })
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

    cli_replays: dict[str, dict] = {}
    for track_id in ("T2", "T3", "T4", "T5"):
        item = next(entry for entry in portfolio["tracks"] if entry["track_id"] == track_id)
        run_dir = ROOT / "artifacts/track-runs-v8" / f"run-{track_id.lower()}-{item['input_hash'][:16]}"
        saved_result = json.loads((run_dir / "result.json").read_text(encoding="utf-8"))
        def without_paths(receipt: dict) -> dict:
            return {
                **receipt,
                "evidence_files": [{**record, "path": "<bound>"} for record in receipt["evidence_files"]],
                "source_files": [{**record, "path": "<bound>"} for record in receipt["source_files"]],
            }
        if canonical_hash(without_paths(saved_result["receipt"])) != canonical_hash(without_paths(item)):
            raise SystemExit(f"track {track_id} CLI Run receipt differs from portfolio")
        cli_replays[track_id] = replay_track_run(run_dir)

    relocation = load("artifacts/relocation-audit.json")
    if (
        relocation.get("status") != "verified-in-recorded-environment"
        or relocation.get("copied_checkout") is not True
        or relocation.get("original_examples_copied") is not False
        or relocation.get("copied_module_imported") is not True
        or relocation.get("tampered_t3_fixture_rejected") is not True
        or relocation.get("script_sha256") != fingerprint_file(ROOT / "scripts/verify_committed_relocation.py").sha256
        or canonical_hash(relocation.get("runs_replayed")) != canonical_hash({"T1": replay_receipt.model_dump(mode="json"), **cli_replays})
    ):
        raise SystemExit("relocation audit is missing or differs from the current five run packages")

    environment_audit = load("artifacts/replay-environment-audit.json")
    constraints = ROOT / "requirements-replay-win-py312.txt"
    pins = {}
    for line in constraints.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            if line.count("==") != 1:
                raise SystemExit("replay environment constraint is not an exact version")
            name, version = line.split("==")
            pins[re.sub(r"[-_.]+", "-", name).lower()] = version
    manifest_paths = {"T1": ROOT / "artifacts/acceptance-runs-v15/run-02a00f229aabd3d2/replay-manifest.json"}
    for track_id in ("T2", "T3", "T4", "T5"):
        receipt = next(item for item in portfolio["tracks"] if item["track_id"] == track_id)
        run_id = f"run-{track_id.lower()}-{receipt['input_hash'][:16]}"
        manifest_paths[track_id] = ROOT / "artifacts/track-runs-v8" / run_id / "replay-manifest.json"
    manifest_hashes = {track_id: hashlib.sha256(path.read_bytes()).hexdigest() for track_id, path in manifest_paths.items()}
    if (
        environment_audit.get("schema_version") != "replay-environment-audit-v1"
        or environment_audit.get("status") != "matched-committed-replay-environment"
        or environment_audit.get("isolated_venv") is not True
        or environment_audit.get("platform") != {key: run.environment[key] for key in ("python", "implementation", "system", "machine")}
        or environment_audit.get("installed_packages") != {**pins, "auditable-scientist-lab": "0.1.0"}
        or environment_audit.get("constraints_sha256") != hashlib.sha256(constraints.read_bytes()).hexdigest()
        or environment_audit.get("manifest_sha256") != manifest_hashes
        or environment_audit.get("script_sha256") != fingerprint_file(ROOT / "scripts/verify_replay_environment.py").sha256
    ):
        raise SystemExit("fresh replay environment audit is missing or differs from current inputs")

    wheel = load("artifacts/wheel-audit.json")
    if (
        wheel.get("schema_version") != "wheel-audit-v2"
        or wheel.get("status") != "verified-within-offline-fixtures"
        or wheel.get("checkout_root_in_installed_process") is not None
        or wheel.get("all_five_relocated_replays_equal") is not True
        or wheel.get("t4_bounded_result_and_unverified_run_claim") is not True
        or wheel.get("bundled_resource_count", 0) < 17
        or wheel.get("python") != run.environment["python"]
        or wheel.get("wheel_artifact_committed") is not False
        or set(wheel.get("replay_manifest_hashes", {})) != {"T1", "T2", "T3", "T4", "T5"}
        or wheel.get("source_snapshot_sha256") != wheel_source_snapshot_hash()
        or wheel.get("script_sha256") != fingerprint_file(ROOT / "scripts/verify_wheel_install.py").sha256
        or not re.fullmatch(r"[a-f0-9]{64}", wheel.get("wheel_sha256", ""))
        or any(wheel.get("boundaries", {}).get(key) is not False for key in ("scientific_validity", "real_data", "research_candidate", "publication_ready", "public_release"))
    ):
        raise SystemExit("wheel audit is missing or differs from the current package")

    result = {
        "schema_version": "acceptance-verification-v1",
        "status": "verified",
        "t1_replay": replay_receipt.model_dump(mode="json"),
        "run_status": run.status.value,
        "tracks": [item["track_id"] for item in portfolio["tracks"]],
        "track_evaluators_replayed": ["T2", "T3", "T4", "T5"],
        "track_cli_replays": cli_replays,
        "t3_optional_external_run_static_replay": optional_t3_static_replay,
        "wheel_audit_verified": True,
        "scientific_boundaries": portfolio["global_boundaries"],
    }
    destination = ROOT / "artifacts/acceptance-verification.json"
    destination.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
