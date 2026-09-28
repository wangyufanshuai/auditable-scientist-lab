"""Create and replay a versioned offline T1 RK4 Tool/Provider Run."""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
from pathlib import Path
import shutil
import tempfile
from typing import Any

from auditable_scientist.domain import (
    Agent, Claim, ClaimStatus, Evidence, EvidenceKind, EvidenceLevel, Evaluator,
    Event, Memory, Observation, Policy, Provider, ProvenanceStatus, Run,
    RunStatus, Tool, Trace,
)
from auditable_scientist.policy import PolicyDenied, ToolRegistry
from auditable_scientist.runtime.canonical import canonical_hash, canonical_json
from auditable_scientist.runtime.environment import capture_environment
from auditable_scientist.runtime.paths import installation_revision
from auditable_scientist.runtime.replay import BoundPaths, ReplayManifest, ReplayMismatch
from auditable_scientist.runtime.run_integrity import verify_run_record

from verify_t1_core_orbit import build_audit


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "examples/hohmann/dataset.json"
STATIC_AUDIT = ROOT / "artifacts/t1-core-orbit-audit.json"
SCHEMA = ROOT / "docs/contracts/t1-core-orbit-tool-call-v1.json"
METHOD = ROOT / "docs/T1_CORE_ORBIT_RUN.md"
MEMORY_SOURCE = ROOT / "docs/EVIDENCE_POLICY.md"
AUDIT = ROOT / "artifacts/t1-core-orbit-run-audit.json"
RUNS = ROOT / "artifacts/t1-core-orbit-runs"
PROVIDER_ID = "internal-rk4-t1-orbit-v1"
TOOL_ID = "t1-core-rk4-apoapsis-v1"
EVALUATOR_ID = "t1-synthetic-rk4-refinement-v1"
SOURCE_PATHS = [
    Path(__file__).resolve(), ROOT / "scripts/verify_t1_core_orbit.py",
    ROOT / "src/auditable_scientist/tools/orbit_integrator.py",
    ROOT / "src/auditable_scientist/tools/numerical.py",
    ROOT / "src/auditable_scientist/domain/models.py",
    ROOT / "src/auditable_scientist/policy/runtime.py",
    ROOT / "src/auditable_scientist/runtime/canonical.py",
    ROOT / "src/auditable_scientist/runtime/environment.py",
    ROOT / "src/auditable_scientist/runtime/replay.py",
    ROOT / "src/auditable_scientist/runtime/run_integrity.py",
    ROOT / "src/auditable_scientist/runtime/paths.py",
    FIXTURE, STATIC_AUDIT, SCHEMA, METHOD, MEMORY_SOURCE,
]


