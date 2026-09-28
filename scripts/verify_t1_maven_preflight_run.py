"""Build and replay an offline shared-kernel Run for the MAVEN short-arc preflight."""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
import math
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

from verify_t1_maven_preflight import propagate, specific_energy


ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT = ROOT / "artifacts/t1-maven-preflight-snapshot.json"
SOURCE_AUDIT = ROOT / "artifacts/t1-maven-preflight-audit.json"
PROTOCOL = ROOT / "docs/T1_MAVEN_PROPAGATION_PREFLIGHT.json"
METHOD = ROOT / "docs/T1_MAVEN_PREFLIGHT_RUN.md"
SCHEMA = ROOT / "docs/contracts/t1-maven-preflight-snapshot-tool-v1.json"
MEMORY_SOURCE = ROOT / "docs/EVIDENCE_POLICY.md"
AUDIT = ROOT / "artifacts/t1-maven-preflight-run-audit.json"
RUNS = ROOT / "artifacts/t1-maven-preflight-runs"
PROVIDER_ID = "internal-t1-maven-short-arc-v1"
TOOL_ID = "t1-maven-offline-short-arc-v1"
EVALUATOR_ID = "t1-maven-sun-only-snapshot-v1"
PROTOCOL_SHA256 = "a37b11b983a9ea0765682d4457c8eed9b378566262fa3adc478d7d60ef9e5a47"
SOURCE_PATHS = [
    Path(__file__).resolve(), ROOT / "scripts/verify_t1_maven_preflight.py",
    SNAPSHOT, SOURCE_AUDIT, PROTOCOL, METHOD, SCHEMA, MEMORY_SOURCE,
    ROOT / "src/auditable_scientist/domain/models.py",
    ROOT / "src/auditable_scientist/policy/runtime.py",
    ROOT / "src/auditable_scientist/runtime/replay.py",
    ROOT / "src/auditable_scientist/runtime/run_integrity.py",
]


