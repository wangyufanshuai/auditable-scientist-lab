"""Create a portable, non-executable T5 real-source Tool/Provider Run."""

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

from verify_acceptance import verify_optional_t5_pbs_source
from verify_t5_pbs_source import ROOT, AUDIT as STATIC_AUDIT, CONTRACT


PROVIDER_ID = "internal-t5-pbs-source-audit-v1"
TOOL_ID = "t5-read-only-pbs-source-audit-v1"
EVALUATOR_ID = "t5-pbs-source-inventory-v1"
SCHEMA = ROOT / "docs/contracts/t5-pbs-source-tool-call-v1.json"
METHOD = ROOT / "docs/T5_PBS_SOURCE_RESULT.md"
MEMORY_SOURCE = ROOT / "docs/EVIDENCE_POLICY.md"
AUDIT = ROOT / "artifacts/t5-pbs-source-run-audit.json"
RUNS = ROOT / "artifacts/t5-pbs-source-runs"
SOURCE_PATHS = [
    Path(__file__).resolve(),
    ROOT / "scripts/verify_t5_pbs_source.py",
    ROOT / "scripts/verify_acceptance.py",
    ROOT / "src/auditable_scientist/domain/models.py",
    ROOT / "src/auditable_scientist/policy/runtime.py",
    ROOT / "src/auditable_scientist/runtime/canonical.py",
    ROOT / "src/auditable_scientist/runtime/environment.py",
    ROOT / "src/auditable_scientist/runtime/event_log.py",
    ROOT / "src/auditable_scientist/runtime/replay.py",
    ROOT / "src/auditable_scientist/runtime/run_integrity.py",
    ROOT / "src/auditable_scientist/runtime/paths.py",
    STATIC_AUDIT, CONTRACT, METHOD, MEMORY_SOURCE, SCHEMA,
    ROOT / "requirements-t5-pbs-pdf.txt",
]


def _digest(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _static_receipt() -> tuple[dict[str, Any], dict[str, Any]]:
    saved = json.loads(STATIC_AUDIT.read_text(encoding="utf-8"))
    summary = verify_optional_t5_pbs_source(saved, verify_dynamic=False)
    if (summary["status"] != "verified-source-document-and-review-flags-only"
            or summary["execution_allowed"] is not False
            or summary["human_acceptance"] is not False):
        raise ReplayMismatch("T5 source receipt widened its authority")
    return saved, summary


def input_payload() -> dict[str, Any]:
    saved, summary = _static_receipt()
    return {
        "schema_version": "t5-pbs-source-run-input-v1",
        "track_id": "T5",
        "subtrack": "real-document-citation-inventory-only",
        "provider_id": PROVIDER_ID,
        "standalone_audit_sha256": _digest(STATIC_AUDIT),
        "source_pdf_sha256": saved["source_pdf_sha256"],
        "source_doi": saved["source"]["doi"],
        "step_count": summary["step_count"],
        "source_snapshot_hash": canonical_hash([
            (path.relative_to(ROOT).as_posix(), _digest(path)) for path in SOURCE_PATHS
        ]),
        "boundaries": saved["boundaries"],
    }


def _policy(snapshot: Path) -> Policy:
    return Policy(
        policy_id="offline-t5-pbs-source-inventory-v1", network="disabled",
        max_seconds=60, max_tool_calls=1,
        allowed_paths=[str(path.resolve()) for path in (*SOURCE_PATHS, snapshot)],
        allowed_providers=[PROVIDER_ID],
    )


def _tool() -> Tool:
    return Tool(
        tool_id=TOOL_ID, name="Read-only protocol source and citation audit",
        version="1", parameter_schema_ref=SCHEMA.relative_to(ROOT).as_posix(),
        deterministic=True, network_required=False,
    )


def _arguments(payload: dict[str, Any], snapshot: Path) -> dict[str, str]:
    return {"provider_id": PROVIDER_ID, "input_hash": canonical_hash(payload),
            "snapshot_path": str(snapshot.resolve())}


def execute(payload: dict[str, Any], snapshot: Path) -> tuple[dict[str, Any], int]:
    registry = ToolRegistry(_policy(snapshot))
    expected = _arguments(payload, snapshot)
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))

    def handler(arguments: dict[str, Any]) -> dict[str, Any]:
        if arguments != expected or input_payload() != payload:
            raise ReplayMismatch("T5 source call differs from declared input or source")
        if snapshot.read_bytes() != STATIC_AUDIT.read_bytes():
            raise ReplayMismatch("T5 source audit snapshot differs")
        saved, summary = _static_receipt()
        return {
            "status": "source-inventory-only",
            "source_pdf_sha256": saved["source_pdf_sha256"],
            "doi": saved["source"]["doi"],
            "license_declaration": saved["source"]["license_declaration"],
            "page_count": summary["page_count"],
            "anchor_count": len(saved["anchors"]),
            "step_count": summary["step_count"],
            "review_flags": saved["review_flags"],
            "boundaries": saved["boundaries"],
            "standalone_audit_sha256": _digest(STATIC_AUDIT),
        }

    registry.register(_tool(), handler, argument_schema=schema)
    receipt = registry.invoke(
        TOOL_ID, expected, path_refs=[str(path) for path in (*SOURCE_PATHS, snapshot)],
        provider_id=PROVIDER_ID,
    )
    if (registry.calls_used != 1 or receipt["page_count"] != 3
            or receipt["anchor_count"] != 11 or receipt["step_count"] != 6
            or receipt["boundaries"]["execution_allowed"] is not False):
        raise ReplayMismatch("T5 source tool count, inventory, or execution boundary differs")
    return receipt, registry.calls_used


