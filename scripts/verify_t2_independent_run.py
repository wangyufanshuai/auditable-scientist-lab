"""Build and replay a bounded T2 independent synthetic endpoint Tool/Provider Run."""

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
    Agent, Claim, ClaimStatus, Evidence, EvidenceKind, EvidenceLevel,
    Evaluator, Event, Memory, Observation, Policy, Provider, ProvenanceStatus,
    Run, RunStatus, Tool, Trace,
)
from auditable_scientist.policy import PolicyDenied, ToolRegistry
from auditable_scientist.runtime.canonical import canonical_hash, canonical_json
from auditable_scientist.runtime.environment import capture_environment
from auditable_scientist.runtime.paths import installation_revision
from auditable_scientist.runtime.replay import BoundPaths, ReplayManifest, ReplayMismatch
from auditable_scientist.runtime.run_integrity import verify_run_record

from verify_t2_independent_endpoint import (
    AUDIT as STATIC_AUDIT, BASE_INPUT, ROOT, VARIED_INPUT, build_audit, verify_saved,
)


PROVIDER_ID = "internal-t2-interval-estimator-v1"
TOOL_ID = "t2-independent-interval-endpoints-v1"
EVALUATOR_ID = "t2-synthetic-independent-endpoints-v1"
SCHEMA = ROOT / "docs/contracts/t2-independent-tool-call-v1.json"
METHOD = ROOT / "docs/T2_INDEPENDENT_ENDPOINT.md"
MEMORY_SOURCE = ROOT / "docs/EVIDENCE_POLICY.md"
AUDIT = ROOT / "artifacts/t2-independent-run-audit.json"
RUNS = ROOT / "artifacts/t2-independent-runs"
SOURCE_PATHS = [
    Path(__file__).resolve(),
    ROOT / "scripts/verify_t2_independent_endpoint.py",
    ROOT / "src/auditable_scientist/tracks/physical_world.py",
    ROOT / "src/auditable_scientist/domain/models.py",
    ROOT / "src/auditable_scientist/policy/runtime.py",
    ROOT / "src/auditable_scientist/runtime/canonical.py",
    ROOT / "src/auditable_scientist/runtime/environment.py",
    ROOT / "src/auditable_scientist/runtime/event_log.py",
    ROOT / "src/auditable_scientist/runtime/replay.py",
    ROOT / "src/auditable_scientist/runtime/run_integrity.py",
    ROOT / "src/auditable_scientist/runtime/paths.py",
    BASE_INPUT, VARIED_INPUT, STATIC_AUDIT, METHOD, MEMORY_SOURCE, SCHEMA,
]


