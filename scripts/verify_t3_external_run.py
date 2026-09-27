"""Build and replay a bounded T3 SciPy Tool/Provider Run in its optional environment."""

from __future__ import annotations

import argparse
import importlib.metadata
import json
import shutil
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
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
from auditable_scientist.runtime.replay import BoundPaths, ReplayManifest, ReplayMismatch, fingerprint_file
from auditable_scientist.runtime.run_integrity import verify_run_record

from verify_t3_external_scipy import (
    ATOL, GATES, INITIAL_STATES, LOCK, NUMPY_LICENSE_SHA256, NUMPY_SOURCE_COMMIT,
    NUMPY_SOURCE_TAG, OMEGAS, PHASE, ROOT, RTOL, SCIPY_LICENSE_SHA256,
    SCIPY_SOURCE_COMMIT, SCIPY_SOURCE_TAG, STEPS, WHEEL_SHA256,
    build_receipt, sha256, verify_environment,
)


PROVIDER_ID = "scipy-dop853-v1"
TOOL_ID = "t3-scipy-dop853-crosscheck-v1"
SCHEMA = ROOT / "schemas/t3-external-tool-call-v1.json"
METHOD = ROOT / "docs/T3_EXTERNAL_SOLVER.md"
MEMORY_SOURCE = ROOT / "docs/EVIDENCE_POLICY.md"
AUDIT = ROOT / "artifacts/t3-external-run-audit.json"
RUNS = ROOT / "artifacts/t3-external-runs"
SOURCE_PATHS = [
    Path(__file__).resolve(), ROOT / "scripts/verify_t3_external_scipy.py",
    ROOT / "src/auditable_scientist/tracks/dynamics.py",
    ROOT / "src/auditable_scientist/tracks/reference_rk4.py",
    ROOT / "src/auditable_scientist/domain/models.py",
    ROOT / "src/auditable_scientist/policy/runtime.py",
    ROOT / "src/auditable_scientist/runtime/canonical.py",
    ROOT / "src/auditable_scientist/runtime/environment.py",
    ROOT / "src/auditable_scientist/runtime/event_log.py",
    ROOT / "src/auditable_scientist/runtime/replay.py",
    ROOT / "src/auditable_scientist/runtime/run_integrity.py",
    ROOT / "src/auditable_scientist/runtime/paths.py",
    LOCK, METHOD, MEMORY_SOURCE, SCHEMA,
]


def installed_license_paths() -> dict[str, Path]:
    return {
        "scipy": Path(importlib.metadata.distribution("scipy").locate_file("scipy-1.18.1.dist-info/LICENSE.txt")),
        "numpy": Path(importlib.metadata.distribution("numpy").locate_file("numpy-2.2.6.dist-info/LICENSE.txt")),
    }


def input_payload() -> dict[str, Any]:
    environment = verify_environment()
    sources = [(path.relative_to(ROOT).as_posix(), sha256(path)) for path in SOURCE_PATHS]
    return {
        "schema_version": "t3-scipy-run-input-v1",
        "track_id": "T3",
        "provider_id": PROVIDER_ID,
        "solver": {"api": "scipy.integrate.solve_ivp", "method": "DOP853", "rtol": RTOL, "atol": ATOL},
        "grid": {"omegas": list(OMEGAS), "initial_states": [list(state) for state in INITIAL_STATES], "steps": STEPS, "end_phase": PHASE},
        "gates": GATES,
        "provider_provenance": environment,
        "source_snapshot_hash": canonical_hash(sources),
    }


def _policy() -> Policy:
    return Policy(
        policy_id="offline-t3-scipy-v1", network="disabled", max_seconds=120,
        max_tool_calls=1,
        allowed_paths=[str(path.resolve()) for path in (LOCK, METHOD, *installed_license_paths().values())],
        allowed_providers=[PROVIDER_ID],
    )


def _tool() -> Tool:
    return Tool(
        tool_id=TOOL_ID, name="SciPy DOP853 oscillator cross-check", version="1",
        parameter_schema_ref=SCHEMA.relative_to(ROOT).as_posix(),
        deterministic=True, network_required=False,
    )