def verify_policy_denials(payload: dict[str, Any], snapshot: Path) -> dict[str, bool]:
    registry = ToolRegistry(_policy(snapshot))
    registry.register(_tool(), lambda _arguments: None,
                      argument_schema=json.loads(SCHEMA.read_text(encoding="utf-8")))
    arguments = _arguments(payload, snapshot)
    try:
        registry.invoke(TOOL_ID, arguments, provider_id="unregistered-provider")
    except PolicyDenied:
        wrong_provider_rejected = True
    else:
        wrong_provider_rejected = False
    try:
        registry.invoke(TOOL_ID, arguments, path_refs=[str(ROOT / "README.md")],
                        provider_id=PROVIDER_ID)
    except PolicyDenied:
        out_of_scope_path_rejected = True
    else:
        out_of_scope_path_rejected = False
    if registry.calls_used != 0 or not wrong_provider_rejected or not out_of_scope_path_rejected:
        raise ReplayMismatch("T5 source policy did not fail closed")
    return {"wrong_provider_rejected": wrong_provider_rejected,
            "out_of_scope_path_rejected": out_of_scope_path_rejected}


def _make_run(payload: dict[str, Any], receipt: dict[str, Any], calls_used: int,
              *, run_dir: Path) -> Run:
    snapshot = run_dir / "source-audit-snapshot.json"
    bindings = BoundPaths(root=ROOT, run_dir=run_dir)
    input_hash = canonical_hash(payload)
    run_id = f"run-t5-pbs-source-{input_hash[:16]}"
    evidence_specs = [
        ("ev-t5p-source-audit", EvidenceKind.SNAPSHOT, snapshot, ["source-inventory", "citation-only"]),
        ("ev-t5p-source-contract", EvidenceKind.SNAPSHOT, CONTRACT, ["rights-declaration", "scope-boundary"]),
        ("ev-t5p-tool-code", EvidenceKind.CODE, Path(__file__).resolve(), ["offline-tool", "source-provenance"]),
        ("ev-t5p-verifier-code", EvidenceKind.CODE, ROOT / "scripts/verify_t5_pbs_source.py", ["source-provenance"]),
        ("ev-t5p-method", EvidenceKind.SNAPSHOT, METHOD, ["method-and-boundaries"]),
    ]
    evidence = [Evidence(
        evidence_id=evidence_id, kind=kind, path_or_uri=bindings.ref(path),
        sha256=_digest(path), source_revision=installation_revision(),
        provenance_status=ProvenanceStatus.UNVERIFIED, allowed_use=allowed_use,
        notes="Real rights-declared PDF source inventory only; no protocol execution, biosafety clearance, or scientific validation.",
    ) for evidence_id, kind, path, allowed_use in evidence_specs]
    policy = _policy(snapshot).model_copy(update={
        "allowed_paths": [bindings.ref(path) for path in (*SOURCE_PATHS, snapshot)],
    })
    base_time = datetime(2026, 9, 28, tzinfo=timezone.utc)
    events: list[Event] = []
    previous = "genesis"
    for seq, (event_type, body) in enumerate([
        ("run.initialized", {"run_id": run_id, "input_hash": input_hash}),
        ("policy.applied", {"policy_id": policy.policy_id, "network": policy.network,
                             "provider_id": PROVIDER_ID}),
        ("tool.invoked", {"tool_id": TOOL_ID, "calls_used": calls_used}),
        ("evaluator.completed", {"evaluator_id": EVALUATOR_ID,
                                  "page_count": receipt["page_count"],
                                  "anchor_count": receipt["anchor_count"],
                                  "step_count": receipt["step_count"]}),
        ("review.required", {"safety_flags": receipt["review_flags"],
                              "execution_allowed": False}),
        ("run.completed", {"status": RunStatus.COMPLETED.value}),
    ]):
        payload_hash = canonical_hash(body)
        events.append(Event(
            event_id=f"t5-pbs-event-{seq}", seq=seq, event_type=event_type,
            occurred_at=base_time+timedelta(seconds=seq), payload_hash=payload_hash,
            prev_event_hash=previous, payload=body,
        ))
        previous = payload_hash
    trace = Trace(trace_id=f"trace-{run_id}", run_id=run_id, input_hash=input_hash,
                  entries=[{"seq": item.seq, "event_type": item.event_type,
                            "payload_hash": item.payload_hash} for item in events])
    return Run(
        run_id=run_id, task_id="t5-optional-pbs-source-review-v1", created_at=base_time,
        input_hash=input_hash, code_revision=installation_revision(),
        environment={**capture_environment(["auditable-scientist-lab", "pydantic", "jsonschema"]),
                     "mode": "offline", "track_id": "T5",
                     "runtime": "optional-read-only-real-source-inventory",
                     "network": "disabled", "provider_id": PROVIDER_ID},
        seed=17, evidence_refs=[item.evidence_id for item in evidence],
        status=RunStatus.COMPLETED,
        agent=Agent(agent_id="offline-t5-pbs-source-agent-v1",
                    name="Offline T5 document evidence agent", version="1",
                    capabilities=["invoke-read-only-source-audit", "record-human-review-block"]),
        tools=[_tool()],
        memories=[Memory(memory_id="evidence-policy-memory-v1",
                         source_ref=bindings.ref(MEMORY_SOURCE),
                         scope="claim-level evidence boundaries",
                         version="local-snapshot", content_hash=_digest(MEMORY_SOURCE))],
        evaluators=[Evaluator(evaluator_id=EVALUATOR_ID,
                              name="T5 real-source citation-inventory evaluator",
                              version="1", read_only=True)],
        providers=[Provider(provider_id=PROVIDER_ID,
                            kind="deterministic-domain-evaluator",
                            name="Local read-only source inventory",
                            version="1", source_ref="scripts/verify_t5_pbs_source.py")],
        policy=policy, events=events, traces=[trace],
        claims=[Claim(
            text="The cited PBS document is an independently validated and safe executable protocol.",
            status=ClaimStatus.UNVERIFIED, level=EvidenceLevel.DEMO,
            evidence_refs=[item.evidence_id for item in evidence],
            falsification_checks=["source-hash-and-license", "page-citation-inventory",
                                  "branch-and-safety-flags", "read-only-policy",
                                  "human-biosafety-review-required"],
            holdout_verified=False,
        )],
        observations=[Observation(
            observation_id="obs-t5-pbs-source-inventory",
            dataset_hash=receipt["source_pdf_sha256"], split="external",
            summary={"scope": "rights-declared-document-only",
                     "page_count": receipt["page_count"],
                     "anchor_count": receipt["anchor_count"],
                     "step_count": receipt["step_count"],
                     "execution_allowed": False},
            units={}, source_ref=bindings.ref(snapshot),
        )],
        evidence=evidence,
    )


