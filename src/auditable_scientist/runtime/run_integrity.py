"""Verify that a saved Run, its JSONL log, and its trace describe one execution."""

from __future__ import annotations

import json
from pathlib import Path

from ..domain import Run
from .canonical import canonical_hash
from .event_log import EventLog
from .replay import BoundPaths, ReplayMismatch, fingerprint_file


def verify_run_record(run_path: str | Path, event_log_path: str | Path, *, root: Path | None = None, bindings: BoundPaths | None = None) -> Run:
    run_file = Path(run_path)
    payload = json.loads(run_file.read_text(encoding="utf-8"))
    run = Run.model_validate(payload)
    events = EventLog(event_log_path).verify()
    if canonical_hash([event.model_dump(mode="json") for event in events]) != canonical_hash(payload["events"]):
        raise ReplayMismatch("saved Run events differ from append-only event log")
    expected_trace = [
        {"seq": event.seq, "event_type": event.event_type, "payload_hash": event.payload_hash}
        for event in events
    ]
    if len(run.traces) != 1 or canonical_hash(run.traces[0].entries) != canonical_hash(expected_trace):
        raise ReplayMismatch("Run trace differs from append-only event log")
    if not events or events[0].event_type != "run.initialized" or events[-1].event_type != "run.completed":
        raise ReplayMismatch("Run event lifecycle is incomplete")
    if events[0].payload != {"run_id": run.run_id, "input_hash": run.input_hash}:
        raise ReplayMismatch("Run initialization event differs from Run identity")
    if events[-1].payload.get("status") != run.status.value:
        raise ReplayMismatch("Run completion event differs from Run status")
    base = root or run_file.resolve().parents[2]
    for evidence in run.evidence:
        if bindings is not None:
            path = bindings.resolve(evidence.path_or_uri)
        else:
            path = Path(evidence.path_or_uri)
            if not path.is_absolute():
                path = base / path
        if fingerprint_file(path).sha256 != evidence.sha256:
            raise ReplayMismatch(f"Run evidence changed: {evidence.evidence_id}")
    return run