def execute(payload: dict[str, Any]) -> tuple[dict[str, Any], int]:
    policy = _policy()
    registry = ToolRegistry(policy)
    tool = _tool()
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    expected_hash = canonical_hash(payload)

    def handler(arguments: dict[str, Any]) -> dict[str, Any]:
        if arguments != {"provider_id": PROVIDER_ID, "input_hash": expected_hash, "lock_path": str(LOCK.resolve())}:
            raise ReplayMismatch("external solver call differs from declared input")
        if input_payload() != payload:
            raise ReplayMismatch("external solver input or provider provenance changed")
        receipt = build_receipt()
        if receipt["grid"] != payload["grid"] or receipt["gates"] != payload["gates"] or receipt["solver"] != payload["solver"]:
            raise ReplayMismatch("external solver used a different declared grid, gate, or method")
        if receipt["environment"] != payload["provider_provenance"]:
            raise ReplayMismatch("external solver environment changed during execution")
        return receipt

    registry.register(tool, handler, argument_schema=schema)
    receipt = registry.invoke(
        TOOL_ID,
        {"provider_id": PROVIDER_ID, "input_hash": expected_hash, "lock_path": str(LOCK.resolve())},
        path_refs=[str(path) for path in (LOCK, METHOD, *installed_license_paths().values())],
        provider_id=PROVIDER_ID,
    )
    if registry.calls_used != 1 or receipt["status"] != "passed-optional-oscillator-cross-check" or not all(receipt["checks"].values()):
        raise ReplayMismatch("optional external solver failed a declared gate")
    return receipt, registry.calls_used


def verify_policy_denials(payload: dict[str, Any]) -> dict[str, bool]:
    registry = ToolRegistry(_policy())
    registry.register(_tool(), lambda _arguments: None, argument_schema=json.loads(SCHEMA.read_text(encoding="utf-8")))
    arguments = {"provider_id": PROVIDER_ID, "input_hash": canonical_hash(payload), "lock_path": str(LOCK.resolve())}
    try:
        registry.invoke(TOOL_ID, arguments, provider_id="unregistered-solver")
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
        raise ReplayMismatch("optional solver policy did not fail closed")
    return {"wrong_provider_rejected": wrong_provider_rejected, "out_of_scope_path_rejected": out_of_scope_path_rejected}


def _snapshot_licenses(run_dir: Path, *, create: bool) -> list[Path]:
    snapshots: list[Path] = []
    expected = {"scipy": SCIPY_LICENSE_SHA256, "numpy": NUMPY_LICENSE_SHA256}
    for name, installed in installed_license_paths().items():
        snapshot = run_dir / f"{name}-license.txt"
        if sha256(installed) != expected[name]:
            raise ReplayMismatch(f"installed {name} license notice changed")
        if create:
            shutil.copyfile(installed, snapshot)
        if not snapshot.is_file() or sha256(snapshot) != expected[name]:
            raise ReplayMismatch(f"snapshotted {name} license notice changed")
        snapshots.append(snapshot)
    return snapshots