def _digest(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _current_audit() -> dict[str, Any]:
    computed = build_audit()
    saved = json.loads(STATIC_AUDIT.read_text(encoding="utf-8"))
    recorded_at = saved.pop("recorded_at", None)
    if not isinstance(recorded_at, str) or datetime.fromisoformat(recorded_at).tzinfo is None:
        raise ReplayMismatch("standalone T1 orbit audit has no dated receipt")
    if saved != computed or computed["status"] != "verified-synthetic-two-body-only":
        raise ReplayMismatch("standalone T1 orbit audit differs from recomputation")
    return computed


def input_payload() -> dict[str, Any]:
    audit = _current_audit()
    return {
        "schema_version": "t1-core-orbit-run-input-v1",
        "track_id": "T1",
        "provider_id": PROVIDER_ID,
        "case_ids": [row["case_id"] for row in audit["rows"]],
        "fixture_sha256": _digest(FIXTURE),
        "standalone_audit_sha256": _digest(STATIC_AUDIT),
        "source_snapshot_hash": canonical_hash([
            (path.relative_to(ROOT).as_posix(), _digest(path)) for path in SOURCE_PATHS
        ]),
        "gates": audit["gates"],
        "boundaries": audit["boundaries"],
    }


def _policy(dataset_snapshot: Path) -> Policy:
    return Policy(
        policy_id="offline-t1-core-orbit-v1", network="disabled",
        max_seconds=60, max_tool_calls=1,
        allowed_paths=[str(path.resolve()) for path in (*SOURCE_PATHS, dataset_snapshot)],
        allowed_providers=[PROVIDER_ID],
    )


def _tool() -> Tool:
    return Tool(
        tool_id=TOOL_ID, name="Offline RK4 two-body apoapsis propagator", version="1",
        parameter_schema_ref=SCHEMA.relative_to(ROOT).as_posix(),
        deterministic=True, network_required=False,
    )


def _arguments(payload: dict[str, Any], dataset_snapshot: Path) -> dict[str, str]:
    return {
        "provider_id": PROVIDER_ID,
        "input_hash": canonical_hash(payload),
        "dataset_path": str(dataset_snapshot.resolve()),
    }


def execute(payload: dict[str, Any], dataset_snapshot: Path) -> tuple[dict[str, Any], int]:
    registry = ToolRegistry(_policy(dataset_snapshot))
    expected = _arguments(payload, dataset_snapshot)
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))

    def handler(arguments: dict[str, Any]) -> dict[str, Any]:
        if arguments != expected or input_payload() != payload:
            raise ReplayMismatch("T1 RK4 tool input or source differs")
        if dataset_snapshot.read_bytes() != FIXTURE.read_bytes():
            raise ReplayMismatch("T1 RK4 input snapshot differs from registered fixture")
        computed = _current_audit()
        if ([row["case_id"] for row in computed["rows"]] != payload["case_ids"]
                or computed["gates"] != payload["gates"]
                or computed["boundaries"] != payload["boundaries"]):
            raise ReplayMismatch("T1 RK4 case inventory, gates, or boundaries changed")
        return computed

    registry.register(_tool(), handler, argument_schema=schema)
    receipt = registry.invoke(
        TOOL_ID, expected,
        path_refs=[str(path) for path in (*SOURCE_PATHS, dataset_snapshot)],
        provider_id=PROVIDER_ID,
    )
    if registry.calls_used != 1 or not all(receipt["checks"].values()):
        raise ReplayMismatch("T1 RK4 tool call or numerical gate failed")
    return receipt, registry.calls_used


def verify_policy_denials(payload: dict[str, Any], dataset_snapshot: Path) -> dict[str, bool]:
    registry = ToolRegistry(_policy(dataset_snapshot))
    registry.register(_tool(), lambda _arguments: None,
                      argument_schema=json.loads(SCHEMA.read_text(encoding="utf-8")))
    arguments = _arguments(payload, dataset_snapshot)
    try:
        registry.invoke(TOOL_ID, arguments, provider_id="unregistered-provider")
    except PolicyDenied:
        wrong_provider_rejected = True
    else:
        wrong_provider_rejected = False
    try:
        registry.invoke(TOOL_ID, arguments, path_refs=[str(ROOT / "README.md")], provider_id=PROVIDER_ID)
    except PolicyDenied:
        out_of_scope_path_rejected = True
    else:
        out_of_scope_path_rejected = False
    if registry.calls_used != 0 or not wrong_provider_rejected or not out_of_scope_path_rejected:
        raise ReplayMismatch("T1 RK4 policy did not fail closed")
    return {"wrong_provider_rejected": True, "out_of_scope_path_rejected": True}