def _digest(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _write_json(path: Path, value: Any) -> None:
    path.write_text(canonical_json(value) + "\n", encoding="utf-8", newline="\n")


def input_payload() -> dict[str, Any]:
    audit = json.loads(SOURCE_AUDIT.read_text(encoding="utf-8"))
    snapshot = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    if (audit.get("status") != "passed-engineering-preflight-only"
            or audit.get("snapshot_sha256") != _digest(SNAPSHOT)
            or audit.get("protocol_sha256") != PROTOCOL_SHA256
            or _digest(PROTOCOL) != PROTOCOL_SHA256
            or snapshot.get("claim_status") != "unverified"
            or snapshot.get("engineering_preflight_passed") is not True
            or snapshot.get("scientific_boundaries", {}).get("mission_validation") is not False):
        raise ReplayMismatch("MAVEN source audit, protocol, or snapshot boundary changed")
    return {
        "schema_version": "t1-maven-preflight-run-input-v1",
        "track_id": "T1", "provider_id": PROVIDER_ID,
        "snapshot_sha256": _digest(SNAPSHOT),
        "source_audit_sha256": _digest(SOURCE_AUDIT),
        "protocol_sha256": PROTOCOL_SHA256,
        "source_inventory_hash": canonical_hash([
            (path.relative_to(ROOT).as_posix(), _digest(path)) for path in SOURCE_PATHS
        ]),
        "initial_et_tdb_seconds": [452_088_000.0, 457_272_000.0],
        "claim_status": "unverified",
    }


def _norm(values: list[float]) -> float:
    return math.sqrt(sum(value * value for value in values))


def recompute_preflight(snapshot: dict[str, Any]) -> dict[str, Any]:
    """Recompute NAV-endpoint comparison only from saved states; never query SPICE."""
    protocol = json.loads(PROTOCOL.read_text(encoding="utf-8"))
    if (snapshot.get("schema_version") != "t1-maven-sun-only-preflight-snapshot-v1"
            or snapshot.get("protocol_sha256") != PROTOCOL_SHA256
            or snapshot.get("claim_status") != "unverified"
            or snapshot.get("engineering_preflight_passed") is not True
            or snapshot.get("scientific_boundaries") != {
                "mission_validation": False, "full_force_model": False,
                "maneuver_reconstruction": False, "untouched_scientific_holdout": False}
            or snapshot.get("engineering_gates") != protocol["engineering_gates"]
            or snapshot.get("model") != protocol["model"]
            or snapshot.get("coordinate_contract") != protocol["coordinate_contract"]
            or snapshot.get("mission_only_states_equal") is not True):
        raise ReplayMismatch("MAVEN saved preflight boundary or protocol changed")
    arcs = snapshot.get("arcs")
    starts = protocol["time_contract"]["initial_et_seconds"]
    if (not isinstance(arcs, list) or len(arcs) != 2
            or [arc.get("initial_et_tdb_seconds") for arc in arcs] != starts):
        raise ReplayMismatch("MAVEN saved arc inventory differs from protocol")
    model = protocol["model"]
    gates = protocol["engineering_gates"]
    mu = model["mu_sun_km3_s2"]
    horizon = protocol["time_contract"]["horizon_seconds"]
    result_rows = []
    for arc in arcs:
        initial = arc.get("initial_nav_sun_state_km_kms")
        target = arc.get("held_nav_endpoint_sun_state_km_kms")
        if (arc.get("endpoint_et_tdb_seconds") != arc["initial_et_tdb_seconds"] + horizon
                or arc.get("start_segment_center_id") != 10
                or arc.get("endpoint_segment_center_id") != 10
                or any(not isinstance(state, list) or len(state) != 6
                       or any(not isinstance(value, (int, float)) or not math.isfinite(value)
                              for value in state) for state in (initial, target))):
            raise ReplayMismatch("MAVEN saved state or Sun-centered segment differs")
        start = tuple(float(value) for value in initial)
        predicted = propagate(start, mu, horizon, model["step_seconds"])
        refined = propagate(start, mu, horizon, model["refinement_step_seconds"])
        repulsive = propagate(start, mu, horizon, model["step_seconds"], gravity_sign=-1)
        position_error = _norm([a-b for a, b in zip(predicted[:3], target[:3], strict=True)])
        velocity_error = _norm([a-b for a, b in zip(predicted[3:], target[3:], strict=True)])
        refinement_error = _norm([a-b for a, b in zip(predicted[:3], refined[:3], strict=True)])
        wrong_sign_error = _norm([a-b for a, b in zip(repulsive[:3], target[:3], strict=True)])
        initial_energy = specific_energy(start, mu)
        energy_drift = abs(specific_energy(predicted, mu) - initial_energy) / max(abs(initial_energy), 1.0)
        values = {
            "position_error_km": position_error,
            "velocity_error_km_s": velocity_error,
            "refinement_position_difference_km": refinement_error,
            "relative_two_body_energy_drift": energy_drift,
            "wrong_sign_position_error_km": wrong_sign_error,
        }
        if (any(not math.isclose(arc.get(key, float("nan")), value, rel_tol=0,
                                 abs_tol=1e-8 if key.endswith("_km") else 1e-12)
                for key, value in values.items())
                or any(not math.isclose(a, b, rel_tol=0, abs_tol=1e-8 if index < 3 else 1e-12)
                       for index, (a, b) in enumerate(zip(arc["sun_only_rk4_endpoint_state_km_kms"],
                                                       predicted, strict=True)))
                or position_error > gates["endpoint_position_error_km_max"]
                or velocity_error > gates["endpoint_velocity_error_km_s_max"]
                or refinement_error > gates["refinement_position_difference_km_max"]
                or energy_drift > gates["relative_two_body_energy_drift_max"]
                or wrong_sign_error <= gates["endpoint_position_error_km_max"]
                or arc.get("engineering_gates_passed") is not True):
            raise ReplayMismatch("MAVEN saved propagation metric or negative control differs")
        result_rows.append({"initial_et_tdb_seconds": arc["initial_et_tdb_seconds"], **values,
                            "engineering_gates_passed": True})
    return {
        "status": "verified-saved-nav-short-arc-comparison-only",
        "arc_count": 2, "rows": result_rows,
        "source_kernel_sha256": snapshot["source_hashes"]["maven_cruise"]["sha256"],
        "snapshot_sha256": _digest(SNAPSHOT),
        "mission_claim_status": "unverified",
        "dynamic_kernel_recomputed": False,
        "scientific_holdout": False,
    }


def _policy(snapshot_path: Path) -> Policy:
    return Policy(
        policy_id="offline-t1-maven-preflight-v1", network="disabled",
        max_seconds=60, max_tool_calls=1,
        allowed_paths=[str(path.resolve()) for path in (*SOURCE_PATHS, snapshot_path)],
        allowed_providers=[PROVIDER_ID],
    )


def _tool() -> Tool:
    return Tool(tool_id=TOOL_ID, name="Offline MAVEN short-arc snapshot checker",
                version="1", parameter_schema_ref=SCHEMA.relative_to(ROOT).as_posix(),
                deterministic=True, network_required=False)


def _arguments(payload: dict[str, Any], snapshot_path: Path) -> dict[str, str]:
    return {"provider_id": PROVIDER_ID, "input_hash": canonical_hash(payload),
            "snapshot_path": str(snapshot_path.resolve())}


def execute(payload: dict[str, Any], snapshot_path: Path) -> tuple[dict[str, Any], int]:
    registry = ToolRegistry(_policy(snapshot_path))
    arguments = _arguments(payload, snapshot_path)

    def handler(actual: dict[str, Any]) -> dict[str, Any]:
        if actual != arguments or payload != input_payload():
            raise ReplayMismatch("MAVEN Tool input or source inventory changed")
        if snapshot_path.read_bytes() != SNAPSHOT.read_bytes():
            raise ReplayMismatch("MAVEN Run snapshot differs from pinned source")
        return recompute_preflight(json.loads(snapshot_path.read_text(encoding="utf-8")))

    registry.register(_tool(), handler, argument_schema=json.loads(SCHEMA.read_text(encoding="utf-8")))
    receipt = registry.invoke(TOOL_ID, arguments,
                              path_refs=[str(path) for path in (*SOURCE_PATHS, snapshot_path)],
                              provider_id=PROVIDER_ID)
    if (registry.calls_used != 1 or receipt["mission_claim_status"] != "unverified"
            or receipt["scientific_holdout"] is not False):
        raise ReplayMismatch("MAVEN Tool/Policy result exceeds engineering scope")
    return receipt, registry.calls_used


def policy_denials(payload: dict[str, Any], snapshot_path: Path) -> dict[str, bool]:
    registry = ToolRegistry(_policy(snapshot_path))
    registry.register(_tool(), lambda _: None,
                      argument_schema=json.loads(SCHEMA.read_text(encoding="utf-8")))
    arguments = _arguments(payload, snapshot_path)
    checks = {}
    for name, kwargs in (
        ("wrong_provider_rejected", {"provider_id": "unknown"}),
        ("out_of_scope_path_rejected", {"provider_id": PROVIDER_ID,
                                        "path_refs": [str(ROOT / "README.md")]}),
    ):
        try:
            registry.invoke(TOOL_ID, arguments, **kwargs)
        except PolicyDenied:
            checks[name] = True
        else:
            checks[name] = False
    if registry.calls_used or not all(checks.values()):
        raise ReplayMismatch("MAVEN policy denial controls failed")
    return checks


def _make_run(payload: dict[str, Any], receipt: dict[str, Any], calls_used: int,
              run_dir: Path) -> Run:
    snapshot_path = run_dir / "nav-snapshot.json"
    bindings = BoundPaths(root=ROOT, run_dir=run_dir)
    input_hash = canonical_hash(payload)
    run_id = f"run-t1-maven-{input_hash[:16]}"
    evidence_specs = [
        ("ev-t1-maven-nav-states", EvidenceKind.DATA, snapshot_path, ["short-arc-engineering-comparison"]),
        ("ev-t1-maven-source-audit", EvidenceKind.SNAPSHOT, SOURCE_AUDIT, ["source-and-boundary-audit"]),
        ("ev-t1-maven-protocol", EvidenceKind.SNAPSHOT, PROTOCOL, ["precommitted-engineering-protocol"]),
        ("ev-t1-maven-propagator", EvidenceKind.CODE,
         ROOT / "scripts/verify_t1_maven_preflight.py", ["offline-propagation-code"]),
        ("ev-t1-maven-run-tool", EvidenceKind.CODE, Path(__file__).resolve(), ["offline-replay-code"]),
        ("ev-t1-maven-method", EvidenceKind.SNAPSHOT, METHOD, ["scope-and-boundaries"]),
    ]
    evidence = [Evidence(
        evidence_id=identity, kind=kind, path_or_uri=bindings.ref(path),
        sha256=_digest(path), source_revision=installation_revision(),
        provenance_status=ProvenanceStatus.UNVERIFIED, allowed_use=allowed_use,
        notes="PDS NAV reconstructed states; engineering short arc only; no mission validation.",
    ) for identity, kind, path, allowed_use in evidence_specs]
    policy = _policy(snapshot_path).model_copy(update={
        "allowed_paths": [bindings.ref(path) for path in (*SOURCE_PATHS, snapshot_path)],
    })
    started = datetime(2026, 9, 27, tzinfo=timezone.utc)
    events: list[Event] = []
    previous = "genesis"
    negative = all(row["wrong_sign_position_error_km"] > 100 for row in receipt["rows"])
    for seq, (kind, body) in enumerate([
        ("run.initialized", {"run_id": run_id, "input_hash": input_hash}),
        ("policy.applied", {"policy_id": policy.policy_id, "network": "disabled"}),
        ("tool.invoked", {"tool_id": TOOL_ID, "calls_used": calls_used}),
        ("evaluator.completed", {"evaluator_id": EVALUATOR_ID, "result": receipt}),
        ("negative_case.checked", {"wrong_sign_gravity_rejected": negative}),
        ("run.completed", {"status": RunStatus.COMPLETED.value}),
    ]):
        digest = canonical_hash(body)
        events.append(Event(event_id=f"t1-maven-event-{seq}", seq=seq,
                            event_type=kind, occurred_at=started + timedelta(seconds=seq),
                            payload_hash=digest, prev_event_hash=previous, payload=body))
        previous = digest
    trace = Trace(trace_id=f"trace-{run_id}", run_id=run_id, input_hash=input_hash,
                  entries=[{"seq": item.seq, "event_type": item.event_type,
                            "payload_hash": item.payload_hash} for item in events])
    return Run(
        run_id=run_id, task_id="t1-maven-short-arc-preflight-v1",
        created_at=started, input_hash=input_hash, code_revision=installation_revision(),
        environment={**capture_environment(["auditable-scientist-lab", "pydantic", "sympy", "jsonschema"]),
                     "mode": "offline", "track_id": "T1", "runtime": "maven-saved-nav-short-arc",
                     "network": "disabled", "provider_id": PROVIDER_ID},
        seed=17, evidence_refs=[item.evidence_id for item in evidence], status=RunStatus.COMPLETED,
        agent=Agent(agent_id="offline-t1-maven-agent-v1", name="Offline MAVEN preflight agent",
                    version="1", capabilities=["invoke-registered-short-arc-checker"]),
        tools=[_tool()],
        memories=[Memory(memory_id="evidence-policy-memory-v1", source_ref=bindings.ref(MEMORY_SOURCE),
                         scope="claim-level evidence boundaries", version="local-snapshot",
                         content_hash=_digest(MEMORY_SOURCE))],
        evaluators=[Evaluator(evaluator_id=EVALUATOR_ID, name="MAVEN saved NAV short-arc checker",
                              version="1", read_only=True)],
        providers=[Provider(provider_id=PROVIDER_ID, kind="deterministic-numerical-backend",
                            name="Offline Sun-only RK4", version="1",
                            source_ref="scripts/verify_t1_maven_preflight.py")],
        policy=policy, events=events, traces=[trace],
        claims=[Claim(text="The Sun-only preflight validates the MAVEN mission trajectory.",
                      status=ClaimStatus.UNVERIFIED, level=EvidenceLevel.DEMO,
                      evidence_refs=[item.evidence_id for item in evidence],
                      falsification_checks=["precommitted-short-arc-endpoints", "source-hash",
                                             "wrong-sign-gravity", "snapshot-mutation",
                                             "independent-mission-observables"],
                      holdout_verified=False)],
        observations=[Observation(observation_id="obs-t1-maven-short-arcs",
                                  dataset_hash=_digest(snapshot_path), split="external",
                                  summary={"arc_count": 2,
                                           "position_error_km": [row["position_error_km"] for row in receipt["rows"]],
                                           "scope": "precommitted-engineering-comparison-only"},
                                  units={"position": "km", "velocity": "km/s", "time": "TDB seconds past J2000"},
                                  source_ref=bindings.ref(snapshot_path))],
        evidence=evidence,
    )


def _report(run: Run, receipt: dict[str, Any]) -> str:
    positions = [row["position_error_km"] for row in receipt["rows"]]
    return ("# T1 MAVEN offline short-arc Run\n\n"
            f"- Run: `{run.run_id}`\n"
            f"- Arc count: `{receipt['arc_count']}`\n"
            f"- Endpoint position errors (km): `{positions}`\n"
            f"- Wrong-sign gravity rejected: `{all(row['wrong_sign_position_error_km'] > 100 for row in receipt['rows'])}`\n"
            f"- Mission Claim: `{run.claims[0].status.value}`\n"
            f"- Result hash: `{canonical_hash(receipt)}`\n\n"
            "Replay propagates saved NAV initial states with the Sun-only RK4 model; it does not query SPICE. "
            "The source is a reconstructed mission solution, not independent flight truth. "
            "No full force/maneuver model, scientific holdout, encounter or mission validation is established.\n")


def write_run() -> Path:
    payload = input_payload()
    run_dir = RUNS / f"run-t1-maven-{canonical_hash(payload)[:16]}"
    if run_dir.exists():
        raise FileExistsError(f"refusing to overwrite existing MAVEN Run: {run_dir}")
    run_dir.mkdir(parents=True)
    snapshot_path = run_dir / "nav-snapshot.json"
    shutil.copyfile(SNAPSHOT, snapshot_path)
    receipt, calls_used = execute(payload, snapshot_path)
    run = _make_run(payload, receipt, calls_used, run_dir)
    _write_json(run_dir / "input.json", payload)
    _write_json(run_dir / "result.json", {"provider_id": PROVIDER_ID, "receipt": receipt})
    _write_json(run_dir / "run.json", run.model_dump(mode="json"))
    (run_dir / "events.jsonl").write_text(
        "".join(canonical_json(event) + "\n" for event in run.events),
        encoding="utf-8", newline="\n")
    ReplayManifest.create(input_payload=payload, code_revision=run.code_revision,
                          environment=run.environment, seed=run.seed,
                          source_paths=SOURCE_PATHS, evidence_paths=[snapshot_path],
                          computational_output=receipt,
                          bindings=BoundPaths(root=ROOT, run_dir=run_dir)).write(
                              run_dir / "replay-manifest.json")
    (run_dir / "report.md").write_text(_report(run, receipt), encoding="utf-8", newline="\n")
    return run_dir


def replay_run(run_dir: Path) -> dict[str, Any]:
    run_dir = run_dir.resolve()
    bindings = BoundPaths(root=ROOT, run_dir=run_dir)
    manifest = ReplayManifest.load(run_dir / "replay-manifest.json")
    if manifest.schema_version != "replay-manifest-v2":
        raise ReplayMismatch("MAVEN Run requires a portable manifest")
    payload = input_payload()
    if (json.loads((run_dir / "input.json").read_text(encoding="utf-8")) != payload
            or run_dir.name != f"run-t1-maven-{canonical_hash(payload)[:16]}"):
        raise ReplayMismatch("saved MAVEN Run input or identity changed")
    snapshot_path = run_dir / "nav-snapshot.json"
    receipt, calls_used = execute(payload, snapshot_path)
    if json.loads((run_dir / "result.json").read_text(encoding="utf-8")) != {
            "provider_id": PROVIDER_ID, "receipt": receipt}:
        raise ReplayMismatch("saved MAVEN Run output changed")
    run = verify_run_record(run_dir / "run.json", run_dir / "events.jsonl",
                            root=ROOT, bindings=bindings)
    expected = _make_run(payload, receipt, calls_used, run_dir)
    if canonical_hash(run) != canonical_hash(expected):
        raise ReplayMismatch("saved MAVEN shared-kernel Run changed")
    result = manifest.verify(input_payload=payload, code_revision=expected.code_revision,
                             environment=expected.environment, seed=expected.seed,
                             source_paths=SOURCE_PATHS, evidence_paths=[snapshot_path],
                             candidate_order=[], computational_output=receipt,
                             bindings=bindings).model_dump(mode="json")
    if (run_dir / "report.md").read_text(encoding="utf-8") != _report(run, receipt):
        raise ReplayMismatch("saved MAVEN Run report changed")
    return result


def verify_run_and_mutations(run_dir: Path) -> dict[str, Any]:
    original = replay_run(run_dir)
    with tempfile.TemporaryDirectory(prefix="scientist-maven-replay-") as temporary:
        relocated = Path(temporary).resolve() / run_dir.name
        shutil.copytree(run_dir, relocated)
        if replay_run(relocated) != original:
            raise ReplayMismatch("relocated MAVEN Run differs")
        output = relocated / "result.json"
        saved = output.read_bytes()
        changed = json.loads(saved)
        changed["receipt"]["rows"][0]["position_error_km"] += 1
        _write_json(output, changed)
        try:
            replay_run(relocated)
        except ReplayMismatch:
            result_tamper_rejected = True
        else:
            result_tamper_rejected = False
        output.write_bytes(saved)
        snapshot = relocated / "nav-snapshot.json"
        snapshot.write_bytes(snapshot.read_bytes() + b"\nchanged\n")
        try:
            replay_run(relocated)
        except ReplayMismatch:
            snapshot_tamper_rejected = True
        else:
            snapshot_tamper_rejected = False
    if not result_tamper_rejected or not snapshot_tamper_rejected:
        raise ReplayMismatch("MAVEN mutation controls failed")
    return {
        "schema_version": "t1-maven-preflight-run-audit-v1",
        "status": "verified-offline-short-arc-run-only",
        "run_path": run_dir.relative_to(ROOT).as_posix(),
        "run_id": run_dir.name, "replay": original,
        "relocated_replay_equal": True,
        "result_tamper_rejected": result_tamper_rejected,
        "snapshot_tamper_rejected": snapshot_tamper_rejected,
        "policy_denials": policy_denials(input_payload(), run_dir / "nav-snapshot.json"),
        "boundaries": {"real_mission_source_tracked": True,
                       "dynamic_kernel_recomputed_in_replay": False,
                       "sun_only_short_arc_recomputed": True,
                       "full_force_maneuver_model": False,
                       "scientific_holdout": False,
                       "mission_claim_verified": False,
                       "publication_ready": False},
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
        AUDIT.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n",
                         encoding="utf-8", newline="\n")
    else:
        run_dir = RUNS / f"run-t1-maven-{canonical_hash(input_payload())[:16]}"
        result = verify_run_and_mutations(run_dir)
        saved = json.loads(AUDIT.read_text(encoding="utf-8"))
        recorded_at = saved.pop("recorded_at", None)
        if not recorded_at or datetime.fromisoformat(recorded_at).tzinfo is None or saved != result:
            raise ReplayMismatch("MAVEN Run audit differs from current replay")
    print(json.dumps({"status": result["status"], "run_id": result["run_id"],
                      "replay": result["replay"],
                      "mutation_controls": [result["result_tamper_rejected"],
                                            result["snapshot_tamper_rejected"]]},
                     sort_keys=True))


if __name__ == "__main__":
    main()
