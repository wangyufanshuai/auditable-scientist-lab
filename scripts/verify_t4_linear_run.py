"""Build and replay an optional T4 exact linear-invariant Tool/Provider Run."""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
from pathlib import Path
import shutil
import tempfile
from typing import Any

import sympy

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

from check_t4_linear_certificate import AUDIT as STATIC_AUDIT, INPUT, ROOT, check_audit
from verify_t4_linear_formal import build_audit


PROVIDER_ID = "internal-sympy-t4-linear-v1"
TOOL_ID = "t4-exact-linear-invariant-v1"
EVALUATOR_ID = "t4-exact-linear-invariant-class-v1"
SCHEMA = ROOT / "schemas/t4-linear-tool-call-v1.json"
METHOD = ROOT / "docs/T4_LINEAR_INVARIANTS.md"
MEMORY_SOURCE = ROOT / "docs/EVIDENCE_POLICY.md"
AUDIT = ROOT / "artifacts/t4-linear-run-audit.json"
RUNS = ROOT / "artifacts/t4-linear-runs"
SOURCE_PATHS = [
    Path(__file__).resolve(),
    ROOT / "scripts/verify_t4_linear_formal.py",
    ROOT / "scripts/check_t4_linear_certificate.py",
    ROOT / "src/auditable_scientist/tracks/proof.py",
    ROOT / "src/auditable_scientist/domain/models.py",
    ROOT / "src/auditable_scientist/policy/runtime.py",
    ROOT / "src/auditable_scientist/runtime/canonical.py",
    ROOT / "src/auditable_scientist/runtime/environment.py",
    ROOT / "src/auditable_scientist/runtime/event_log.py",
    ROOT / "src/auditable_scientist/runtime/replay.py",
    ROOT / "src/auditable_scientist/runtime/run_integrity.py",
    ROOT / "src/auditable_scientist/runtime/paths.py",
    INPUT, STATIC_AUDIT, METHOD, MEMORY_SOURCE, SCHEMA,
]


def _digest(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _static_receipt() -> dict[str, Any]:
    saved = json.loads(STATIC_AUDIT.read_text(encoding="utf-8"))
    check_audit(saved)
    current = build_audit()
    timestamp = saved.pop("recorded_at", None)
    if not timestamp or datetime.fromisoformat(timestamp).tzinfo is None or saved != current:
        raise ReplayMismatch("T4 standalone exact certificate differs from current algebra")
    return current


def input_payload() -> dict[str, Any]:
    static = _static_receipt()
    return {
        "schema_version": "t4-linear-run-input-v1",
        "track_id": "T4",
        "subtrack": "exact-rational-linear-invariant",
        "provider_id": PROVIDER_ID,
        "provider_version": sympy.__version__,
        "systems": json.loads(INPUT.read_text(encoding="utf-8")),
        "standalone_audit_sha256": _digest(STATIC_AUDIT),
        "standalone_input_sha256": static["input_sha256"],
        "source_snapshot_hash": canonical_hash([
            (path.relative_to(ROOT).as_posix(), _digest(path)) for path in SOURCE_PATHS
        ]),
        "boundaries": static["boundaries"],
    }


def _policy(snapshot: Path) -> Policy:
    return Policy(
        policy_id="offline-t4-exact-linear-v1", network="disabled", max_seconds=60,
        max_tool_calls=1,
        allowed_paths=[str(path.resolve()) for path in (*SOURCE_PATHS, snapshot)],
        allowed_providers=[PROVIDER_ID],
    )


def _tool() -> Tool:
    return Tool(
        tool_id=TOOL_ID, name="Exact rational linear-invariant proof", version="1",
        parameter_schema_ref=SCHEMA.relative_to(ROOT).as_posix(),
        deterministic=True, network_required=False,
    )


def execute(payload: dict[str, Any], snapshot: Path) -> tuple[dict[str, Any], int]:
    registry = ToolRegistry(_policy(snapshot))
    expected = {
        "provider_id": PROVIDER_ID,
        "input_hash": canonical_hash(payload),
        "fixture_path": str(snapshot.resolve()),
    }
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))

    def handler(arguments: dict[str, Any]) -> dict[str, Any]:
        if arguments != expected or input_payload() != payload:
            raise ReplayMismatch("T4 exact solver call differs from declared input or source")
        if snapshot.read_bytes() != INPUT.read_bytes():
            raise ReplayMismatch("T4 exact solver input snapshot differs")
        static = _static_receipt()
        summary = check_audit({**static, "recorded_at": json.loads(STATIC_AUDIT.read_text(encoding="utf-8"))["recorded_at"]})
        return {
            "status": "verified-exact-linear-class-only",
            "summary": summary,
            "certificates": static["certificates"],
            "boundaries": static["boundaries"],
            "standalone_audit_sha256": _digest(STATIC_AUDIT),
        }

    registry.register(_tool(), handler, argument_schema=schema)
    receipt = registry.invoke(
        TOOL_ID, expected,
        path_refs=[str(path) for path in (*SOURCE_PATHS, snapshot)],
        provider_id=PROVIDER_ID,
    )
    if registry.calls_used != 1 or receipt["summary"] != {
        "verified": True, "systems": 3, "positive_proofs": 2, "negative_controls": 1,
    }:
        raise ReplayMismatch("T4 exact proof used wrong tool count or lost a declared case")
    return receipt, registry.calls_used