def _make_run(payload: dict[str, Any], receipt: dict[str, Any], calls_used: int, *, run_dir: Path) -> Run:
    snapshot = run_dir / "dataset.json"
    bindings = BoundPaths(root=ROOT, run_dir=run_dir)
    input_hash = canonical_hash(payload)
    run_id = f"run-t1-core-orbit-{input_hash[:16]}"
    evidence_specs = [
        ("ev-t1-core-dataset", EvidenceKind.DATA, snapshot, ["synthetic-fixture"]),
        ("ev-t1-core-audit", EvidenceKind.SNAPSHOT, STATIC_AUDIT, ["numerical-recomputation"]),
        ("ev-t1-core-integrator", EvidenceKind.CODE,
         ROOT / "src/auditable_scientist/tools/orbit_integrator.py", ["offline-tool"]),
        ("ev-t1-core-method", EvidenceKind.SNAPSHOT, METHOD, ["method-and-boundaries"]),
    ]
    evidence = [Evidence(
        evidence_id=evidence_id, kind=kind, path_or_uri=bindings.ref(path),
        sha256=_digest(path), source_revision=installation_revision(),
        provenance_status=ProvenanceStatus.UNVERIFIED, allowed_use=allowed_use,
        notes="Synthetic circular two-body computation only; dated ephemeris, mission and rights gates remain open.",
    ) for evidence_id, kind, path, allowed_use in evidence_specs]
    policy = _policy(snapshot).model_copy(update={
        "allowed_paths": [bindings.ref(path) for path in (*SOURCE_PATHS, snapshot)],
    })
    base_time = datetime(2026, 9, 27, tzinfo=timezone.utc)
    events: list[Event] = []
    previous = "genesis"
    for seq, (event_type, body) in enumerate([
        ("run.initialized", {"run_id": run_id, "input_hash": input_hash}),
        ("policy.applied", {"policy_id": policy.policy_id, "network": "disabled", "provider_id": PROVIDER_ID}),
        ("tool.invoked", {"tool_id": TOOL_ID, "calls_used": calls_used}),
        ("evaluator.completed", {"evaluator_id": EVALUATOR_ID,
                                 "summary": receipt["summary"], "checks": receipt["checks"]}),
        ("negative_case.checked", {"repulsive_force_rejected": receipt["checks"]["repulsive_force_rejected"]}),
        ("run.completed", {"status": RunStatus.COMPLETED.value}),
    ]):
        payload_hash = canonical_hash(body)
        events.append(Event(
            event_id=f"t1-core-orbit-event-{seq}", seq=seq, event_type=event_type,
            occurred_at=base_time + timedelta(seconds=seq), payload_hash=payload_hash,
            prev_event_hash=previous, payload=body,
        ))
        previous = payload_hash
    trace = Trace(
        trace_id=f"trace-{run_id}", run_id=run_id, input_hash=input_hash,
        entries=[{"seq": item.seq, "event_type": item.event_type, "payload_hash": item.payload_hash}
                 for item in events],
    )
    return Run(
        run_id=run_id, task_id="t1-versioned-core-rk4-crosscheck-v1", created_at=base_time,
        input_hash=input_hash, code_revision=installation_revision(),
        environment={
            **capture_environment(["auditable-scientist-lab", "pydantic", "sympy", "jsonschema"]),
            "mode": "offline", "track_id": "T1", "runtime": "versioned-core-rk4-tool-run",
            "network": "disabled", "provider_id": PROVIDER_ID,
        },
        seed=17, evidence_refs=[item.evidence_id for item in evidence], status=RunStatus.COMPLETED,
        agent=Agent(agent_id="offline-t1-core-orbit-agent-v1", name="Offline T1 numerical agent",
                    version="1", capabilities=["invoke-registered-propagator", "record-negative-control"]),
        tools=[_tool()],
        memories=[Memory(memory_id="evidence-policy-memory-v1", source_ref=bindings.ref(MEMORY_SOURCE),
                         scope="claim-level evidence boundaries", version="local-snapshot",
                         content_hash=_digest(MEMORY_SOURCE))],
        evaluators=[Evaluator(evaluator_id=EVALUATOR_ID, name="T1 synthetic RK4 refinement evaluator",
                              version="1", read_only=True)],
        providers=[Provider(provider_id=PROVIDER_ID, kind="deterministic-numerical-backend",
                            name="Internal fixed-step RK4 propagator", version="1",
                            source_ref="src/auditable_scientist/tools/orbit_integrator.py")],
        policy=policy, events=events, traces=[trace],
        claims=[Claim(
            text="The idealized transfer predicts a dated Mars mission trajectory.",
            status=ClaimStatus.UNVERIFIED, level=EvidenceLevel.DEMO,
            evidence_refs=[item.evidence_id for item in evidence],
            falsification_checks=["two-body-recomputation", "step-refinement",
                                  "repulsive-force-negative", "source-and-snapshot-replay"],
            holdout_verified=False,
        )],
        observations=[Observation(
            observation_id="obs-t1-synthetic-orbits", dataset_hash=input_hash, split="external",
            summary={"case_count": len(receipt["rows"]), "metrics": receipt["summary"]},
            units={"radius": "km", "time_of_flight": "day", "velocity": "km/s"},
            source_ref=bindings.ref(snapshot),
        )],
        evidence=evidence,
    )


