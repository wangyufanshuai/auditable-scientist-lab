"""Runtime primitives for append-only logs and deterministic replay."""

from .canonical import canonical_bytes, canonical_hash, canonical_json
from .environment import capture_environment
from .event_log import EventLog, EventLogError
from .replay import ReplayManifest, ReplayMismatch, ReplayReceipt

__all__ = [
    "EventLog",
    "EventLogError",
    "ReplayManifest",
    "ReplayMismatch",
    "ReplayReceipt",
    "canonical_bytes",
    "canonical_hash",
    "canonical_json",
    "capture_environment",
]
