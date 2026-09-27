"""Build a deterministic shared-kernel Run for a bounded track evaluator."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from ..domain import (
    Agent,
    Claim,
    ClaimStatus,
    Evidence,
    EvidenceKind,
    EvidenceLevel,
    Evaluator,
    Event,
    Memory,
    Observation,
    Provider,
    ProvenanceStatus,
    Run,
    RunStatus,
    Trace,
)
from ..runtime.canonical import canonical_hash
from ..runtime.environment import capture_environment
from ..runtime.paths import installation_revision, resource_path
from ..runtime.replay import BoundPaths, fingerprint_file
from .common import TrackReceipt
from .runner import track_policy, track_tool


def make_track_run(
    *,
    track_id: str,
    task_id: str,
    receipt: TrackReceipt,
    fixture_path: Path,
    negative_case: Any,
    seed: int = 17,
    calls_used: int = 0,
    bindings: BoundPaths | None = None,
) -> Run:
    if calls_used not in (0, 1):
        raise ValueError("bounded track Run requires zero or one registered tool call")
    fixture = fingerprint_file(fixture_path)
    ref = (bindings.ref if bindings is not None else lambda path: str(path))
    evaluator_source = Path(__file__).with_name({"T2": "causal.py", "T3": "dynamics.py", "T3N": "nbody.py", "T4": "proof.py", "T5": "protocol.py"}[track_id])
    evaluator_fingerprint = fingerprint_file(evaluator_source)
    evidence_id = f"ev-{track_id.lower()}-fixture"
    evidence = Evidence(
        evidence_id=evidence_id,
        kind=EvidenceKind.DATA,
        path_or_uri=ref(fixture_path),
        sha256=fixture.sha256,
        source_revision=installation_revision(),
        provenance_status=ProvenanceStatus.UNVERIFIED,
        allowed_use=["offline-fixture", "bounded-evaluator"],
        notes="Fixture evidence is not real-data or publication evidence.",
    )
    evaluator_evidence_id = f"ev-{track_id.lower()}-evaluator-code"
    evaluator_evidence = Evidence(
        evidence_id=evaluator_evidence_id,
        kind=EvidenceKind.CODE,
        path_or_uri=ref(evaluator_source),
        sha256=evaluator_fingerprint.sha256,
        source_revision=installation_revision(),
        provenance_status=ProvenanceStatus.UNVERIFIED,
        allowed_use=["offline-evaluator", "source-provenance"],
        notes="Local evaluator source fingerprint; this does not establish external scientific validity.",
    )
    code_evidence = [evaluator_evidence]
    if track_id == "T3":
        reference_source = Path(__file__).with_name("reference_rk4.py")
        code_evidence.append(Evidence(
            evidence_id="ev-t3-rk4-reference-code",
            kind=EvidenceKind.CODE,
            path_or_uri=ref(reference_source),
            sha256=fingerprint_file(reference_source).sha256,
            source_revision=installation_revision(),
            provenance_status=ProvenanceStatus.UNVERIFIED,
            allowed_use=["offline-evaluator", "source-provenance"],
            notes="Local independent numerical method; academic formula citation does not establish source rights or real-world validation.",
        ))
    if track_id == "T3N":
        reference_source = Path(__file__).with_name("reference_nbody_rk4.py")
        code_evidence.append(Evidence(
            evidence_id="ev-t3n-rk4-reference-code",
            kind=EvidenceKind.CODE,
            path_or_uri=ref(reference_source),
            sha256=fingerprint_file(reference_source).sha256,
            source_revision=installation_revision(),
            provenance_status=ProvenanceStatus.UNVERIFIED,
            allowed_use=["offline-evaluator", "source-provenance"],
            notes="Independent local RK4 reference for the symmetric fixture only.",
        ))
    provider_id = f"internal-{track_id.lower()}-evaluator"
    policy = track_policy(track_id, fixture_path)
    input_hash = receipt.input_hash
    run_id = f"run-{track_id.lower()}-{input_hash[:16]}"
    agent = Agent(
        agent_id=f"offline-{track_id.lower()}-agent-v1",
        name=f"Offline {track_id} evaluator agent",
        version="1",
        capabilities=["invoke-registered-evaluator", "record-negative-case"],
    )
    tool = track_tool(track_id)
    memory_source = resource_path("docs/EVIDENCE_POLICY.md")
    memory = Memory(
        memory_id="evidence-policy-memory-v1",
        source_ref=ref(memory_source),
        scope="claim-level evidence boundaries",
        version="local-snapshot",
        content_hash=fingerprint_file(memory_source).sha256,
    )
    evaluator = Evaluator(evaluator_id=receipt.evaluator_id, name=f"{track_id} independent evaluator", version="1", read_only=True)
    provider = Provider(
        provider_id=provider_id,
        kind="deterministic-domain-evaluator",
        name=f"Internal {track_id} evaluator",
        version="1",
        source_ref="src/auditable_scientist/tracks",
    )
    claim = Claim(
        text=f"The {track_id} evaluator passed its bounded fixture gate; this is not a real-world scientific claim.",
        status=ClaimStatus.UNVERIFIED,
        level=EvidenceLevel.VALIDATED_REPRODUCTION if receipt.passed else EvidenceLevel.DEMO,
        evidence_refs=[evidence_id, *[item.evidence_id for item in code_evidence]],
        falsification_checks=["positive-evaluator-replay", "negative-case-rejection", "fixture-hash", *(["rk4-backend-agreement"] if track_id in ("T3", "T3N") else [])],
        holdout_verified=False,
    )
    observation = Observation(
        observation_id=f"obs-{track_id.lower()}-fixture",
        dataset_hash=receipt.input_hash,
        split="external",
        summary={"track_id": track_id, "evaluator_id": receipt.evaluator_id, "evidence_level": receipt.evidence_level},
        units={},
        source_ref=ref(fixture_path),
    )
    environment = {
        **capture_environment(["auditable-scientist-lab", "pydantic", "sympy", "jsonschema"]),
        "mode": "offline",
        "track_id": track_id,
        "runtime": "bounded-evaluator",
        "network": "disabled",
    }
    base_time = datetime(2026, 9, 21, tzinfo=timezone.utc)
    payloads = [
        ("run.initialized", {"run_id": run_id, "input_hash": input_hash}),
        ("policy.applied", {"policy_id": policy.policy_id, "network": policy.network, "provider_id": provider_id}),
        *([("tool.invoked", {"tool_id": tool.tool_id, "calls_used": calls_used})] if calls_used else []),
        ("evaluator.completed", {"evaluator_id": receipt.evaluator_id, "result": receipt.result}),
        ("negative_case.checked", {"negative_case": negative_case, "negative_case_passed": receipt.negative_case_passed}),
        ("run.completed", {"status": "completed" if receipt.passed else "unverified"}),
    ]
    events: list[Event] = []
    previous = "genesis"
    for seq, (event_type, payload) in enumerate(payloads):
        payload_hash = canonical_hash(payload)
        events.append(
            Event(
                event_id=f"{track_id.lower()}-event-{seq}",
                seq=seq,
                event_type=event_type,
                occurred_at=base_time + timedelta(seconds=seq),
                payload_hash=payload_hash,
                prev_event_hash=previous,
                payload=payload,
            )
        )
        previous = payload_hash
    trace = Trace(
        trace_id=f"trace-{run_id}",
        run_id=run_id,
        input_hash=input_hash,
        entries=[{"seq": event.seq, "event_type": event.event_type, "payload_hash": event.payload_hash} for event in events],
    )
    return Run(
        run_id=run_id,
        task_id=task_id,
        created_at=base_time,
        input_hash=input_hash,
        code_revision=installation_revision(),
        environment=environment,
        seed=seed,
        evidence_refs=[evidence_id, *[item.evidence_id for item in code_evidence]],
        status=RunStatus.COMPLETED if receipt.passed else RunStatus.UNVERIFIED,
        agent=agent,
        tools=[tool],
        memories=[memory],
        evaluators=[evaluator],
        providers=[provider],
        policy=policy.model_copy(update={"allowed_paths": [ref(fixture_path)]}) if bindings is not None else policy,
        events=events,
        traces=[trace],
        claims=[claim],
        observations=[observation],
        evidence=[evidence, *code_evidence],
    )
