"""T5: safe bio-chem protocol constraint verification without wet-lab execution."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ProtocolStep(BaseModel):
    model_config = ConfigDict(extra="forbid")

    step_id: str = Field(min_length=1)
    action: str = Field(min_length=1)
    reagent: str = Field(min_length=1)
    volume_ul: float = Field(gt=0)
    temperature_c: float
    duration_min: float = Field(gt=0)
    provenance_status: Literal["verified", "unverified", "blocked"]


class ProtocolSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    protocol_id: str = Field(min_length=1)
    steps: list[ProtocolStep] = Field(min_length=1)
    min_temperature_c: float
    max_temperature_c: float
    max_total_volume_ul: float = Field(gt=0)
    require_verified_provenance: bool = True


class ProtocolVerification(BaseModel):
    model_config = ConfigDict(extra="forbid")

    evaluator_id: str = "bio-chem-protocol-v1"
    passed: bool
    failures: list[str]
    execution_allowed: bool = False
    evidence_level: Literal["demo", "validated-reproduction"]
    notes: list[str]


def verify_protocol(protocol: ProtocolSpec) -> ProtocolVerification:
    failures: list[str] = []
    expected_ids = [f"step-{index + 1}" for index in range(len(protocol.steps))]
    actual_ids = [item.step_id for item in protocol.steps]
    if actual_ids != expected_ids:
        failures.append("step-order")
    if protocol.min_temperature_c > protocol.max_temperature_c:
        failures.append("temperature-range-definition")
    total_volume = sum(item.volume_ul for item in protocol.steps)
    if total_volume > protocol.max_total_volume_ul:
        failures.append("total-volume")
    for item in protocol.steps:
        if not protocol.min_temperature_c <= item.temperature_c <= protocol.max_temperature_c:
            failures.append(f"temperature:{item.step_id}")
        if protocol.require_verified_provenance and item.provenance_status != "verified":
            failures.append(f"provenance:{item.step_id}")
    passed = not failures
    return ProtocolVerification(
        passed=passed,
        failures=failures,
        execution_allowed=False,
        evidence_level="validated-reproduction" if passed else "demo",
        notes=[
            "This evaluator checks declarative constraints only.",
            "It never schedules, controls, or authorizes wet-lab execution.",
        ],
    )
