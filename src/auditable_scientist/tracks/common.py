"""Common receipt fields for independent track evaluators."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from ..runtime.canonical import canonical_hash


class TrackEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: str = Field(min_length=1)
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    bytes: int = Field(ge=0)
    provenance_status: Literal["verified", "unverified", "blocked"]
    allowed_use: list[str] = Field(min_length=1)


class TrackReceipt(BaseModel):
    model_config = ConfigDict(extra="forbid")

    track_id: str = Field(min_length=1)
    evaluator_id: str = Field(min_length=1)
    evidence_level: Literal["demo", "validated-reproduction", "real-data", "research-candidate"]
    input_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    passed: bool
    negative_case_passed: bool
    evidence_files: list[TrackEvidence] = Field(default_factory=list)
    source_files: list[TrackEvidence] = Field(default_factory=list)
    blocked_gates: list[str] = Field(default_factory=list)
    result: dict[str, Any]


def make_track_receipt(
    *,
    track_id: str,
    evaluator_id: str,
    input_payload: Any,
    evidence_level: str,
    passed: bool,
    negative_case_passed: bool,
    result: dict[str, Any],
    evidence_files: list[dict[str, Any]] | None = None,
    source_files: list[dict[str, Any]] | None = None,
    blocked_gates: list[str] | None = None,
) -> TrackReceipt:
    return TrackReceipt(
        track_id=track_id,
        evaluator_id=evaluator_id,
        evidence_level=evidence_level,
        input_hash=canonical_hash(input_payload),
        passed=passed,
        negative_case_passed=negative_case_passed,
        evidence_files=list(evidence_files or []),
        source_files=list(source_files or []),
        blocked_gates=list(blocked_gates or []),
        result=result,
    )