def _digest(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _static_receipt() -> dict[str, Any]:
    current = build_audit()
    saved = json.loads(STATIC_AUDIT.read_text(encoding="utf-8"))
    verify_saved(saved, current)
    return current


def input_payload() -> dict[str, Any]:
    static = _static_receipt()
    return {
        "schema_version": "t2-independent-run-input-v1",
        "track_id": "T2",
        "subtrack": "synthetic-impact-interval-endpoints",
        "provider_id": PROVIDER_ID,
        "case_count": static["case_count"],
        "train_count": static["train_count"],
        "holdout_count": static["holdout_count"],
        "base_input_sha256": _digest(BASE_INPUT),
        "varied_input_sha256": _digest(VARIED_INPUT),
        "standalone_audit_sha256": _digest(STATIC_AUDIT),
        "source_snapshot_hash": canonical_hash([
            (path.relative_to(ROOT).as_posix(), _digest(path)) for path in SOURCE_PATHS
        ]),
        "gates": static["gates"],
        "boundaries": static["boundaries"],
    }


def _policy(base_snapshot: Path, varied_snapshot: Path) -> Policy:
    return Policy(
        policy_id="offline-t2-independent-endpoint-v1", network="disabled",
        max_seconds=60, max_tool_calls=1,
        allowed_paths=[str(path.resolve()) for path in (*SOURCE_PATHS, base_snapshot, varied_snapshot)],
        allowed_providers=[PROVIDER_ID],
    )


def _tool() -> Tool:
    return Tool(
        tool_id=TOOL_ID, name="Independent synthetic impact-interval endpoint estimator",
        version="1", parameter_schema_ref=SCHEMA.relative_to(ROOT).as_posix(),
        deterministic=True, network_required=False,
    )


def _arguments(payload: dict[str, Any], base_snapshot: Path, varied_snapshot: Path) -> dict[str, str]:
    return {
        "provider_id": PROVIDER_ID,
        "input_hash": canonical_hash(payload),
        "base_snapshot_path": str(base_snapshot.resolve()),
        "varied_snapshot_path": str(varied_snapshot.resolve()),
    }


def execute(payload: dict[str, Any], base_snapshot: Path, varied_snapshot: Path) -> tuple[dict[str, Any], int]:
    registry = ToolRegistry(_policy(base_snapshot, varied_snapshot))
    expected = _arguments(payload, base_snapshot, varied_snapshot)
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))

    def handler(arguments: dict[str, Any]) -> dict[str, Any]:
        if arguments != expected or input_payload() != payload:
            raise ReplayMismatch("T2 endpoint call differs from declared input or source")
        if base_snapshot.read_bytes() != BASE_INPUT.read_bytes() or varied_snapshot.read_bytes() != VARIED_INPUT.read_bytes():
            raise ReplayMismatch("T2 endpoint input snapshots differ")
        static = _static_receipt()
        return {
            "status": "verified-synthetic-endpoints-only",
            "case_count": static["case_count"],
            "train_count": static["train_count"],
            "holdout_count": static["holdout_count"],
            "metrics": static["metrics"],
            "gates": static["gates"],
            "rows_sha256": canonical_hash(static["rows"]),
            "boundaries": static["boundaries"],
            "standalone_audit_sha256": _digest(STATIC_AUDIT),
        }

    registry.register(_tool(), handler, argument_schema=schema)
    receipt = registry.invoke(
        TOOL_ID, expected,
        path_refs=[str(path) for path in (*SOURCE_PATHS, base_snapshot, varied_snapshot)],
        provider_id=PROVIDER_ID,
    )
    if (registry.calls_used != 1 or receipt["case_count"] != 124
            or receipt["holdout_count"] != 84 or not all(receipt["gates"].values())):
        raise ReplayMismatch("T2 endpoint Run lost cases, gates, or tool-call bound")
    return receipt, registry.calls_used


def verify_policy_denials(payload: dict[str, Any], base_snapshot: Path, varied_snapshot: Path) -> dict[str, bool]:
    registry = ToolRegistry(_policy(base_snapshot, varied_snapshot))
    registry.register(_tool(), lambda _arguments: None,
                      argument_schema=json.loads(SCHEMA.read_text(encoding="utf-8")))
    arguments = _arguments(payload, base_snapshot, varied_snapshot)
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
        raise ReplayMismatch("T2 endpoint Run policy did not fail closed")
    return {
        "wrong_provider_rejected": wrong_provider_rejected,
        "out_of_scope_path_rejected": out_of_scope_path_rejected,
    }


