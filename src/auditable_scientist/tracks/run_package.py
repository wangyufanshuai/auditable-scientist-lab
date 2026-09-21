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
    Policy,
    Provider,
    ProvenanceStatus,
    Run,
    RunStatus,
    Tool,
    Trace,
)
from ..runtime.canonical import canonical_hash
from ..runtime.replay import fingerprint_file
from .common import TrackReceipt


def make_track_run(
    *,
    track_id: str,
    task_id: str,
    receipt: TrackReceipt,
    fixture_path: Path,
    negative_case: Any,
    seed: int = 17,
) -> Run:
    fixture = fingerprint_file(fixture_path)
    evidence_id = f"ev-{track_id.lower()}-fixture"
    evidence = Evidence(
        evidence_id=evidence_id,
        kind=EvidenceKind.DATA,
        path_or_uri=str(fixture_path),
        sha256=fixture.sha256,
        source_revision="local-working-tree",
        provenance_status=ProvenanceStatus.UNVERIFIED,
        allowed_use=["offline-fixture", "bounded-evaluator"],
        notes="Fixture evidence is not real-data or publication evidence.",
    )
    provider_id = f"internal-{track_id.lower()}-evaluator"
    policy = Policy(
        policy_id=f"offline-{track_id.lower()}-v1",
        network="disabled",
        max_seconds=60,
        max_tool_calls=1,
        allowed_paths=[str(fixture_path.parent)],
        allowed_providers=[provider_id],
    )
    input_hash = receipt.input_hash
    run_id = f"run-{track_id.lower()}-{input_hash[:16]}"
    agent = Agent(
        agent_id=f"offline-{track_id.lower()}-agent-v1",
        name=f"Offline {track_id} evaluator agent",
        version="1",
        capabilities=["invoke-registered-evaluator", "record-negative-case"],
    )
    tool = Tool(
        tool_id=f"{track_id.lower()}-evaluator",
        name=f"{track_id} domain evaluator",
        version="1",
        parameter_schema_ref="schemas/track-receipt-v1.json",
        deterministic=True,
        network_required=False,
    )
    memory_source = Path(__file__).resolve().parents[3] / "docs/EVIDENCE_POLICY.md"
    memory = Memory(
        memory_id="evidence-policy-memory-v1",
        source_ref=str(memory_source),
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
        evidence_refs=[evidence_id],
        falsification_checks=["positive-evaluator-replay", "negative-case-rejection", "fixture-hash"],
        holdout_verified=False,
    )
    observation = Observation(
        observation_id=f"obs-{track_id.lower()}-fixture",
        dataset_hash=receipt.input_hash,
        split="external",
        summary={"track_id": track_id, "evaluator_id": receipt.evaluator_id, "evidence_level": receipt.evidence_level},
        units={},
        source_ref=str(fixture_path),
    )
    environment = {"mode": "offline", "track_id": track_id, "runtime": "bounded-evaluator"}
    base_time = datetime(2026, 9, 21, tzinfo=timezone.utc)
    payloads = [
        ("run.initialized", {"run_id": run_id, "input_hash": input_hash}),
        ("policy.applied", {"policy_id": policy.policy_id, "network": policy.network, "provider_id": provider_id}),
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
        code_revision="local-working-tree",
        environment=environment,
        seed=seed,
        evidence_refs=[evidence_id],
        status=RunStatus.COMPLETED if receipt.passed else RunStatus.UNVERIFIED,
        agent=agent,
        tools=[tool],
        memories=[memory],
        evaluators=[evaluator],
        providers=[provider],
        policy=policy,
        events=events,
        traces=[trace],
        claims=[claim],
        observations=[observation],
        evidence=[evidence],
    )
