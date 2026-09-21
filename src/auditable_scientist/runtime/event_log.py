"""Append-only JSONL event log with payload hash-chain verification."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..domain import Event
from .canonical import canonical_hash


class EventLogError(ValueError):
    """Raised when an event log is malformed or has been tampered with."""


class EventLog:
    def __init__(self, path: str | Path):
        self.path = Path(path)

    def append(
        self,
        event_type: str,
        payload: dict[str, Any],
        *,
        event_id: str | None = None,
        occurred_at: datetime | None = None,
    ) -> Event:
        existing = self.verify()
        previous_hash = existing[-1].payload_hash if existing else "genesis"
        event = Event(
            event_id=event_id or str(uuid.uuid4()),
            seq=len(existing),
            event_type=event_type,
            occurred_at=occurred_at or datetime.now(timezone.utc),
            payload_hash=canonical_hash(payload),
            prev_event_hash=previous_hash,
            payload=payload,
        )
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(canonical_json_line(event) + "\n")
        return event

    def read(self) -> list[Event]:
        if not self.path.exists():
            return []
        events: list[Event] = []
        for line_number, line in enumerate(self.path.read_text(encoding="utf-8").splitlines(), start=1):
            if not line.strip():
                raise EventLogError(f"blank line at event log line {line_number}")
            try:
                raw = json.loads(line)
                events.append(Event.model_validate(raw))
            except (json.JSONDecodeError, ValueError) as exc:
                raise EventLogError(f"invalid event at line {line_number}: {exc}") from exc
        return events

    def verify(self) -> list[Event]:
        events = self.read()
        previous = "genesis"
        for expected_seq, event in enumerate(events):
            if event.seq != expected_seq:
                raise EventLogError("event sequence is not contiguous")
            if event.prev_event_hash != previous:
                raise EventLogError("event previous hash does not match the chain")
            expected_payload_hash = canonical_hash(event.payload)
            if event.payload_hash != expected_payload_hash:
                raise EventLogError(f"payload hash mismatch for event {event.event_id}")
            previous = event.payload_hash
        return events


def canonical_json_line(event: Event) -> str:
    from .canonical import canonical_json

    return canonical_json(event)