def verify_policy_denials(payload: dict[str, Any], snapshot: Path) -> dict[str, bool]:
    registry = ToolRegistry(_policy(snapshot))
    registry.register(_tool(), lambda _arguments: None,
                      argument_schema=json.loads(SCHEMA.read_text(encoding="utf-8")))
    arguments = {
        "provider_id": PROVIDER_ID,
        "input_hash": canonical_hash(payload),
        "fixture_path": str(snapshot.resolve()),
    }
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
        raise ReplayMismatch("T4 exact proof policy did not fail closed")
    return {
        "wrong_provider_rejected": wrong_provider_rejected,
        "out_of_scope_path_rejected": out_of_scope_path_rejected,
    }


def _make_run(payload: dict[str, Any], receipt: dict[str, Any], calls_used: int, *, run_dir: Path) -> Run:
    snapshot = run_dir / "fixture.json"
    bindings = BoundPaths(root=ROOT, run_dir=run_dir)
    input_hash = canonical_hash(payload)
    run_id = f"run-t4-linear-{input_hash[:16]}"
    evidence_specs = [
        ("ev-t4l-input", EvidenceKind.DATA, snapshot, ["declared-matrix-fixture"]),
        ("ev-t4l-static-certificate", EvidenceKind.SNAPSHOT, STATIC_AUDIT, ["exact-certificate", "source-provenance"]),
        ("ev-t4l-tool-code", EvidenceKind.CODE, Path(__file__).resolve(), ["offline-tool", "source-provenance"]),
        ("ev-t4l-independent-checker", EvidenceKind.CODE, ROOT / "scripts/check_t4_linear_certificate.py", ["independent-checker"]),
        ("ev-t4l-method", EvidenceKind.SNAPSHOT, METHOD, ["method-and-boundaries"]),
    ]
    evidence = [
        Evidence(
            evidence_id=evidence_id, kind=kind, path_or_uri=bindings.ref(path),
            sha256=_digest(path), source_revision=installation_revision(),
            provenance_status=ProvenanceStatus.UNVERIFIED, allowed_use=allowed_use,
            notes="Exact algebra on declared matrices; physical model, data rights, and publication status remain unverified.",
        ) for evidence_id, kind, path, allowed_use in evidence_specs
    ]
    policy = _policy(snapshot).model_copy(update={
        "allowed_paths": [bindings.ref(path) for path in (*SOURCE_PATHS, snapshot)],
    })
    base_time = datetime(2026, 9, 27, tzinfo=timezone.utc)
    events: list[Event] = []
    previous = "genesis"
    for seq, (event_type, body) in enumerate([
        ("run.initialized", {"run_id": run_id, "input_hash": input_hash}),
        ("policy.applied", {"policy_id": policy.policy_id, "network": policy.network, "provider_id": PROVIDER_ID}),
        ("tool.invoked", {"tool_id": TOOL_ID, "calls_used": calls_used}),
        ("evaluator.completed", {"evaluator_id": EVALUATOR_ID, "summary": receipt["summary"]}),
        ("negative_case.checked", {"leaky_system_rejected": not receipt["certificates"][-1]["universal_conservation_proved"]}),
        ("run.completed", {"status": RunStatus.COMPLETED.value}),
    ]):
        payload_hash = canonical_hash(body)
        events.append(Event(
            event_id=f"t4-linear-event-{seq}", seq=seq, event_type=event_type,
            occurred_at=base_time + timedelta(seconds=seq),
            payload_hash=payload_hash, prev_event_hash=previous, payload=body,
        ))
        previous = payload_hash
    trace = Trace(
        trace_id=f"trace-{run_id}", run_id=run_id, input_hash=input_hash,
        entries=[{"seq": item.seq, "event_type": item.event_type, "payload_hash": item.payload_hash} for item in events],
    )
    return Run(
        run_id=run_id, task_id="t4-optional-exact-linear-invariant-v1", created_at=base_time,
        input_hash=input_hash, code_revision=installation_revision(),
        environment={
            **capture_environment(["auditable-scientist-lab", "pydantic", "sympy", "jsonschema"]),
            "mode": "offline", "track_id": "T4", "runtime": "optional-exact-linear-proof",
            "network": "disabled", "provider_id": PROVIDER_ID,
        },
        seed=17, evidence_refs=[item.evidence_id for item in evidence], status=RunStatus.COMPLETED,
        agent=Agent(agent_id="offline-t4-linear-agent-v1", name="Offline T4 exact proof agent", version="1", capabilities=["invoke-registered-proof", "record-negative-control"]),
        tools=[_tool()],
        memories=[Memory(memory_id="evidence-policy-memory-v1", source_ref=bindings.ref(MEMORY_SOURCE), scope="claim-level evidence boundaries", version="local-snapshot", content_hash=_digest(MEMORY_SOURCE))],
        evaluators=[Evaluator(evaluator_id=EVALUATOR_ID, name="T4 exact rational linear-invariant evaluator", version="1", read_only=True)],
        providers=[Provider(provider_id=PROVIDER_ID, kind="deterministic-domain-evaluator", name="Local SymPy exact matrix evaluator", version=sympy.__version__, source_ref="scripts/verify_t4_linear_formal.py")],
        policy=policy, events=events, traces=[trace],
        claims=[Claim(
            text="The declared linear transition represents a physically conserved quantity.",
            status=ClaimStatus.UNVERIFIED, level=EvidenceLevel.DEMO,
            evidence_refs=[item.evidence_id for item in evidence],
            falsification_checks=["exact-coefficient-identities", "independent-fraction-checker", "leaky-negative-control", "source-and-snapshot-binding"],
            holdout_verified=False,
        )],
        observations=[Observation(
            observation_id="obs-t4-linear-certificates", dataset_hash=input_hash, split="external",
            summary={"scope": "declared-rational-linear-systems", **receipt["summary"]},
            units={}, source_ref=bindings.ref(snapshot),
        )],
        evidence=evidence,
    )


