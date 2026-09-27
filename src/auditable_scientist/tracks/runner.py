"""Policy-guarded, offline execution of the four bounded track evaluators."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..domain import Policy, Tool
from ..policy import ToolRegistry
from ..runtime.canonical import canonical_hash
from ..runtime.replay import ReplayMismatch, fingerprint_file
from .causal import CausalCase, evaluate_causal_fixture
from .common import TrackReceipt
from .dynamics import DynamicsCase, evaluate_dynamics_fixture
from .proof import ProofPackage, ProofState, verify_proof_package
from .protocol import ProtocolSpec, verify_protocol


ROOT = Path(__file__).resolve().parents[3]
TRACK_SOURCES = {"T2": "causal.py", "T3": "dynamics.py", "T4": "proof.py", "T5": "protocol.py"}


@dataclass(frozen=True)
class TrackExecution:
    input_payload: Any
    receipt: TrackReceipt
    negative_case: dict[str, Any]
    calls_used: int


def track_policy(track_id: str, fixture_path: Path) -> Policy:
    if track_id not in TRACK_SOURCES:
        raise ValueError(f"unsupported track: {track_id}")
    return Policy(
        policy_id=f"offline-{track_id.lower()}-v1",
        network="disabled",
        max_seconds=60,
        max_tool_calls=1,
        allowed_paths=[str(fixture_path.resolve().parent)],
        allowed_providers=[f"internal-{track_id.lower()}-evaluator"],
    )


def track_tool(track_id: str) -> Tool:
    if track_id not in TRACK_SOURCES:
        raise ValueError(f"unsupported track: {track_id}")
    return Tool(
        tool_id=f"{track_id.lower()}-evaluator",
        name=f"{track_id} domain evaluator",
        version="1",
        parameter_schema_ref="schemas/track-tool-call-v1.json",
        deterministic=True,
        network_required=False,
    )


def track_source_paths(track_id: str) -> list[Path]:
    if track_id not in TRACK_SOURCES:
        raise ValueError(f"unsupported track: {track_id}")
    return [
        ROOT / "pyproject.toml",
        ROOT / "src/auditable_scientist/tracks" / TRACK_SOURCES[track_id],
        ROOT / "src/auditable_scientist/tracks/common.py",
        ROOT / "src/auditable_scientist/tracks/run_package.py",
        ROOT / "src/auditable_scientist/tracks/runner.py",
        ROOT / "src/auditable_scientist/domain/models.py",
        ROOT / "src/auditable_scientist/policy/runtime.py",
        ROOT / "src/auditable_scientist/runtime/canonical.py",
        ROOT / "src/auditable_scientist/runtime/environment.py",
        ROOT / "src/auditable_scientist/runtime/event_log.py",
        ROOT / "src/auditable_scientist/runtime/replay.py",
        ROOT / "src/auditable_scientist/runtime/run_integrity.py",
        ROOT / "src/auditable_scientist/cli.py",
        ROOT / "src/auditable_scientist/track_cli.py",
        ROOT / "scripts/generate_track_artifacts.py",
        ROOT / "docs/EVIDENCE_POLICY.md",
        ROOT / "schemas/track-tool-call-v1.json",
        ROOT / "schemas/track-receipt-v1.json",
        ROOT / "schemas/track-acceptance-v1.json",
        ROOT / "schemas/run.schema.json",
    ]


def _file_record(path: Path, *, allowed_use: list[str]) -> dict[str, Any]:
    fingerprint = fingerprint_file(path)
    try:
        recorded_path = path.relative_to(ROOT).as_posix()
    except ValueError:
        recorded_path = str(path)
    return {
        "path": recorded_path,
        "sha256": fingerprint.sha256,
        "bytes": fingerprint.bytes,
        "provenance_status": "unverified",
        "allowed_use": allowed_use,
    }


def load_track_input(track_id: str, fixture_path: Path) -> Any:
    data = json.loads(fixture_path.read_text(encoding="utf-8"))
    if track_id == "T2":
        if data.get("schema_version") != "causal-fixture-v1":
            raise ValueError("T2 fixture version differs")
        cases = [CausalCase.model_validate(row) for row in data["cases"]]
        return [case.model_dump(mode="json") for case in cases]
    if track_id == "T3":
        if data.get("schema_version") != "dynamics-fixture-v1":
            raise ValueError("T3 fixture version differs")
        cases = [DynamicsCase.model_validate(row) for row in data["cases"]]
        return [case.model_dump(mode="json") for case in cases]
    if track_id == "T4":
        return ProofPackage.model_validate(data).model_dump(mode="json")
    if track_id == "T5":
        return ProtocolSpec.model_validate(data).model_dump(mode="json")
    raise ValueError(f"unsupported track: {track_id}")


def _evaluate(track_id: str, input_payload: Any) -> tuple[TrackReceipt, dict[str, Any]]:
    if track_id == "T2":
        cases = [CausalCase.model_validate(row) for row in input_payload]
        result, receipt = evaluate_causal_fixture(cases)
        negative = {"wrong_coefficient": 1.0, "rejected": result.negative_candidate_rejected}
    elif track_id == "T3":
        cases = [DynamicsCase.model_validate(row) for row in input_payload]
        result, receipt = evaluate_dynamics_fixture(cases)
        negative = {"solver": "explicit-euler", "rejected": result.negative_euler_rejected}
    elif track_id == "T4":
        package = ProofPackage.model_validate(input_payload)
        result = verify_proof_package(package)
        tampered = package.model_copy(update={"trajectory": [*package.trajectory, ProofState(step=len(package.trajectory), mass_a=0, mass_b=4)]})
        negative_result = verify_proof_package(tampered)
        from .common import make_track_receipt

        receipt = make_track_receipt(
            track_id="T4", evaluator_id=result.evaluator_id, input_payload=input_payload,
            evidence_level=result.evidence_level, passed=result.passed,
            negative_case_passed=not negative_result.passed,
            result=result.model_dump(mode="json"),
            blocked_gates=["formal proof backend beyond finite obligation check"],
        )
        negative = negative_result.model_dump(mode="json")
    elif track_id == "T5":
        protocol = ProtocolSpec.model_validate(input_payload)
        result = verify_protocol(protocol)
        bad_steps = [protocol.steps[0].model_copy(update={"provenance_status": "blocked"}), *protocol.steps[1:]]
        negative_result = verify_protocol(protocol.model_copy(update={"steps": bad_steps}))
        from .common import make_track_receipt

        receipt = make_track_receipt(
            track_id="T5", evaluator_id=result.evaluator_id, input_payload=input_payload,
            evidence_level=result.evidence_level, passed=result.passed,
            negative_case_passed=not negative_result.passed,
            result=result.model_dump(mode="json"),
            blocked_gates=["real wet-lab validation and human biosafety review"],
        )
        negative = negative_result.model_dump(mode="json")
    else:
        raise ValueError(f"unsupported track: {track_id}")
    return receipt, negative


def run_registered_track(track_id: str, fixture_path: Path) -> TrackExecution:
    fixture_path = fixture_path.resolve()
    payload = load_track_input(track_id, fixture_path)
    expected_hash = canonical_hash(payload)
    before = fingerprint_file(fixture_path)
    policy = track_policy(track_id, fixture_path)
    registry = ToolRegistry(policy)
    declaration = track_tool(track_id)
    schema = json.loads((ROOT / declaration.parameter_schema_ref).read_text(encoding="utf-8"))

    def handler(arguments: dict[str, Any]) -> tuple[TrackReceipt, dict[str, Any]]:
        if arguments["track_id"] != track_id or Path(arguments["fixture_path"]).resolve() != fixture_path:
            raise ValueError("registered evaluator call differs from requested track or fixture")
        live_payload = load_track_input(track_id, fixture_path)
        if canonical_hash(live_payload) != arguments["input_hash"]:
            raise ReplayMismatch("fixture content differs from registered input hash")
        return _evaluate(track_id, live_payload)

    registry.register(declaration, handler, argument_schema=schema)
    receipt, negative = registry.invoke(
        declaration.tool_id,
        {"track_id": track_id, "input_hash": expected_hash, "fixture_path": str(fixture_path)},
        path_refs=[str(fixture_path)],
        provider_id=policy.allowed_providers[0],
    )
    if fingerprint_file(fixture_path) != before or receipt.input_hash != expected_hash or registry.calls_used != 1:
        raise ReplayMismatch("registered evaluator input changed during execution")
    if not receipt.passed or not receipt.negative_case_passed:
        raise ValueError(f"{track_id} bounded positive or negative gate failed")
    receipt = TrackReceipt.model_validate({
        **receipt.model_dump(mode="json"),
        "evidence_files": [_file_record(fixture_path, allowed_use=["offline-fixture", "bounded-evaluator"])],
        "source_files": [
            _file_record(path, allowed_use=["offline-evaluator", "source-provenance"])
            for path in track_source_paths(track_id)
        ],
    })
    return TrackExecution(input_payload=payload, receipt=receipt, negative_case=negative, calls_used=registry.calls_used)