def _make_run(payload: dict[str, Any], receipt: dict[str, Any], calls_used: int, *, run_dir: Path) -> Run:
    base_snapshot = run_dir / "base-fixture.json"
    varied_snapshot = run_dir / "varied-fixture.json"
    bindings = BoundPaths(root=ROOT, run_dir=run_dir)
    input_hash = canonical_hash(payload)
    run_id = f"run-t2-endpoint-{input_hash[:16]}"
    evidence_specs = [
        ("ev-t2e-base", EvidenceKind.DATA, base_snapshot, ["synthetic-fixture"]),
        ("ev-t2e-varied", EvidenceKind.DATA, varied_snapshot, ["synthetic-holdout-fixture"]),
        ("ev-t2e-static-audit", EvidenceKind.SNAPSHOT, STATIC_AUDIT, ["independent-estimator-audit"]),
        ("ev-t2e-tool-code", EvidenceKind.CODE, Path(__file__).resolve(), ["offline-tool", "source-provenance"]),
        ("ev-t2e-estimator-code", EvidenceKind.CODE, ROOT / "scripts/verify_t2_independent_endpoint.py", ["independent-estimator"]),
        ("ev-t2e-method", EvidenceKind.SNAPSHOT, METHOD, ["method-and-boundaries"]),
    ]
    evidence = [
        Evidence(
            evidence_id=evidence_id, kind=kind, path_or_uri=bindings.ref(path),
            sha256=_digest(path), source_revision=installation_revision(),
            provenance_status=ProvenanceStatus.UNVERIFIED, allowed_use=allowed_use,
            notes="Synthetic simulator result only; real interventions, causal identification, source rights, and physical validity remain unverified.",
        ) for evidence_id, kind, path, allowed_use in evidence_specs
    ]
    policy = _policy(base_snapshot, varied_snapshot).model_copy(update={
        "allowed_paths": [bindings.ref(path) for path in (*SOURCE_PATHS, base_snapshot, varied_snapshot)],
    })
    base_time = datetime(2026, 9, 27, tzinfo=timezone.utc)
    events: list[Event] = []
    previous = "genesis"
    for seq, (event_type, body) in enumerate([
        ("run.initialized", {"run_id": run_id, "input_hash": input_hash}),
        ("policy.applied", {"policy_id": policy.policy_id, "network": policy.network, "provider_id": PROVIDER_ID}),
        ("tool.invoked", {"tool_id": TOOL_ID, "calls_used": calls_used}),
        ("evaluator.completed", {"evaluator_id": EVALUATOR_ID, "metrics": receipt["metrics"], "gates": receipt["gates"]}),
        ("negative_case.checked", {"ignored_intervention_rejected": receipt["gates"]["ignored_intervention_rejected"]}),
        ("run.completed", {"status": RunStatus.COMPLETED.value}),
    ]):
        payload_hash = canonical_hash(body)
        events.append(Event(
            event_id=f"t2-endpoint-event-{seq}", seq=seq, event_type=event_type,
            occurred_at=base_time + timedelta(seconds=seq),
            payload_hash=payload_hash, prev_event_hash=previous, payload=body,
        ))
        previous = payload_hash
    trace = Trace(
        trace_id=f"trace-{run_id}", run_id=run_id, input_hash=input_hash,
        entries=[{"seq": item.seq, "event_type": item.event_type, "payload_hash": item.payload_hash} for item in events],
    )
    return Run(
        run_id=run_id, task_id="t2-optional-independent-synthetic-endpoints-v1",
        created_at=base_time, input_hash=input_hash, code_revision=installation_revision(),
        environment={
            **capture_environment(["auditable-scientist-lab", "pydantic", "sympy", "jsonschema"]),
            "mode": "offline", "track_id": "T2", "runtime": "optional-independent-endpoint",
            "network": "disabled", "provider_id": PROVIDER_ID,
        },
        seed=17, evidence_refs=[item.evidence_id for item in evidence], status=RunStatus.COMPLETED,
        agent=Agent(agent_id="offline-t2-endpoint-agent-v1", name="Offline T2 endpoint agent", version="1", capabilities=["invoke-registered-estimator", "record-negative-control"]),
        tools=[_tool()],
        memories=[Memory(memory_id="evidence-policy-memory-v1", source_ref=bindings.ref(MEMORY_SOURCE), scope="claim-level evidence boundaries", version="local-snapshot", content_hash=_digest(MEMORY_SOURCE))],
        evaluators=[Evaluator(evaluator_id=EVALUATOR_ID, name="T2 independent synthetic endpoint evaluator", version="1", read_only=True)],
        providers=[Provider(provider_id=PROVIDER_ID, kind="deterministic-domain-evaluator", name="Local impact-interval estimator", version="1", source_ref="scripts/verify_t2_independent_endpoint.py")],
        policy=policy, events=events, traces=[trace],
        claims=[Claim(
            text="The intervention effects measured by this synthetic simulator generalize to real physical systems.",
            status=ClaimStatus.UNVERIFIED, level=EvidenceLevel.DEMO,
            evidence_refs=[item.evidence_id for item in evidence],
            falsification_checks=["paired-branch-endpoint-replay", "independent-interval-estimator", "ignored-intervention-negative", "source-and-snapshot-binding"],
            holdout_verified=False,
        )],
        observations=[Observation(
            observation_id="obs-t2-synthetic-endpoints", dataset_hash=input_hash, split="external",
            summary={"case_count": receipt["case_count"], "holdout_count": receipt["holdout_count"], "metrics": receipt["metrics"]},
            units={"horizontal_position": "m", "effect": "m"}, source_ref=bindings.ref(base_snapshot),
        )],
        evidence=evidence,
    )


