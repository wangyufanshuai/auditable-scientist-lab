"""Policy-guarded, offline execution of the four bounded track evaluators."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..domain import Policy, Tool
from ..policy import ToolRegistry
from ..runtime.canonical import canonical_hash
from ..runtime.paths import checkout_root, project_root, resource_path, source_path
from ..runtime.replay import BoundPaths, ReplayMismatch, fingerprint_file
from .causal import CausalCase, evaluate_causal_fixture
from .common import TrackReceipt
from .dynamics import DynamicsCase, evaluate_dynamics_fixture
from .nbody import NBodyCase, evaluate_nbody_fixture
from .oscillator_proof import OscillatorProofPackage, verify_oscillator_package
from .physical_world import PhysicalCase, evaluate_physical_fixture
from .proof import ProofPackage, verify_proof_package
from .protocol import ProtocolSpec, verify_protocol


ROOT = project_root()
TRACK_SOURCES = {"T2": "causal.py", "T2P": "physical_world.py", "T3": "dynamics.py", "T3N": "nbody.py", "T4": "proof.py", "T4O": "oscillator_proof.py", "T5": "protocol.py"}


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
        allowed_paths=[str(fixture_path.resolve())],
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
    sources = [
        f"tracks/{TRACK_SOURCES[track_id]}", "tracks/common.py", "tracks/run_package.py",
        "tracks/runner.py", "domain/models.py", "policy/runtime.py", "runtime/canonical.py",
        "runtime/environment.py", "runtime/event_log.py", "runtime/replay.py",
        "runtime/run_integrity.py", "runtime/paths.py", "cli.py", "track_cli.py",
    ]
    if track_id == "T3":
        sources.insert(1, "tracks/reference_rk4.py")
    if track_id == "T3N":
        sources.insert(1, "tracks/reference_nbody_rk4.py")
    if track_id == "T4O":
        sources[1:1] = ["tracks/dynamics.py", "tracks/reference_rk4.py", "tools/dimensions.py"]
    resources = [
        "pyproject.toml", "docs/EVIDENCE_POLICY.md", "schemas/track-tool-call-v1.json",
        "schemas/track-receipt-v1.json", "schemas/track-acceptance-v1.json", "schemas/run.schema.json",
    ]
    if track_id == "T3":
        resources.append("docs/T3_METHOD.md")
    if track_id == "T2P":
        resources.append("docs/T2_PHYSICAL_METHOD.md")
    if track_id == "T3N":
        resources.append("docs/T3_NBODY_METHOD.md")
    if track_id in ("T4", "T4O"):
        resources.append("docs/T4_METHOD.md")
    if track_id == "T5":
        resources.append("docs/T5_METHOD.md")
    paths = [source_path(f"src/auditable_scientist/{item}") for item in sources]
    root = checkout_root()
    if root is not None:
        paths.append(root / "scripts/generate_track_artifacts.py")
    return [*paths, *[resource_path(item) for item in resources]]


def _file_record(path: Path, *, allowed_use: list[str], bindings: BoundPaths | None = None) -> dict[str, Any]:
    fingerprint = fingerprint_file(path)
    if bindings is not None:
        recorded_path = bindings.ref(path)
    else:
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
    if track_id == "T2P":
        if data.get("schema_version") != "physical-world-fixture-v1":
            raise ValueError("T2P fixture version differs")
        cases = [PhysicalCase.model_validate(row) for row in data["cases"]]
        return [case.model_dump(mode="json") for case in cases]
    if track_id == "T3N":
        if data.get("schema_version") != "nbody-fixture-v1":
            raise ValueError("T3N fixture version differs")
        cases = [NBodyCase.model_validate(row) for row in data["cases"]]
        return [case.model_dump(mode="json") for case in cases]
    if track_id == "T4":
        return ProofPackage.model_validate(data).model_dump(mode="json")
    if track_id == "T4O":
        return OscillatorProofPackage.model_validate(data).model_dump(mode="json")
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
    elif track_id == "T2P":
        cases = [PhysicalCase.model_validate(row) for row in input_payload]
        result, receipt = evaluate_physical_fixture(cases)
        negative = {"estimator": "ignores-intervention", "holdout_rmse": result.ignored_intervention_holdout_rmse, "rejected": result.ignored_intervention_rejected}
    elif track_id == "T3N":
        cases = [NBodyCase.model_validate(row) for row in input_payload]
        result, receipt = evaluate_nbody_fixture(cases)
        negative = {"force": "repulsive", "position_error": result.negative_repulsive_force_error, "rejected": result.negative_force_rejected}
    elif track_id == "T4":
        package = ProofPackage.model_validate(input_payload)
        result = verify_proof_package(package)
        changed_state = package.trajectory[-1].model_copy(update={"mass_b": package.trajectory[-1].mass_b + 1})
        changed_trajectory = [*package.trajectory[:-1], changed_state]
        tampered = package.model_copy(update={
            "trajectory": changed_trajectory,
            "trajectory_hash": canonical_hash([item.model_dump(mode="json") for item in changed_trajectory]),
        })
        negative_result = verify_proof_package(tampered)
        from .common import make_track_receipt

        receipt = make_track_receipt(
            track_id="T4", evaluator_id=result.evaluator_id, input_payload=input_payload,
            evidence_level=result.evidence_level, passed=result.passed,
            negative_case_passed=not negative_result.passed,
            result=result.model_dump(mode="json"),
            blocked_gates=["general formal proof backend beyond this fixed transfer rule"],
        )
        negative = negative_result.model_dump(mode="json")
    elif track_id == "T4O":
        package = OscillatorProofPackage.model_validate(input_payload)
        result = verify_oscillator_package(package)
        altered_output = package.output.model_copy(update={"final_x": package.output.final_x + 0.1})
        tampered = package.model_copy(update={
            "output": altered_output,
            "output_hash": canonical_hash(altered_output.model_dump(mode="json")),
        })
        negative_result = verify_oscillator_package(tampered)
        from .common import make_track_receipt

        receipt = make_track_receipt(
            track_id="T4O", evaluator_id=result.evaluator_id, input_payload=input_payload,
            evidence_level=result.evidence_level, passed=result.passed,
            negative_case_passed=not negative_result.passed,
            result=result.model_dump(mode="json"),
            blocked_gates=["external formal proof backend", "reviewed physics model and real-world validation"],
        )
        negative = negative_result.model_dump(mode="json")
    elif track_id == "T5":
        protocol = ProtocolSpec.model_validate(input_payload)
        result = verify_protocol(protocol)
        changed_document = protocol.documents[0].model_copy(update={
            "text": protocol.documents[0].text.replace("buffer", "water", 1),
        })
        negative_result = verify_protocol(protocol.model_copy(update={
            "documents": [changed_document, *protocol.documents[1:]],
        }))
        from .common import make_track_receipt

        receipt = make_track_receipt(
            track_id="T5", evaluator_id=result.evaluator_id, input_payload=input_payload,
            evidence_level=result.evidence_level, passed=result.passed,
            negative_case_passed=not negative_result.passed,
            result=result.model_dump(mode="json"),
            blocked_gates=["independent source and rights validation", "real wet-lab validation and human biosafety review"],
        )
        negative = negative_result.model_dump(mode="json")
    else:
        raise ValueError(f"unsupported track: {track_id}")
    return receipt, negative


def run_registered_track(track_id: str, fixture_path: Path, *, bindings: BoundPaths | None = None) -> TrackExecution:
    fixture_path = fixture_path.resolve()
    payload = load_track_input(track_id, fixture_path)
    expected_hash = canonical_hash(payload)
    before = fingerprint_file(fixture_path)
    policy = track_policy(track_id, fixture_path)
    registry = ToolRegistry(policy)
    declaration = track_tool(track_id)
    schema = json.loads(resource_path(declaration.parameter_schema_ref).read_text(encoding="utf-8"))

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
        "evidence_files": [_file_record(fixture_path, allowed_use=["offline-fixture", "bounded-evaluator"], bindings=bindings)],
        "source_files": [
            _file_record(path, allowed_use=["offline-evaluator", "source-provenance"], bindings=bindings)
            for path in track_source_paths(track_id)
        ],
    })
    return TrackExecution(input_payload=payload, receipt=receipt, negative_case=negative, calls_used=registry.calls_used)