def _write_json(path: Path, value: Any) -> None:
    path.write_text(canonical_json(value) + "\n", encoding="utf-8", newline="\n")


def _report(run: Run, receipt: dict[str, Any]) -> str:
    return (
        "# T1 versioned offline RK4 Run\n\n"
        f"- Run: `{run.run_id}`\n"
        f"- Provider: `{PROVIDER_ID}`; tool calls: `1`\n"
        f"- Numerical status: `{receipt['status']}`\n"
        f"- Maximum relative TOF error: `{receipt['summary']['relative_tof_error']}`\n"
        f"- Maximum relative position error: `{receipt['summary']['relative_final_position_error']}`\n"
        f"- Repulsive-force negative: `{receipt['checks']['repulsive_force_rejected']}`\n"
        f"- Real-world Claim: `{run.claims[0].status.value}`; level: `{run.claims[0].level.value}`\n\n"
        "The nine fixture cases are synthetic. Initial speed uses vis-viva; no dated ephemeris, "
        "mission trajectory, independent orbit derivation, or publication validity is established.\n"
    )


def write_run() -> Path:
    payload = input_payload()
    run_dir = RUNS / f"run-t1-core-orbit-{canonical_hash(payload)[:16]}"
    if run_dir.exists():
        raise FileExistsError(f"refusing to overwrite existing T1 core orbit Run: {run_dir}")
    run_dir.mkdir(parents=True)
    snapshot = run_dir / "dataset.json"
    shutil.copyfile(FIXTURE, snapshot)
    receipt, calls_used = execute(payload, snapshot)
    run = _make_run(payload, receipt, calls_used, run_dir=run_dir)
    bindings = BoundPaths(root=ROOT, run_dir=run_dir)
    _write_json(run_dir / "input.json", payload)
    _write_json(run_dir / "result.json", {"provider_id": PROVIDER_ID, "receipt": receipt})
    _write_json(run_dir / "run.json", run.model_dump(mode="json"))
    (run_dir / "events.jsonl").write_text(
        "".join(canonical_json(event) + "\n" for event in run.events), encoding="utf-8", newline="\n",
    )
    ReplayManifest.create(
        input_payload=payload, code_revision=run.code_revision, environment=run.environment,
        seed=run.seed, source_paths=SOURCE_PATHS, evidence_paths=[snapshot],
        candidate_order=[], computational_output=receipt, bindings=bindings,
    ).write(run_dir / "replay-manifest.json")
    (run_dir / "report.md").write_text(_report(run, receipt), encoding="utf-8", newline="\n")
    return run_dir


def replay_run(run_dir: Path) -> dict[str, Any]:
    run_dir = run_dir.resolve()
    bindings = BoundPaths(root=ROOT, run_dir=run_dir)
    manifest = ReplayManifest.load(run_dir / "replay-manifest.json")
    if manifest.schema_version != "replay-manifest-v2":
        raise ReplayMismatch("T1 core orbit Run requires a portable replay manifest")
    payload = input_payload()
    if (json.loads((run_dir / "input.json").read_text(encoding="utf-8")) != payload
            or run_dir.name != f"run-t1-core-orbit-{canonical_hash(payload)[:16]}"):
        raise ReplayMismatch("saved T1 core orbit input or identity changed")
    snapshot = run_dir / "dataset.json"
    receipt, calls_used = execute(payload, snapshot)
    if json.loads((run_dir / "result.json").read_text(encoding="utf-8")) != {
            "provider_id": PROVIDER_ID, "receipt": receipt}:
        raise ReplayMismatch("saved T1 core orbit numerical output changed")
    run = verify_run_record(run_dir / "run.json", run_dir / "events.jsonl", root=ROOT, bindings=bindings)
    expected = _make_run(payload, receipt, calls_used, run_dir=run_dir)
    if canonical_hash(run) != canonical_hash(expected):
        raise ReplayMismatch("saved T1 core orbit shared-kernel Run changed")
    replay = manifest.verify(
        input_payload=payload, code_revision=expected.code_revision,
        environment=expected.environment, seed=expected.seed,
        source_paths=SOURCE_PATHS, evidence_paths=[snapshot], candidate_order=[],
        computational_output=receipt, bindings=bindings,
    ).model_dump(mode="json")
    if (run_dir / "report.md").read_text(encoding="utf-8") != _report(run, receipt):
        raise ReplayMismatch("saved T1 core orbit report changed")
    return replay