def _write_json(path: Path, payload: Any) -> None:
    path.write_text(canonical_json(payload) + "\n", encoding="utf-8", newline="\n")


def _report(run: Run, receipt: dict[str, Any]) -> str:
    return (
        "# T2 optional independent synthetic endpoint Run\n\n"
        f"- Run: `{run.run_id}`\n"
        f"- Provider: `{PROVIDER_ID}`\n"
        f"- Status: `{run.status.value}`; real-world Claim: `{run.claims[0].status.value}`\n"
        f"- Cases: `{receipt['case_count']}`; holdout: `{receipt['holdout_count']}`\n"
        f"- Holdout effect RMSE (m): `{receipt['metrics']['holdout_effect_rmse_m']}`\n"
        f"- Ignored-intervention RMSE (m): `{receipt['metrics']['ignored_intervention_holdout_rmse_m']}`\n"
        f"- Result hash: `{canonical_hash(receipt)}`\n\n"
        "Only the declared synthetic simulator endpoints are cross-checked. Real interventions, causal identification, source rights, and publication remain unverified.\n"
    )


def write_run() -> Path:
    payload = input_payload()
    run_dir = RUNS / f"run-t2-endpoint-{canonical_hash(payload)[:16]}"
    if run_dir.exists():
        raise FileExistsError(f"refusing to overwrite existing T2 endpoint Run: {run_dir}")
    run_dir.mkdir(parents=True)
    base_snapshot = run_dir / "base-fixture.json"
    varied_snapshot = run_dir / "varied-fixture.json"
    shutil.copyfile(BASE_INPUT, base_snapshot)
    shutil.copyfile(VARIED_INPUT, varied_snapshot)
    receipt, calls_used = execute(payload, base_snapshot, varied_snapshot)
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
        seed=run.seed, source_paths=SOURCE_PATHS, evidence_paths=[base_snapshot, varied_snapshot],
        computational_output=receipt, bindings=bindings,
    ).write(run_dir / "replay-manifest.json")
    (run_dir / "report.md").write_text(_report(run, receipt), encoding="utf-8", newline="\n")
    return run_dir


def replay_run(run_dir: Path) -> dict[str, Any]:
    run_dir = run_dir.resolve()
    bindings = BoundPaths(root=ROOT, run_dir=run_dir)
    manifest = ReplayManifest.load(run_dir / "replay-manifest.json")
    if manifest.schema_version != "replay-manifest-v2":
        raise ReplayMismatch("T2 endpoint Run requires a portable manifest")
    payload = input_payload()
    if (json.loads((run_dir / "input.json").read_text(encoding="utf-8")) != payload
            or run_dir.name != f"run-t2-endpoint-{canonical_hash(payload)[:16]}"):
        raise ReplayMismatch("saved T2 endpoint Run input or identity changed")
    base_snapshot = run_dir / "base-fixture.json"
    varied_snapshot = run_dir / "varied-fixture.json"
    receipt, calls_used = execute(payload, base_snapshot, varied_snapshot)
    if json.loads((run_dir / "result.json").read_text(encoding="utf-8")) != {"provider_id": PROVIDER_ID, "receipt": receipt}:
        raise ReplayMismatch("saved T2 endpoint output changed")
    run = verify_run_record(run_dir / "run.json", run_dir / "events.jsonl", root=ROOT, bindings=bindings)
    expected = _make_run(payload, receipt, calls_used, run_dir=run_dir)
    if canonical_hash(run) != canonical_hash(expected):
        raise ReplayMismatch("saved T2 shared-kernel Run changed")
    replay = manifest.verify(
        input_payload=payload, code_revision=expected.code_revision, environment=expected.environment,
        seed=expected.seed, source_paths=SOURCE_PATHS,
        evidence_paths=[base_snapshot, varied_snapshot], candidate_order=[],
        computational_output=receipt, bindings=bindings,
    ).model_dump(mode="json")
    if (run_dir / "report.md").read_text(encoding="utf-8") != _report(run, receipt):
        raise ReplayMismatch("saved T2 endpoint report changed")
    return replay


