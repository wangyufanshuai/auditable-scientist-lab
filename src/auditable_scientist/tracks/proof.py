"""T4: machine-checkable proof obligations attached to a numeric trajectory."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from ..runtime.canonical import canonical_hash


class ProofState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    step: int = Field(ge=0)
    mass_a: float = Field(ge=0)
    mass_b: float = Field(ge=0)


class ProofObligation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    obligation_id: str = Field(min_length=1)
    checker_id: Literal["mass-conservation", "nonnegative-state", "trajectory-hash"]
    statement: str = Field(min_length=1)


class ProofPackage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    package_id: str = Field(min_length=1)
    trajectory: list[ProofState] = Field(min_length=1)
    obligations: list[ProofObligation] = Field(min_length=1)
    trajectory_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    claim_status: Literal["verified", "blocked"] = "blocked"


class ProofVerification(BaseModel):
    model_config = ConfigDict(extra="forbid")

    evaluator_id: str = "proof-carrying-simulation-v1"
    passed: bool
    checked_obligations: list[str]
    failed_obligations: list[str]
    claim_status: Literal["verified", "blocked"]
    evidence_level: Literal["demo", "validated-reproduction"]


def verify_proof_package(package: ProofPackage) -> ProofVerification:
    failed: list[str] = []
    checked: list[str] = []
    expected_hash = canonical_hash([item.model_dump(mode="json") for item in package.trajectory])
    for obligation in package.obligations:
        checked.append(obligation.obligation_id)
        passed = {
            "mass-conservation": len({round(item.mass_a + item.mass_b, 12) for item in package.trajectory}) == 1,
            "nonnegative-state": all(item.mass_a >= 0 and item.mass_b >= 0 for item in package.trajectory),
            "trajectory-hash": package.trajectory_hash == expected_hash,
        }[obligation.checker_id]
        if not passed:
            failed.append(obligation.obligation_id)
    passed = not failed
    return ProofVerification(
        passed=passed,
        checked_obligations=checked,
        failed_obligations=failed,
        claim_status="verified" if passed else "blocked",
        evidence_level="validated-reproduction" if passed else "demo",
    )