def verify_run_and_mutations(run_dir: Path) -> dict[str, Any]:
    original = replay_run(run_dir)
    with tempfile.TemporaryDirectory(prefix="scientist-t1-core-orbit-") as temporary:
        relocated = Path(temporary).resolve() / run_dir.name
        if not relocated.is_relative_to(Path(tempfile.gettempdir()).resolve()):
            raise ReplayMismatch("T1 core orbit temporary relocation escaped the temp directory")
        shutil.copytree(run_dir, relocated)
        if replay_run(relocated) != original:
            raise ReplayMismatch("relocated T1 core orbit Run differs")
        result_path = relocated / "result.json"
        saved_result = result_path.read_bytes()
        changed = json.loads(saved_result)
        changed["receipt"]["summary"]["relative_tof_error"] = 0.5
        _write_json(result_path, changed)
        try:
            replay_run(relocated)
        except ReplayMismatch:
            result_tamper_rejected = True
        else:
            result_tamper_rejected = False
        result_path.write_bytes(saved_result)
        snapshot = relocated / "dataset.json"
        snapshot.write_bytes(snapshot.read_bytes() + b"\n ")
        try:
            replay_run(relocated)
        except ReplayMismatch:
            snapshot_tamper_rejected = True
        else:
            snapshot_tamper_rejected = False
    if not result_tamper_rejected or not snapshot_tamper_rejected:
        raise ReplayMismatch("T1 core orbit Run mutation controls failed")
    return {
        "schema_version": "t1-core-orbit-run-audit-v1",
        "status": "verified-synthetic-two-body-run-only",
        "run_path": run_dir.relative_to(ROOT).as_posix(),
        "run_id": run_dir.name,
        "replay": original,
        "relocated_replay_equal": True,
        "result_tamper_rejected": True,
        "snapshot_tamper_rejected": True,
        "provider_id": PROVIDER_ID,
        "provider_version": "internal-rk4-v1",
        "policy_denials": verify_policy_denials(input_payload(), run_dir / "dataset.json"),
        "boundaries": {
            "synthetic_two_body_grid": True,
            "shared_kernel_run": True,
            "main_cli_integrated": False,
            "independent_orbit_derivation": False,
            "real_data": False,
            "dated_ephemeris": False,
            "mission_validity": False,
            "publication_ready": False,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--write", action="store_true")
    action.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    if args.write:
        run_dir = write_run()
        result = verify_run_and_mutations(run_dir)
        result["recorded_at"] = datetime.now(timezone.utc).isoformat()
        AUDIT.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    else:
        run_dir = RUNS / f"run-t1-core-orbit-{canonical_hash(input_payload())[:16]}"
        result = verify_run_and_mutations(run_dir)
        saved = json.loads(AUDIT.read_text(encoding="utf-8"))
        recorded_at = saved.pop("recorded_at", None)
        if not recorded_at or datetime.fromisoformat(recorded_at).tzinfo is None or saved != result:
            raise ReplayMismatch("T1 core orbit Run audit differs from current replay")
    print(json.dumps({"status": result["status"], "run_id": result["run_id"],
                      "replay": result["replay"],
                      "mutation_controls": [result["result_tamper_rejected"], result["snapshot_tamper_rejected"]]},
                     indent=2))


if __name__ == "__main__":
    main()