def verify_run_and_mutations(run_dir: Path) -> dict[str, Any]:
    original = replay_run(run_dir)
    with tempfile.TemporaryDirectory(prefix="scientist-t2-endpoint-replay-") as temporary:
        relocated = Path(temporary).resolve() / run_dir.name
        if not relocated.is_relative_to(Path(tempfile.gettempdir()).resolve()):
            raise ReplayMismatch("temporary T2 relocation escaped system temp")
        shutil.copytree(run_dir, relocated)
        if replay_run(relocated) != original:
            raise ReplayMismatch("relocated T2 endpoint Run differs")
        result_path = relocated / "result.json"
        original_result = result_path.read_bytes()
        changed = json.loads(original_result)
        changed["receipt"]["metrics"]["holdout_effect_rmse_m"] = 0.5
        _write_json(result_path, changed)
        try:
            replay_run(relocated)
        except ReplayMismatch:
            result_tamper_rejected = True
        else:
            result_tamper_rejected = False
        result_path.write_bytes(original_result)
        varied_snapshot = relocated / "varied-fixture.json"
        varied_snapshot.write_bytes(varied_snapshot.read_bytes() + b"\nchanged\n")
        try:
            replay_run(relocated)
        except ReplayMismatch:
            snapshot_tamper_rejected = True
        else:
            snapshot_tamper_rejected = False
    if not result_tamper_rejected or not snapshot_tamper_rejected:
        raise ReplayMismatch("T2 endpoint Run mutation controls failed")
    return {
        "schema_version": "t2-independent-run-audit-v1",
        "status": "verified-synthetic-endpoint-run-only",
        "run_path": run_dir.relative_to(ROOT).as_posix(),
        "run_id": run_dir.name,
        "replay": original,
        "relocated_replay_equal": True,
        "result_tamper_rejected": result_tamper_rejected,
        "snapshot_tamper_rejected": snapshot_tamper_rejected,
        "policy_denials": verify_policy_denials(input_payload(), run_dir / "base-fixture.json", run_dir / "varied-fixture.json"),
        "boundaries": {
            "synthetic_simulator_endpoints": True,
            "independent_event_interval_implementation": True,
            "real_intervention_data": False,
            "observational_causal_identification": False,
            "physical_model_validated": False,
            "source_rights_reviewed": False,
            "research_candidate": False,
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
        run_dir = RUNS / f"run-t2-endpoint-{canonical_hash(input_payload())[:16]}"
        result = verify_run_and_mutations(run_dir)
        saved = json.loads(AUDIT.read_text(encoding="utf-8"))
        recorded_at = saved.pop("recorded_at", None)
        if not recorded_at or datetime.fromisoformat(recorded_at).tzinfo is None or saved != result:
            raise ReplayMismatch("T2 endpoint Run audit differs from current replay")
    print(json.dumps({
        "status": result["status"], "run_id": result["run_id"],
        "replay": result["replay"],
        "mutation_controls": [result["result_tamper_rejected"], result["snapshot_tamper_rejected"]],
    }, sort_keys=True))


if __name__ == "__main__":
    main()