def _make_run(payload: dict[str, Any], receipt: dict[str, Any], calls_used: int, *, run_dir: Path, snapshots: list[Path]) -> Run:
    bindings = BoundPaths(root=ROOT, run_dir=run_dir)
    input_hash = canonical_hash(payload)
    run_id = f"run-t3-scipy-{input_hash[:16]}"
    evidence_specs = [
        ("ev-t3-scipy-tool-code", EvidenceKind.CODE, Path(__file__).resolve(), installation_revision(), ["offline-tool", "source-provenance"]),
        ("ev-t3-scipy-lock", EvidenceKind.SNAPSHOT, LOCK, installation_revision(), ["pinned-wheel-manifest", "source-provenance"]),
        ("ev-t3-scipy-method", EvidenceKind.EXTERNAL_REFERENCE, METHOD, installation_revision(), ["method-and-rights-review"]),
        ("ev-t3-scipy-license", EvidenceKind.SNAPSHOT, snapshots[0], SCIPY_SOURCE_COMMIT, ["license-notice", "rights-review"]),
        ("ev-t3-numpy-license", EvidenceKind.SNAPSHOT, snapshots[1], NUMPY_SOURCE_COMMIT, ["license-notice", "rights-review"]),
    ]
    evidence = [
        Evidence(
            evidence_id=evidence_id, kind=kind, path_or_uri=bindings.ref(path),
            sha256=fingerprint_file(path).sha256, source_revision=revision,
            provenance_status=ProvenanceStatus.UNVERIFIED, allowed_use=allowed_use,
            notes="Byte and version binding is checked; scientific validity and redistribution approval remain separate.",
        )
        for evidence_id, kind, path, revision, allowed_use in evidence_specs
    ]
    policy = _policy().model_copy(update={
        "allowed_paths": [bindings.ref(path) for path in (LOCK, METHOD, *snapshots)],
    })
    status = RunStatus.COMPLETED
    base_time = datetime(2026, 9, 27, tzinfo=timezone.utc)
    events: list[Event] = []
    previous = "genesis"
    for seq, (event_type, body) in enumerate([
        ("run.initialized", {"run_id": run_id, "input_hash": input_hash}),
        ("policy.applied", {"policy_id": policy.policy_id, "network": policy.network, "provider_id": PROVIDER_ID}),
        ("tool.invoked", {"tool_id": TOOL_ID, "calls_used": calls_used}),
        ("evaluator.completed", {"evaluator_id": "t3-scipy-crosscheck-v1", "summary": receipt["summary"], "checks": receipt["checks"]}),
        ("negative_case.checked", {"wrong_sign_position_error": receipt["summary"]["wrong_sign_position_error"], "rejected": receipt["checks"]["wrong_sign_rejected"]}),
        ("run.completed", {"status": status.value}),
    ]):
        payload_hash = canonical_hash(body)
        events.append(Event(
            event_id=f"t3-scipy-event-{seq}", seq=seq, event_type=event_type,
            occurred_at=base_time + timedelta(seconds=seq),
            payload_hash=payload_hash, prev_event_hash=previous, payload=body,
        ))
        previous = payload_hash
    trace = Trace(
        trace_id=f"trace-{run_id}", run_id=run_id, input_hash=input_hash,
        entries=[{"seq": event.seq, "event_type": event.event_type, "payload_hash": event.payload_hash} for event in events],
    )
    return Run(
        run_id=run_id, task_id="t3-optional-external-oscillator-v1", created_at=base_time,
        input_hash=input_hash, code_revision=installation_revision(),
        environment={
            **capture_environment(["auditable-scientist-lab", "pydantic", "sympy", "jsonschema", "numpy", "scipy"]),
            "mode": "offline", "track_id": "T3", "runtime": "optional-external-solver",
            "network": "disabled", "provider_id": PROVIDER_ID,
            "pinned_wheel_sha256": WHEEL_SHA256,
            "installed_license_sha256": {"scipy": SCIPY_LICENSE_SHA256, "numpy": NUMPY_LICENSE_SHA256},
        },
        seed=17, evidence_refs=[item.evidence_id for item in evidence], status=status,
        agent=Agent(agent_id="offline-t3-scipy-agent-v1", name="Offline T3 external solver agent", version="1", capabilities=["invoke-registered-solver", "record-negative-control"]),
        tools=[_tool()],
        memories=[Memory(memory_id="evidence-policy-memory-v1", source_ref=bindings.ref(MEMORY_SOURCE), scope="claim-level evidence boundaries", version="local-snapshot", content_hash=sha256(MEMORY_SOURCE))],
        evaluators=[Evaluator(evaluator_id="t3-scipy-crosscheck-v1", name="T3 optional oscillator cross-check", version="1", read_only=True)],
        providers=[Provider(provider_id=PROVIDER_ID, kind="external-numerical-solver", name="SciPy DOP853", version="1.18.1", source_ref=f"https://github.com/scipy/scipy/tree/{SCIPY_SOURCE_TAG}")],
        policy=policy, events=events, traces=[trace],
        claims=[Claim(
            text="The pinned SciPy solver passed this nine-case oscillator cross-check only.",
            status=ClaimStatus.UNVERIFIED, level=EvidenceLevel.VALIDATED_REPRODUCTION,
            evidence_refs=[item.evidence_id for item in evidence],
            falsification_checks=["analytic-position-and-velocity", "local-solver-agreement", "wrong-sign-negative-control", "license-and-wheel-provenance"],
            holdout_verified=False,
        )],
        observations=[Observation(
            observation_id="obs-t3-scipy-grid", dataset_hash=input_hash, split="external",
            summary={"case_count": receipt["summary"]["case_count"], "scope": receipt["scope"], "checks": receipt["checks"]},
            units={"position": "normalized", "velocity": "normalized", "time": "oscillator units"},
            source_ref=bindings.ref(Path(__file__).resolve()),
        )],
        evidence=evidence,
    )