def _write_json(path: Path, payload: Any) -> None:
    path.write_text(canonical_json(payload)+"\n", encoding="utf-8", newline="\n")


def _report(run: Run, receipt: dict[str, Any]) -> str:
    return (
        "# T5 read-only PBS source Run\n\n"
        f"- Run: `{run.run_id}`\n"
        f"- Provider: `{PROVIDER_ID}`\n"
        f"- DOI: `{receipt['doi']}`; source PDF SHA-256: `{receipt['source_pdf_sha256']}`\n"
        f"- Pages: `{receipt['page_count']}`; citation anchors: `{receipt['anchor_count']}`; numbered steps: `{receipt['step_count']}`\n"
        f"- Claim: `{run.claims[0].status.value}`; execution allowed: `false`; human review required: `true`\n"
        f"- Result hash: `{canonical_hash(receipt)}`\n\n"
        "The source's license declaration is recorded. The step inventory is not an executable recipe, an independent reproduction, or a biosafety clearance.\n"
    )


def write_run() -> Path:
    payload = input_payload()
    run_dir = RUNS / f"run-t5-pbs-source-{canonical_hash(payload)[:16]}"
    if run_dir.exists():
        raise FileExistsError(f"refusing to overwrite existing T5 source Run: {run_dir}")
    run_dir.mkdir(parents=True)
    snapshot = run_dir / "source-audit-snapshot.json"
    shutil.copyfile(STATIC_AUDIT, snapshot)
    receipt, calls_used = execute(payload, snapshot)
    run = _make_run(payload, receipt, calls_used, run_dir=run_dir)
    bindings = BoundPaths(root=ROOT, run_dir=run_dir)
    _write_json(run_dir / "input.json", payload)
    _write_json(run_dir / "result.json", {"provider_id": PROVIDER_ID, "receipt": receipt})
    _write_json(run_dir / "run.json", run.model_dump(mode="json"))
    (run_dir / "events.jsonl").write_text(
        "".join(canonical_json(event)+"\n" for event in run.events),
        encoding="utf-8", newline="\n",
    )
    ReplayManifest.create(
        input_payload=payload, code_revision=run.code_revision,
        environment=run.environment, seed=run.seed,
        source_paths=SOURCE_PATHS, evidence_paths=[snapshot],
        computational_output=receipt, bindings=bindings,
    ).write(run_dir / "replay-manifest.json")
    (run_dir / "report.md").write_text(_report(run, receipt),
                                         encoding="utf-8", newline="\n")
    return run_dir