def _write_json(path: Path, payload: Any) -> None:
    path.write_text(canonical_json(payload) + "\n", encoding="utf-8", newline="\n")


def _report(run: Run, receipt: dict[str, Any]) -> str:
    return (
        "# T4 optional exact linear-invariant Run\n\n"
        f"- Run: `{run.run_id}`\n"
        f"- Provider: `{PROVIDER_ID}` (SymPy {sympy.__version__})\n"
        f"- Status: `{run.status.value}`; scientific Claim: `{run.claims[0].status.value}`\n"
        f"- Exact positive certificates: `{receipt['summary']['positive_proofs']}`\n"
        f"- Leaky negative controls: `{receipt['summary']['negative_controls']}`\n"
        f"- Result hash: `{canonical_hash(receipt)}`\n\n"
        "Only the declared rational linear identities are proven. Physical interpretation, arbitrary dynamics, real data, and publication remain unverified.\n"
    )


def write_run() -> Path:
    payload = input_payload()
    run_dir = RUNS / f"run-t4-linear-{canonical_hash(payload)[:16]}"
    if run_dir.exists():
        raise FileExistsError(f"refusing to overwrite existing T4 linear Run: {run_dir}")
    run_dir.mkdir(parents=True)
    snapshot = run_dir / "fixture.json"
    shutil.copyfile(INPUT, snapshot)
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
        computational_output=receipt, bindings=bindings,
    ).write(run_dir / "replay-manifest.json")
    (run_dir / "report.md").write_text(_report(run, receipt), encoding="utf-8", newline="\n")
    return run_dir