def _report(run: Run, receipt: dict[str, Any]) -> str:
    return (
        "# T3 optional SciPy Run\n\n"
        f"- Run: `{run.run_id}`\n"
        f"- Provider: `{PROVIDER_ID}` (SciPy 1.18.1, NumPy 2.2.6)\n"
        f"- Status: `{run.status.value}`; Claim: `{run.claims[0].status.value}`\n"
        f"- Grid: `{receipt['summary']['case_count']}` unit-mass oscillator cases\n"
        f"- Negative control rejected: `{receipt['checks']['wrong_sign_rejected']}`\n"
        f"- Result hash: `{canonical_hash(receipt)}`\n\n"
        "This is an optional pinned local solver cross-check. It does not establish multi-body, real-mission, or publication validity.\n"
    )


def _write_json(path: Path, value: Any) -> None:
    path.write_text(canonical_json(value) + "\n", encoding="utf-8", newline="\n")


def write_run() -> Path:
    payload = input_payload()
    run_dir = RUNS / f"run-t3-scipy-{canonical_hash(payload)[:16]}"
    if run_dir.exists():
        raise FileExistsError(f"refusing to overwrite an existing external Run: {run_dir}")
    run_dir.mkdir(parents=True)
    snapshots = _snapshot_licenses(run_dir, create=True)
    receipt, calls_used = execute(payload)
    run = _make_run(payload, receipt, calls_used, run_dir=run_dir, snapshots=snapshots)
    bindings = BoundPaths(root=ROOT, run_dir=run_dir)
    _write_json(run_dir / "input.json", payload)
    _write_json(run_dir / "result.json", {"provider_id": PROVIDER_ID, "receipt": receipt})
    _write_json(run_dir / "run.json", run.model_dump(mode="json"))
    (run_dir / "events.jsonl").write_text(
        "".join(canonical_json(event) + "\n" for event in run.events), encoding="utf-8", newline="\n",
    )
    ReplayManifest.create(
        input_payload=payload, code_revision=run.code_revision, environment=run.environment,
        seed=run.seed, source_paths=SOURCE_PATHS, evidence_paths=snapshots,
        computational_output=receipt, bindings=bindings,
    ).write(run_dir / "replay-manifest.json")
    (run_dir / "report.md").write_text(_report(run, receipt), encoding="utf-8", newline="\n")
    return run_dir


def replay_run(run_dir: Path) -> dict[str, Any]:
    run_dir = run_dir.resolve()
    bindings = BoundPaths(root=ROOT, run_dir=run_dir)
    manifest = ReplayManifest.load(run_dir / "replay-manifest.json")
    if manifest.schema_version != "replay-manifest-v2":
        raise ReplayMismatch("optional SciPy Run requires a portable manifest")
    payload = input_payload()
    saved_input = json.loads((run_dir / "input.json").read_text(encoding="utf-8"))
    if saved_input != payload or run_dir.name != f"run-t3-scipy-{canonical_hash(payload)[:16]}":
        raise ReplayMismatch("saved SciPy Run input or identity changed")
    snapshots = _snapshot_licenses(run_dir, create=False)
    receipt, calls_used = execute(payload)
    saved_result = json.loads((run_dir / "result.json").read_text(encoding="utf-8"))
    if saved_result != {"provider_id": PROVIDER_ID, "receipt": receipt}:
        raise ReplayMismatch("saved SciPy solver output changed")
    run = verify_run_record(run_dir / "run.json", run_dir / "events.jsonl", root=ROOT, bindings=bindings)
    expected_run = _make_run(payload, receipt, calls_used, run_dir=run_dir, snapshots=snapshots)
    if canonical_hash(run) != canonical_hash(expected_run):
        raise ReplayMismatch("saved SciPy shared-kernel Run changed")
    result = manifest.verify(
        input_payload=payload, code_revision=expected_run.code_revision,
        environment=expected_run.environment, seed=expected_run.seed,
        source_paths=SOURCE_PATHS, evidence_paths=snapshots, candidate_order=[],
        computational_output=receipt, bindings=bindings,
    ).model_dump(mode="json")
    if (run_dir / "report.md").read_text(encoding="utf-8") != _report(run, receipt):
        raise ReplayMismatch("saved SciPy Run report changed")
    return result