def replay_run(run_dir: Path) -> dict[str, Any]:
    run_dir = run_dir.resolve()
    bindings = BoundPaths(root=ROOT, run_dir=run_dir)
    manifest = ReplayManifest.load(run_dir / "replay-manifest.json")
    if manifest.schema_version != "replay-manifest-v2":
        raise ReplayMismatch("T5 source Run requires a portable manifest")
    payload = input_payload()
    if (json.loads((run_dir / "input.json").read_text(encoding="utf-8")) != payload
            or run_dir.name != f"run-t5-pbs-source-{canonical_hash(payload)[:16]}"):
        raise ReplayMismatch("saved T5 source Run input or identity changed")
    snapshot = run_dir / "source-audit-snapshot.json"
    receipt, calls_used = execute(payload, snapshot)
    if json.loads((run_dir / "result.json").read_text(encoding="utf-8")) != {
            "provider_id": PROVIDER_ID, "receipt": receipt}:
        raise ReplayMismatch("saved T5 source result changed")
    run = verify_run_record(run_dir / "run.json", run_dir / "events.jsonl",
                            root=ROOT, bindings=bindings)
    expected = _make_run(payload, receipt, calls_used, run_dir=run_dir)
    if canonical_hash(run) != canonical_hash(expected):
        raise ReplayMismatch("saved T5 shared-kernel Run changed")
    replay = manifest.verify(
        input_payload=payload, code_revision=expected.code_revision,
        environment=expected.environment, seed=expected.seed,
        source_paths=SOURCE_PATHS, evidence_paths=[snapshot], candidate_order=[],
        computational_output=receipt, bindings=bindings,
    ).model_dump(mode="json")
    if (run_dir / "report.md").read_text(encoding="utf-8") != _report(run, receipt):
        raise ReplayMismatch("saved T5 source report changed")
    return replay


