"""Build and replay a portable, offline T1 DE440s snapshot geometry Run."""

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


ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT = ROOT / "artifacts/t1-de440s-ephemeris-snapshot.json"
SOURCE_AUDIT = ROOT / "artifacts/t1-de440s-ephemeris-audit.json"
METHOD = ROOT / "docs/T1_DE440S_RUN.md"
SCHEMA = ROOT / "docs/contracts/t1-de440s-snapshot-tool-v1.json"
MEMORY_SOURCE = ROOT / "docs/EVIDENCE_POLICY.md"
AUDIT = ROOT / "artifacts/t1-de440s-run-audit.json"
RUNS = ROOT / "artifacts/t1-de440s-runs"
PROVIDER_ID = "internal-t1-de440s-snapshot-v1"
TOOL_ID = "t1-de440s-offline-geometry-v1"
EVALUATOR_ID = "t1-de440s-snapshot-geometry-v1"
SOURCE_PATHS = [
    Path(__file__).resolve(), SNAPSHOT, SOURCE_AUDIT, METHOD, SCHEMA,
    MEMORY_SOURCE, ROOT / "src/auditable_scientist/domain/models.py",
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
    if (audit.get("status") != "verified-source-tracked-geometry-only"
            or audit.get("snapshot_sha256") != _digest(SNAPSHOT)
            or snapshot.get("claim_status") != "unverified"
            or snapshot.get("source", {}).get("sha256") !=
            "c1c7feeab882263fc493a9d5a5b2ddd71b54826cdf65d8d17a76126b260a49f2"):
        raise ReplayMismatch("DE440s source audit or snapshot boundary changed")
    return {
        "schema_version": "t1-de440s-snapshot-run-input-v1",
        "track_id": "T1", "provider_id": PROVIDER_ID,
        "snapshot_sha256": _digest(SNAPSHOT),
        "source_audit_sha256": _digest(SOURCE_AUDIT),
        "source_inventory_hash": canonical_hash([
            (path.relative_to(ROOT).as_posix(), _digest(path)) for path in SOURCE_PATHS
        ]),
        "departure_jd_tdb": [2460584.5, 2461375.5],
        "claim_status": "unverified",
    }


def recompute_geometry(snapshot: dict[str, Any]) -> dict[str, Any]:
    """Check internal geometry of pinned ephemeris states without CSPICE."""
    if (snapshot.get("schema_version") != "t1-de440s-fixed-date-geometry-v1"
            or snapshot.get("claim_status") != "unverified"
            or snapshot.get("evidence_level") != "real-data"
            or snapshot.get("coordinate_contract", {}).get("mars_target") !=
            "MARS BARYCENTER (4), not Mars center (499)"):
        raise ReplayMismatch("DE440s snapshot contract changed")
    cases = snapshot.get("cases")
    if not isinstance(cases, list) or len(cases) != 2:
        raise ReplayMismatch("DE440s fixed-date case inventory changed")
    dates = [2460584.5, 2461375.5]
    gaps: list[float] = []
    angles: list[float] = []
    for row, date in zip(cases, dates, strict=True):
        if row.get("departure_jd_tdb") != date:
            raise ReplayMismatch("DE440s predeclared departure date changed")
        earth = row.get("earth_departure_state_km_kms")
        mars_departure = row.get("mars_barycenter_departure_state_km_kms")
        mars_arrival = row.get("mars_barycenter_arrival_state_km_kms")
        if any(not isinstance(vector, list) or len(vector) != 6 or
               any(not isinstance(value, (int, float)) or not math.isfinite(value)
                   for value in vector)
               for vector in (earth, mars_departure, mars_arrival)):
            raise ReplayMismatch("DE440s state vector is incomplete or nonfinite")
        norm = lambda vector: math.sqrt(sum(value * value for value in vector))
        r_earth = norm(earth[:3])
        r_mars = norm(mars_departure[:3])
        if not 100_000_000 < r_earth < 200_000_000 or not 180_000_000 < r_mars < 300_000_000:
            raise ReplayMismatch("DE440s state radius is outside declared scale")
        tof = math.pi * math.sqrt(((r_earth + r_mars) / 2) ** 3 /
                                  snapshot["gm_sun_km3_s2"]) / 86_400
        ideal = [-value * r_mars / r_earth for value in earth[:3]]
        gap = norm([actual - predicted for actual, predicted in
                    zip(mars_arrival[:3], ideal, strict=True)])
        cosine = (sum(a * b for a, b in zip(earth[:3], mars_arrival[:3], strict=True)) /
                  (r_earth * norm(mars_arrival[:3])))
        angle = 180 - math.degrees(math.acos(max(-1.0, min(1.0, cosine))))
        for key, actual, tolerance in (
            ("ideal_tof_days", tof, 1e-10),
            ("arrival_jd_tdb", date + tof, 1e-9),
            ("arrival_position_gap_km", gap, 1e-5),
            ("opposition_angle_gap_deg", angle, 1e-10),
        ):
            if not math.isclose(row[key], actual, rel_tol=0, abs_tol=tolerance):
                raise ReplayMismatch(f"DE440s saved {key} differs from state-vector calculation")
        if any(not math.isclose(saved, actual, rel_tol=0, abs_tol=1e-5)
               for saved, actual in zip(row["ideal_arrival_position_km"], ideal, strict=True)):
            raise ReplayMismatch("DE440s ideal arrival vector differs")
        gaps.append(gap)
        angles.append(angle)
    return {
        "status": "verified-snapshot-geometry-only",
        "case_count": 2, "departure_jd_tdb": dates,
        "arrival_position_gap_km": gaps, "opposition_angle_gap_deg": angles,
        "source_kernel_sha256": snapshot["source"]["sha256"],
        "snapshot_sha256": _digest(SNAPSHOT),
        "mission_claim_status": "unverified",
        "dynamic_kernel_recomputed": False,
    }


def _policy(snapshot_path: Path) -> Policy:
    return Policy(
        policy_id="offline-t1-de440s-snapshot-v1", network="disabled",
        max_seconds=60, max_tool_calls=1,
        allowed_paths=[str(path.resolve()) for path in (*SOURCE_PATHS, snapshot_path)],
        allowed_providers=[PROVIDER_ID],
    )


def _tool() -> Tool:
    return Tool(tool_id=TOOL_ID, name="Offline DE440s state-vector geometry checker",
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
            raise ReplayMismatch("DE440s tool input or source inventory changed")
        if snapshot_path.read_bytes() != SNAPSHOT.read_bytes():
            raise ReplayMismatch("DE440s Run snapshot differs from pinned source")
        return recompute_geometry(json.loads(snapshot_path.read_text(encoding="utf-8")))

    registry.register(_tool(), handler, argument_schema=json.loads(SCHEMA.read_text(encoding="utf-8")))
    receipt = registry.invoke(TOOL_ID, arguments,
                              path_refs=[str(path) for path in (*SOURCE_PATHS, snapshot_path)],
                              provider_id=PROVIDER_ID)
    if registry.calls_used != 1 or receipt["mission_claim_status"] != "unverified":
        raise ReplayMismatch("DE440s Tool/Policy result is outside its declared scope")
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
        raise ReplayMismatch("DE440s policy denial controls failed")
    return checks


def _make_run(payload: dict[str, Any], receipt: dict[str, Any], calls_used: int,
              run_dir: Path) -> Run:
    snapshot_path = run_dir / "ephemeris-snapshot.json"
    bindings = BoundPaths(root=ROOT, run_dir=run_dir)
    input_hash = canonical_hash(payload)
    run_id = f"run-t1-de440s-{input_hash[:16]}"
    evidence_specs = [
        ("ev-t1-de440s-states", EvidenceKind.DATA, snapshot_path, ["fixed-date-ephemeris-geometry"]),
        ("ev-t1-de440s-source-audit", EvidenceKind.SNAPSHOT, SOURCE_AUDIT, ["source-and-rights-audit"]),
        ("ev-t1-de440s-tool", EvidenceKind.CODE, Path(__file__).resolve(), ["offline-replay-code"]),
        ("ev-t1-de440s-method", EvidenceKind.SNAPSHOT, METHOD, ["scope-and-boundaries"]),
    ]
    evidence = [Evidence(
        evidence_id=identity, kind=kind, path_or_uri=bindings.ref(path),
        sha256=_digest(path), source_revision=installation_revision(),
        provenance_status=ProvenanceStatus.UNVERIFIED, allowed_use=allowed_use,
        notes="NAIF source-tracked model states; no spacecraft or Mars-center validation.",
    ) for identity, kind, path, allowed_use in evidence_specs]
    policy = _policy(snapshot_path).model_copy(update={
        "allowed_paths": [bindings.ref(path) for path in (*SOURCE_PATHS, snapshot_path)],
    })
    started = datetime(2026, 9, 27, tzinfo=timezone.utc)
    events: list[Event] = []
    previous = "genesis"
    for seq, (kind, body) in enumerate([
        ("run.initialized", {"run_id": run_id, "input_hash": input_hash}),
        ("policy.applied", {"policy_id": policy.policy_id, "network": "disabled"}),
        ("tool.invoked", {"tool_id": TOOL_ID, "calls_used": calls_used}),
        ("evaluator.completed", {"evaluator_id": EVALUATOR_ID, "result": receipt}),
        ("run.completed", {"status": RunStatus.COMPLETED.value}),
    ]):
        digest = canonical_hash(body)
        events.append(Event(event_id=f"t1-de440s-event-{seq}", seq=seq,
                            event_type=kind, occurred_at=started + timedelta(seconds=seq),
                            payload_hash=digest, prev_event_hash=previous, payload=body))
        previous = digest
    trace = Trace(trace_id=f"trace-{run_id}", run_id=run_id, input_hash=input_hash,
                  entries=[{"seq": item.seq, "event_type": item.event_type,
                            "payload_hash": item.payload_hash} for item in events])
    return Run(
        run_id=run_id, task_id="t1-de440s-fixed-date-geometry-v1",
        created_at=started, input_hash=input_hash, code_revision=installation_revision(),
        environment={**capture_environment(["auditable-scientist-lab", "pydantic", "sympy", "jsonschema"]),
                     "mode": "offline", "track_id": "T1", "runtime": "de440s-snapshot-geometry",
                     "network": "disabled", "provider_id": PROVIDER_ID},
        seed=17, evidence_refs=[item.evidence_id for item in evidence], status=RunStatus.COMPLETED,
        agent=Agent(agent_id="offline-t1-de440s-agent-v1", name="Offline T1 DE440s geometry agent",
                    version="1", capabilities=["invoke-registered-geometry-checker"]),
        tools=[_tool()],
        memories=[Memory(memory_id="evidence-policy-memory-v1", source_ref=bindings.ref(MEMORY_SOURCE),
                         scope="claim-level evidence boundaries", version="local-snapshot",
                         content_hash=_digest(MEMORY_SOURCE))],
        evaluators=[Evaluator(evaluator_id=EVALUATOR_ID, name="DE440s snapshot geometry checker",
                              version="1", read_only=True)],
        providers=[Provider(provider_id=PROVIDER_ID, kind="deterministic-domain-evaluator",
                            name="Offline state-vector geometry", version="1",
                            source_ref="scripts/verify_t1_de440s_run.py")],
        policy=policy, events=events, traces=[trace],
        claims=[Claim(text="The ideal transfer reaches Mars in a validated spacecraft encounter.",
                      status=ClaimStatus.UNVERIFIED, level=EvidenceLevel.DEMO,
                      evidence_refs=[item.evidence_id for item in evidence],
                      falsification_checks=["fixed-date-state-geometry", "source-hash",
                                             "snapshot-mutation", "independent-mission-comparison"],
                      holdout_verified=False)],
        observations=[Observation(observation_id="obs-t1-de440s-fixed-dates",
                                  dataset_hash=_digest(snapshot_path), split="external",
                                  summary={"case_count": 2, "evidence_level": "real-data",
                                           "scope": "ephemeris-model-geometry-only"},
                                  units={"position": "km", "velocity": "km/s", "time": "JD TDB"},
                                  source_ref=bindings.ref(snapshot_path))],
        evidence=evidence,
    )


def _report(run: Run, receipt: dict[str, Any]) -> str:
    return ("# T1 DE440s fixed-date geometry Run\n\n"
            f"- Run: `{run.run_id}`\n"
            f"- Snapshot cases: `{receipt['case_count']}`\n"
            f"- Arrival position gaps (km): `{receipt['arrival_position_gap_km']}`\n"
            f"- Mission Claim: `{run.claims[0].status.value}`\n"
            f"- Result hash: `{canonical_hash(receipt)}`\n\n"
            "Replay recomputes geometry from saved Mars-barycenter states, not from the NAIF kernel. "
            "It does not validate a spacecraft trajectory, Mars-center encounter, or scientific holdout.\n")


def write_run() -> Path:
    payload = input_payload()
    run_dir = RUNS / f"run-t1-de440s-{canonical_hash(payload)[:16]}"
    if run_dir.exists():
        raise FileExistsError(f"refusing to overwrite existing DE440s Run: {run_dir}")
    run_dir.mkdir(parents=True)
    snapshot_path = run_dir / "ephemeris-snapshot.json"
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
        raise ReplayMismatch("DE440s Run requires a portable manifest")
    payload = input_payload()
    if (json.loads((run_dir / "input.json").read_text(encoding="utf-8")) != payload
            or run_dir.name != f"run-t1-de440s-{canonical_hash(payload)[:16]}"):
        raise ReplayMismatch("saved DE440s Run input or identity changed")
    snapshot_path = run_dir / "ephemeris-snapshot.json"
    receipt, calls_used = execute(payload, snapshot_path)
    if json.loads((run_dir / "result.json").read_text(encoding="utf-8")) != {
            "provider_id": PROVIDER_ID, "receipt": receipt}:
        raise ReplayMismatch("saved DE440s Run output changed")
    run = verify_run_record(run_dir / "run.json", run_dir / "events.jsonl",
                            root=ROOT, bindings=bindings)
    expected = _make_run(payload, receipt, calls_used, run_dir)
    if canonical_hash(run) != canonical_hash(expected):
        raise ReplayMismatch("saved DE440s shared-kernel Run changed")
    result = manifest.verify(input_payload=payload, code_revision=expected.code_revision,
                             environment=expected.environment, seed=expected.seed,
                             source_paths=SOURCE_PATHS, evidence_paths=[snapshot_path],
                             candidate_order=[], computational_output=receipt,
                             bindings=bindings).model_dump(mode="json")
    if (run_dir / "report.md").read_text(encoding="utf-8") != _report(run, receipt):
        raise ReplayMismatch("saved DE440s Run report changed")
    return result


def verify_run_and_mutations(run_dir: Path) -> dict[str, Any]:
    original = replay_run(run_dir)
    with tempfile.TemporaryDirectory(prefix="scientist-de440s-replay-") as temporary:
        relocated = Path(temporary).resolve() / run_dir.name
        shutil.copytree(run_dir, relocated)
        if replay_run(relocated) != original:
            raise ReplayMismatch("relocated DE440s Run differs")
        output = relocated / "result.json"
        saved = output.read_bytes()
        changed = json.loads(saved)
        changed["receipt"]["arrival_position_gap_km"][0] += 1
        _write_json(output, changed)
        try:
            replay_run(relocated)
        except ReplayMismatch:
            result_tamper_rejected = True
        else:
            result_tamper_rejected = False
        output.write_bytes(saved)
        snapshot = relocated / "ephemeris-snapshot.json"
        snapshot.write_bytes(snapshot.read_bytes() + b"\nchanged\n")
        try:
            replay_run(relocated)
        except ReplayMismatch:
            snapshot_tamper_rejected = True
        else:
            snapshot_tamper_rejected = False
    if not result_tamper_rejected or not snapshot_tamper_rejected:
        raise ReplayMismatch("DE440s mutation controls failed")
    return {
        "schema_version": "t1-de440s-run-audit-v1",
        "status": "verified-offline-snapshot-geometry-run-only",
        "run_path": run_dir.relative_to(ROOT).as_posix(),
        "run_id": run_dir.name, "replay": original,
        "relocated_replay_equal": True,
        "result_tamper_rejected": result_tamper_rejected,
        "snapshot_tamper_rejected": snapshot_tamper_rejected,
        "policy_denials": policy_denials(input_payload(), run_dir / "ephemeris-snapshot.json"),
        "boundaries": {"real_ephemeris_source_tracked": True,
                       "dynamic_kernel_recomputed_in_replay": False,
                       "mars_center_encounter_validated": False,
                       "spacecraft_trajectory_validated": False,
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
        run_dir = RUNS / f"run-t1-de440s-{canonical_hash(input_payload())[:16]}"
        result = verify_run_and_mutations(run_dir)
        saved = json.loads(AUDIT.read_text(encoding="utf-8"))
        recorded_at = saved.pop("recorded_at", None)
        if not recorded_at or datetime.fromisoformat(recorded_at).tzinfo is None or saved != result:
            raise ReplayMismatch("DE440s Run audit differs from current replay")
    print(json.dumps({"status": result["status"], "run_id": result["run_id"],
                      "replay": result["replay"],
                      "mutation_controls": [result["result_tamper_rejected"],
                                            result["snapshot_tamper_rejected"]]},
                     sort_keys=True))


if __name__ == "__main__":
    main()