def replay_run(run_dir: Path) -> dict[str, Any]:
    run_dir = run_dir.resolve()
    bindings = BoundPaths(root=ROOT, run_dir=run_dir)
    manifest = ReplayManifest.load(run_dir / "replay-manifest.json")
    if manifest.schema_version != "replay-manifest-v2":
        raise ReplayMismatch("T4 exact Run requires a portable manifest")
    payload = input_payload()
    if (json.loads((run_dir / "input.json").read_text(encoding="utf-8")) != payload
            or run_dir.name != f"run-t4-linear-{canonical_hash(payload)[:16]}"):
        raise ReplayMismatch("saved T4 exact Run input or identity changed")
    snapshot = run_dir / "fixture.json"
    receipt, calls_used = execute(payload, snapshot)
    if json.loads((run_dir / "result.json").read_text(encoding="utf-8")) != {"provider_id": PROVIDER_ID, "receipt": receipt}:
        raise ReplayMismatch("saved T4 exact proof result changed")
    run = verify_run_record(run_dir / "run.json", run_dir / "events.jsonl", root=ROOT, bindings=bindings)
    expected = _make_run(payload, receipt, calls_used, run_dir=run_dir)
    if canonical_hash(run) != canonical_hash(expected):
        raise ReplayMismatch("saved T4 exact shared-kernel Run changed")
    replay = manifest.verify(
        input_payload=payload, code_revision=expected.code_revision,
        environment=expected.environment, seed=expected.seed,
        source_paths=SOURCE_PATHS, evidence_paths=[snapshot], candidate_order=[],
        computational_output=receipt, bindings=bindings,
    ).model_dump(mode="json")
    if (run_dir / "report.md").read_text(encoding="utf-8") != _report(run, receipt):
        raise ReplayMismatch("saved T4 exact Run report changed")
    return replay


def verify_run_and_mutations(run_dir: Path) -> dict[str, Any]:
    original = replay_run(run_dir)
    with tempfile.TemporaryDirectory(prefix="scientist-t4-linear-replay-") as temporary:
        relocated = Path(temporary).resolve() / run_dir.name
        if not relocated.is_relative_to(Path(tempfile.gettempdir()).resolve()):
            raise ReplayMismatch("temporary T4 relocation escaped system temp")
        shutil.copytree(run_dir, relocated)
        if replay_run(relocated) != original:
            raise ReplayMismatch("relocated T4 exact Run differs")
        result_path = relocated / "result.json"
        original_result = result_path.read_bytes()
        changed = json.loads(original_result)
        changed["receipt"]["certificates"][0]["universal_conservation_proved"] = False
        _write_json(result_path, changed)
        try:
            replay_run(relocated)
        except ReplayMismatch:
            result_tamper_rejected = True
        else:
            result_tamper_rejected = False
        result_path.write_bytes(original_result)
        snapshot = relocated / "fixture.json"
        snapshot.write_bytes(snapshot.read_bytes() + b"\nchanged\n")
        try:
            replay_run(relocated)
        except ReplayMismatch:
            snapshot_tamper_rejected = True
        else:
            snapshot_tamper_rejected = False
    if not result_tamper_rejected or not snapshot_tamper_rejected:
        raise ReplayMismatch("T4 exact Run mutation controls failed")
    return {
        "schema_version": "t4-linear-run-audit-v1",
        "status": "verified-exact-linear-class-only",
        "run_path": run_dir.relative_to(ROOT).as_posix(),
        "run_id": run_dir.name,
        "replay": original,
        "relocated_replay_equal": True,
        "result_tamper_rejected": result_tamper_rejected,
        "snapshot_tamper_rejected": snapshot_tamper_rejected,
        "policy_denials": verify_policy_denials(input_payload(), run_dir / "fixture.json"),
        "boundaries": {
            "declared_exact_linear_class": True,
            "physical_model_validated": False,
            "general_formal_backend": False,
            "real_data": False,
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
        run_dir = RUNS / f"run-t4-linear-{canonical_hash(input_payload())[:16]}"
        result = verify_run_and_mutations(run_dir)
        saved = json.loads(AUDIT.read_text(encoding="utf-8"))
        recorded_at = saved.pop("recorded_at", None)
        if not recorded_at or datetime.fromisoformat(recorded_at).tzinfo is None or saved != result:
            raise ReplayMismatch("T4 exact Run audit differs from current replay")
    print(json.dumps({
        "status": result["status"], "run_id": result["run_id"],
        "replay": result["replay"],
        "mutation_controls": [result["result_tamper_rejected"], result["snapshot_tamper_rejected"]],
    }, sort_keys=True))


if __name__ == "__main__":
    main()
