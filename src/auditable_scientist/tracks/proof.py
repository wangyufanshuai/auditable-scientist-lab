"""T4: exact transfer witnesses and bounded symbolic proof obligations."""

from __future__ import annotations

from collections import Counter
from decimal import Decimal
from fractions import Fraction
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field
from sympy import expand, symbols

from ..runtime.canonical import canonical_hash


class ProofState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    step: int = Field(ge=0)
    mass_a: Decimal = Field(allow_inf_nan=False)
    mass_b: Decimal = Field(allow_inf_nan=False)


class ProofObligation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    obligation_id: str = Field(min_length=1)
    checker_id: Literal[
        "mass-conservation", "nonnegative-state", "trajectory-hash",
        "transition-rule", "symbolic-invariant",
    ]
    statement: str = Field(min_length=1)


class ProofPackage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    package_id: str = Field(min_length=1)
    rule_id: Literal["conservative-transfer-v1"]
    trajectory: list[ProofState] = Field(min_length=2)
    transfers: list[Decimal] = Field(min_length=1)
    obligations: list[ProofObligation] = Field(min_length=1)
    trajectory_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    claim_status: Literal["bounded-verified", "blocked"] = "blocked"


class ProofVerification(BaseModel):
    model_config = ConfigDict(extra="forbid")

    evaluator_id: str = "proof-carrying-simulation-v2"
    rule_id: str
    proof_method: str
    passed: bool
    checked_obligations: list[str]
    failed_obligations: list[str]
    claim_status: Literal["bounded-verified", "blocked"]
    evidence_level: Literal["demo", "validated-reproduction"]


REQUIRED_CHECKERS = frozenset({
    "mass-conservation", "nonnegative-state", "trajectory-hash",
    "transition-rule", "symbolic-invariant",
})
CHECKER_STATEMENTS = {
    "mass-conservation": "total mass is constant",
    "nonnegative-state": "masses are nonnegative",
    "trajectory-hash": "trajectory hash matches",
    "transition-rule": "each step follows the declared transfer witness",
    "symbolic-invariant": "the conservative transfer rule preserves total mass",
}


def _transfer_witnesses_match(package: ProofPackage) -> bool:
    if len(package.transfers) != len(package.trajectory) - 1:
        return False
    for previous, current, amount in zip(package.trajectory, package.trajectory[1:], package.transfers):
        if not all(value.is_finite() for value in (previous.mass_a, previous.mass_b, current.mass_a, current.mass_b, amount)):
            return False
        previous_a, previous_b = Fraction(previous.mass_a), Fraction(previous.mass_b)
        current_a, current_b, exact_amount = Fraction(current.mass_a), Fraction(current.mass_b), Fraction(amount)
        if (
            current.step != previous.step + 1
            or exact_amount < 0
            or exact_amount > previous_a
            or current_a != previous_a - exact_amount
            or current_b != previous_b + exact_amount
        ):
            return False
    return True


def verify_proof_package(package: ProofPackage) -> ProofVerification:
    """Verify a fixed conservative transfer rule; make no general proof claim."""

    failed: list[str] = []
    checked = [item.obligation_id for item in package.obligations]
    checkers = Counter(item.checker_id for item in package.obligations)
    identifiers = Counter(checked)
    for checker in sorted(REQUIRED_CHECKERS - checkers.keys()):
        failed.append(f"missing:{checker}")
    for checker, count in sorted(checkers.items()):
        if count != 1:
            failed.append(f"duplicate:{checker}")
    for identifier, count in sorted(identifiers.items()):
        if count != 1:
            failed.append(f"duplicate-id:{identifier}")
    if package.claim_status != "blocked":
        failed.append("predeclared-claim")
    for obligation in package.obligations:
        if obligation.statement != CHECKER_STATEMENTS[obligation.checker_id]:
            failed.append(f"statement:{obligation.obligation_id}")

    expected_hash = canonical_hash([item.model_dump(mode="json") for item in package.trajectory])
    exact_states = [(Fraction(item.mass_a), Fraction(item.mass_b)) for item in package.trajectory]
    initial_total = sum(exact_states[0])
    a, b, amount = symbols("a b amount", real=True)
    algebraic_identity = expand((a - amount) + (b + amount) - (a + b)) == 0
    results = {
        "mass-conservation": all(sum(state) == initial_total for state in exact_states),
        "nonnegative-state": all(a >= 0 and b >= 0 for a, b in exact_states),
        "trajectory-hash": package.trajectory_hash == expected_hash,
        "transition-rule": _transfer_witnesses_match(package),
        "symbolic-invariant": algebraic_identity,
    }
    for obligation in package.obligations:
        if not results[obligation.checker_id]:
            failed.append(obligation.obligation_id)
    passed = not failed
    return ProofVerification(
        rule_id=package.rule_id,
        proof_method="exact-rational-transfer-witness-plus-symbolic-conservation-identity",
        passed=passed,
        checked_obligations=checked,
        failed_obligations=failed,
        claim_status="bounded-verified" if passed else "blocked",
        evidence_level="validated-reproduction" if passed else "demo",
    )
