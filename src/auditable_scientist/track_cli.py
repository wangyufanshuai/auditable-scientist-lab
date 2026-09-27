"""Replayable CLI run bundles for bounded T2–T5 fixture evaluations."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

from .domain import ClaimStatus, Run
from .runtime.canonical import canonical_hash, canonical_json
from .runtime.replay import ReplayManifest, ReplayMismatch
from .runtime.paths import resource_path
from .runtime.run_integrity import verify_run_record
from .tracks.run_package import make_track_run
from .tracks.runner import ROOT, run_registered_track, track_source_paths


TASK_IDS = {
    "T2": "t2-causal-intervention-v1",
    "T3": "t3-harmonic-dynamics-v1",
    "T4": "t4-proof-carrying-v1",
    "T5": "t5-bio-chem-protocol-v1",
}
FIXTURE_RESOURCES = {
    "T2": "examples/causal/fixture.json",
    "T3": "examples/dynamics/fixture.json",
    "T4": "examples/proof/fixture.json",
    "T5": "examples/protocol/fixture.json",
}


def init_track_fixture(track_id: str, path: Path) -> Path:
    if track_id not in FIXTURE_RESOURCES:
        raise ValueError(f"unsupported track: {track_id}")
    if path.exists():
        raise FileExistsError(f"refusing to overwrite existing fixture: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(resource_path(FIXTURE_RESOURCES[track_id]), path)
    return path


def _write_json(path: Path, payload: Any) -> None:
    path.write_text(canonical_json(payload) + "\n", encoding="utf-8", newline="\n")


def _render_report(run: Run, result: dict[str, Any], negative_case: dict[str, Any]) -> str:
    track_id = run.environment["track_id"]
    return (
        f"# {track_id} bounded offline run\n\n"
        f"- Run: `{run.run_id}`\n"
        f"- Status: `{run.status.value}`\n"
        f"- Evaluator: `{run.evaluators[0].evaluator_id}`\n"
        f"- Registered tool calls: `1`\n"
        f"- Fixture result: `{canonical_json(result)}`\n"
        f"- Negative control: `{canonical_json(negative_case)}`\n"
        "- Claim status: `unverified`\n"
        "- Real-data, research-candidate, and publication claims: `false`\n\n"
        "This run checks a local fixture only. T5 never authorizes wet-lab execution.\n"
    )


def build_track_run(track_id: str, fixture_path: Path, *, seed: int, output_dir: Path) -> Path:
    if seed < 0:
        raise ValueError("seed must be nonnegative")
    fixture_path = fixture_path.resolve()
    execution = run_registered_track(track_id, fixture_path)
    run = make_track_run(
        track_id=track_id,
        task_id=TASK_IDS[track_id],
        receipt=execution.receipt,
        fixture_path=fixture_path,
        negative_case=execution.negative_case,
        seed=seed,
        calls_used=execution.calls_used,
    )
    if run.policy is None or run.policy.network != "disabled" or run.claims[0].status != ClaimStatus.UNVERIFIED:
        raise ValueError("track Run violated its bounded offline evidence policy")
    run_dir = output_dir / run.run_id
    if run_dir.exists() and any(run_dir.iterdir()):
        raise FileExistsError(f"run directory already exists; choose another output directory: {run_dir}")
    run_dir.mkdir(parents=True, exist_ok=True)
    result = {
        "track_id": track_id,
        "fixture_path": str(fixture_path),
        "receipt": execution.receipt.model_dump(mode="json"),
        "negative_case": execution.negative_case,
    }
    manifest = ReplayManifest.create(
        input_payload=execution.input_payload,
        code_revision=run.code_revision,
        environment=run.environment,
        seed=seed,
        source_paths=track_source_paths(track_id),
        evidence_paths=[fixture_path],
        computational_output={"result": execution.receipt.result, "negative_case": execution.negative_case},
    )
    _write_json(run_dir / "input.json", execution.input_payload)
    _write_json(run_dir / "result.json", result)
    _write_json(run_dir / "run.json", run.model_dump(mode="json"))
    (run_dir / "events.jsonl").write_text(
        "".join(canonical_json(event) + "\n" for event in run.events), encoding="utf-8", newline="\n"
    )
    manifest.write(run_dir / "replay-manifest.json")
    (run_dir / "report.md").write_text(
        _render_report(run, execution.receipt.result, execution.negative_case), encoding="utf-8", newline="\n"
    )
    return run_dir


def replay_track_run(run_dir: Path) -> dict[str, Any]:
    result = json.loads((run_dir / "result.json").read_text(encoding="utf-8"))
    track_id = result["track_id"]
    if track_id not in TASK_IDS:
        raise ReplayMismatch("saved track identifier is unsupported")
    fixture_path = Path(result["fixture_path"]).resolve()
    execution = run_registered_track(track_id, fixture_path)
    saved_input = json.loads((run_dir / "input.json").read_text(encoding="utf-8"))
    if canonical_hash(saved_input) != canonical_hash(execution.input_payload):
        raise ReplayMismatch("saved track input differs from current fixture")
    if canonical_hash(result["receipt"]) != canonical_hash(execution.receipt.model_dump(mode="json")):
        raise ReplayMismatch("saved track receipt differs from deterministic evaluator")
    if canonical_hash(result["negative_case"]) != canonical_hash(execution.negative_case):
        raise ReplayMismatch("saved negative case differs from deterministic evaluator")
    run = verify_run_record(run_dir / "run.json", run_dir / "events.jsonl", root=ROOT)
    expected_run = make_track_run(
        track_id=track_id,
        task_id=TASK_IDS[track_id],
        receipt=execution.receipt,
        fixture_path=fixture_path,
        negative_case=execution.negative_case,
        seed=run.seed,
        calls_used=execution.calls_used,
    )
    if canonical_hash(run) != canonical_hash(expected_run):
        raise ReplayMismatch("saved shared-kernel Run differs from deterministic replay")
    manifest = ReplayManifest.load(run_dir / "replay-manifest.json")
    receipt = manifest.verify(
        input_payload=execution.input_payload,
        code_revision=expected_run.code_revision,
        environment=expected_run.environment,
        seed=run.seed,
        source_paths=track_source_paths(track_id),
        evidence_paths=[fixture_path],
        candidate_order=[],
        computational_output={"result": execution.receipt.result, "negative_case": execution.negative_case},
    )
    if manifest.input_hash != run.input_hash:
        raise ReplayMismatch("track manifest input differs from saved Run")
    expected_report = _render_report(run, execution.receipt.result, execution.negative_case)
    if (run_dir / "report.md").read_text(encoding="utf-8") != expected_report:
        raise ReplayMismatch("track report differs from deterministic replay")
    return receipt.model_dump(mode="json")


def inspect_track_run(run_dir: Path) -> dict[str, Any]:
    run = verify_run_record(run_dir / "run.json", run_dir / "events.jsonl", root=ROOT)
    result = json.loads((run_dir / "result.json").read_text(encoding="utf-8"))
    return {
        "track_id": result["track_id"],
        "run_id": run.run_id,
        "status": run.status.value,
        "claim": run.claims[0].model_dump(mode="json"),
        "evaluator": result["receipt"]["result"],
        "negative_case": result["negative_case"],
    }