def verify_run_and_mutations(run_dir: Path) -> dict[str, Any]:
    original = replay_run(run_dir)
    with tempfile.TemporaryDirectory(prefix="scientist-t3-scipy-replay-") as temporary:
        relocated = Path(temporary) / run_dir.name
        shutil.copytree(run_dir, relocated)
        if replay_run(relocated) != original:
            raise ReplayMismatch("relocated SciPy Run differs")
        result_path = relocated / "result.json"
        saved_result = result_path.read_bytes()
        altered = json.loads(saved_result)
        altered["receipt"]["summary"]["case_count"] = 8
        _write_json(result_path, altered)
        try:
            replay_run(relocated)
        except ReplayMismatch:
            result_tamper_rejected = True
        else:
            result_tamper_rejected = False
        result_path.write_bytes(saved_result)
        license_path = relocated / "scipy-license.txt"
        license_path.write_bytes(license_path.read_bytes() + b"\nchanged\n")
        try:
            replay_run(relocated)
        except ReplayMismatch:
            license_tamper_rejected = True
        else:
            license_tamper_rejected = False
    if not result_tamper_rejected or not license_tamper_rejected:
        raise ReplayMismatch("SciPy Run mutation controls failed")
    return {
        "schema_version": "t3-external-run-audit-v1",
        "status": "verified-within-pinned-oscillator-grid",
        "run_path": run_dir.relative_to(ROOT).as_posix(),
        "run_id": run_dir.name,
        "replay": original,
        "relocated_replay_equal": True,
        "result_tamper_rejected": result_tamper_rejected,
        "license_tamper_rejected": license_tamper_rejected,
        "provider_id": PROVIDER_ID,
        "provider_version": "scipy-1.18.1-numpy-2.2.6",
        "source_tag_and_commit": {"scipy": [SCIPY_SOURCE_TAG, SCIPY_SOURCE_COMMIT], "numpy": [NUMPY_SOURCE_TAG, NUMPY_SOURCE_COMMIT]},
        "pinned_wheel_sha256": WHEEL_SHA256,
        "license_sha256": {"scipy": SCIPY_LICENSE_SHA256, "numpy": NUMPY_LICENSE_SHA256},
        "policy_denials": verify_policy_denials(input_payload()),
        "boundaries": {"oscillator_fixture": True, "multi_body": False, "real_mission": False, "scientific_validity": False, "publication_ready": False},
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--write", action="store_true", help="write a new content-addressed optional Run and its audit")
    action.add_argument("--verify", action="store_true", help="replay the committed Run and compare its audit")
    args = parser.parse_args()
    if args.write:
        run_dir = write_run()
        result = verify_run_and_mutations(run_dir)
        result["recorded_at"] = datetime.now(timezone.utc).isoformat()
        AUDIT.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    else:
        run_dir = RUNS / f"run-t3-scipy-{canonical_hash(input_payload())[:16]}"
        result = verify_run_and_mutations(run_dir)
        saved = json.loads(AUDIT.read_text(encoding="utf-8"))
        recorded_at = saved.pop("recorded_at", None)
        if not recorded_at or datetime.fromisoformat(recorded_at).tzinfo is None or saved != result:
            raise ReplayMismatch("optional SciPy Run audit differs from current replay")
    print(json.dumps({"status": result["status"], "run_id": result["run_id"], "replay": result["replay"], "mutation_controls": [result["result_tamper_rejected"], result["license_tamper_rejected"]]}, indent=2))


if __name__ == "__main__":
    main()