def verify_run_and_mutations(run_dir: Path) -> dict[str, Any]:
    original = replay_run(run_dir)
    with tempfile.TemporaryDirectory(prefix="scientist-t5-pbs-replay-") as temporary:
        relocated = Path(temporary).resolve() / run_dir.name
        if not relocated.is_relative_to(Path(tempfile.gettempdir()).resolve()):
            raise ReplayMismatch("temporary T5 relocation escaped system temp")
        shutil.copytree(run_dir, relocated)
        if replay_run(relocated) != original:
            raise ReplayMismatch("relocated T5 source Run differs")
        result_path = relocated / "result.json"
        original_result = result_path.read_bytes()
        changed = json.loads(original_result)
        changed["receipt"]["boundaries"]["execution_allowed"] = True
        _write_json(result_path, changed)
        try:
            replay_run(relocated)
        except ReplayMismatch:
            result_tamper_rejected = True
        else:
            result_tamper_rejected = False
        result_path.write_bytes(original_result)
        snapshot = relocated / "source-audit-snapshot.json"
        snapshot.write_bytes(snapshot.read_bytes()+b"\nchanged\n")
        try:
            replay_run(relocated)
        except ReplayMismatch:
            snapshot_tamper_rejected = True
        else:
            snapshot_tamper_rejected = False
    if not result_tamper_rejected or not snapshot_tamper_rejected:
        raise ReplayMismatch("T5 source Run mutation controls failed")
    return {
        "schema_version": "t5-pbs-source-run-audit-v1",
        "status": "verified-read-only-source-inventory-only",
        "run_path": run_dir.relative_to(ROOT).as_posix(),
        "run_id": run_dir.name,
        "replay": original,
        "relocated_replay_equal": True,
        "result_tamper_rejected": result_tamper_rejected,
        "snapshot_tamper_rejected": snapshot_tamper_rejected,
        "policy_denials": verify_policy_denials(input_payload(),
                                                 run_dir / "source-audit-snapshot.json"),
        "boundaries": {"source_inventory_only": True,
                       "real_source_document": True,
                       "independent_procedure_validation": False,
                       "biosafety_review_complete": False,
                       "human_acceptance": False,
                       "execution_allowed": False,
                       "claim_status": "unverified"},
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
        AUDIT.write_text(json.dumps(result, indent=2, sort_keys=True)+"\n",
                         encoding="utf-8", newline="\n")
    else:
        run_dir = RUNS / f"run-t5-pbs-source-{canonical_hash(input_payload())[:16]}"
        result = verify_run_and_mutations(run_dir)
        saved = json.loads(AUDIT.read_text(encoding="utf-8"))
        stamp = saved.pop("recorded_at", None)
        if (not isinstance(stamp, str)
                or datetime.fromisoformat(stamp.replace("Z", "+00:00")).tzinfo is None
                or saved != result):
            raise ReplayMismatch("T5 source Run audit differs from current replay")
    print(json.dumps({"status": result["status"], "run_id": result["run_id"],
                      "replay": result["replay"],
                      "mutation_controls": [result["result_tamper_rejected"],
                                            result["snapshot_tamper_rejected"]]},
                     sort_keys=True))


if __name__ == "__main__":
    main()
