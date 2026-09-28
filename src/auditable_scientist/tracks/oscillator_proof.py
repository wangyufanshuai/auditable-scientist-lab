"""T4O: bounded proof-carrying receipt for the T3 harmonic oscillator."""

from __future__ import annotations

from collections import Counter
from hashlib import sha256
from math import isfinite
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ..runtime.canonical import canonical_hash
from ..tools.dimensions import check_expression_dimensions, parse_unit
from .dynamics import DynamicsCase, _verlet
from .reference_rk4 import rk4_oscillator


CHECKER_STATEMENTS = {
    "input-hash": "declared initial conditions and seed match the input hash",
    "output-hash": "claimed numerical output matches the output hash",
    "source-hash": "the executed T3 solver source matches its declared hash",
    "units": "declared units satisfy the oscillator acceleration and energy equations",
    "initial-boundary": "reported initial state matches the declared initial state",
    "solver-replay": "claimed output agrees with replayed velocity-Verlet",
    "analytic-reference": "replayed position agrees with the harmonic closed form",
    "rk4-reference": "replayed position agrees with independent fixed-step RK4",
    "energy-drift": "replayed maximum specific-energy drift is bounded",
    "formal-prover": "an external formal proof of the solver is available",
}
REQUIRED_CHECKERS = frozenset(CHECKER_STATEMENTS) - {"formal-prover"}
UNIT_FIELDS = frozenset({"position", "velocity", "time", "frequency", "specific_energy"})
EXPECTED_UNITS = {
    "position": "m", "velocity": "m/s", "time": "s",
    "frequency": "s^-1", "specific_energy": "m^2/s^2",
}
MAX_POSITION_ERROR = 2e-3
MAX_REFERENCE_DELTA = 2e-3
MAX_ENERGY_DRIFT = 2e-3


class OscillatorOutput(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    initial_x: float
    initial_v: float
    final_x: float
    max_specific_energy_drift: float = Field(ge=0)


class OscillatorObligation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    obligation_id: str = Field(min_length=1)
    checker_id: Literal[
        "input-hash", "output-hash", "source-hash", "units", "initial-boundary",
        "solver-replay", "analytic-reference", "rk4-reference", "energy-drift",
        "formal-prover",
    ]
    statement: str = Field(min_length=1)


class OscillatorProofPackage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    package_id: str = Field(min_length=1)
    solver_id: Literal["velocity-verlet-v1"]
    case: DynamicsCase
    seed: int = Field(ge=0)
    units: dict[str, str]
    output: OscillatorOutput
    input_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    output_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    source_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    obligations: list[OscillatorObligation] = Field(min_length=1)
    claim_status: Literal["blocked"] = "blocked"

    @model_validator(mode="after")
    def finite_case(self) -> "OscillatorProofPackage":
        if not all(isfinite(value) for value in (
            self.case.omega, self.case.dt, self.case.x0, self.case.v0,
        )):
            raise ValueError("oscillator case contains a nonfinite number")
        if not (0 < self.case.omega <= 2 and 0 < self.case.dt <= 0.02
                and 1 <= self.case.steps <= 1000 and abs(self.case.x0) <= 2
                and abs(self.case.v0) <= 2):
            raise ValueError("oscillator case is outside the declared finite grid")
        return self


class CheckerResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    checker_id: str
    status: Literal["passed", "failed", "inconclusive", "not_applicable"]
    detail: str


class OscillatorVerification(BaseModel):
    model_config = ConfigDict(extra="forbid")

    evaluator_id: str = "proof-carrying-oscillator-v1"
    solver_id: str = "velocity-verlet-v1"
    reference_solver_id: str = "fixed-step-rk4-v1"
    results: list[CheckerResult]
    passed: bool
    claim_status: Literal["bounded-verified", "blocked"]
    evidence_level: Literal["demo", "validated-reproduction"]
    max_position_error: float
    max_reference_delta: float
    max_specific_energy_drift: float


def _solver_source_hash() -> str:
    return sha256(Path(__file__).with_name("dynamics.py").read_bytes()).hexdigest()


def _input_payload(case: DynamicsCase, seed: int) -> dict:
    return {"case": case.model_dump(mode="json"), "seed": seed, "solver_id": "velocity-verlet-v1"}


def create_oscillator_package(case: DynamicsCase, *, seed: int = 17) -> OscillatorProofPackage:
    """Emit a claim that still requires an independent checker run."""
    if seed < 0 or not all(isfinite(value) for value in (case.omega, case.dt, case.x0, case.v0)):
        raise ValueError("invalid oscillator input")
    if not (0 < case.omega <= 2 and 0 < case.dt <= 0.02 and 1 <= case.steps <= 1000
            and abs(case.x0) <= 2 and abs(case.v0) <= 2):
        raise ValueError("oscillator case is outside the declared finite grid")
    final_x, _, drift = _verlet(case)
    output = OscillatorOutput(initial_x=case.x0, initial_v=case.v0, final_x=final_x, max_specific_energy_drift=drift)
    return OscillatorProofPackage(
        package_id=f"oscillator-{case.case_id}", solver_id="velocity-verlet-v1",
        case=case, seed=seed, units=EXPECTED_UNITS.copy(), output=output,
        input_hash=canonical_hash(_input_payload(case, seed)),
        output_hash=canonical_hash(output.model_dump(mode="json")),
        source_sha256=_solver_source_hash(),
        obligations=[
            OscillatorObligation(obligation_id=f"o{index}", checker_id=checker,
                                 statement=CHECKER_STATEMENTS[checker])
            for index, checker in enumerate(CHECKER_STATEMENTS, start=1)
        ],
    )


def _units_valid(units: dict[str, str]) -> bool:
    if set(units) != UNIT_FIELDS or units != EXPECTED_UNITS:
        return False
    try:
        if any(parse_unit(units[key]) != parse_unit(expected) for key, expected in EXPECTED_UNITS.items()):
            return False
        variable_units = {"x0": units["position"], "v0": units["velocity"], "omega": units["frequency"]}
        acceleration = check_expression_dimensions("omega**2*x0", variable_units, "m/s^2")
        energy = check_expression_dimensions("v0**2+omega**2*x0**2", variable_units, "m^2/s^2")
        return acceleration.status == "valid" and energy.status == "valid"
    except ValueError:
        return False


def verify_oscillator_package(package: OscillatorProofPackage) -> OscillatorVerification:
    """Recompute the finite trajectory; do not trust the package's claim or hashes alone."""
    case = package.case
    final_x, exact_x, drift = _verlet(case)
    rk4_x, _, _ = rk4_oscillator(case.x0, case.v0, case.omega, case.dt, case.steps)
    position_error = abs(final_x - exact_x)
    reference_delta = abs(final_x - rk4_x)
    checks = {
        "input-hash": package.input_hash == canonical_hash(_input_payload(case, package.seed)),
        "output-hash": package.output_hash == canonical_hash(package.output.model_dump(mode="json")),
        "source-hash": package.source_sha256 == _solver_source_hash(),
        "units": _units_valid(package.units),
        "initial-boundary": package.output.initial_x == case.x0 and package.output.initial_v == case.v0,
        "solver-replay": abs(package.output.final_x - final_x) <= 1e-12 and abs(package.output.max_specific_energy_drift - drift) <= 1e-12,
        "analytic-reference": position_error <= MAX_POSITION_ERROR,
        "rk4-reference": reference_delta <= MAX_REFERENCE_DELTA,
        "energy-drift": drift <= MAX_ENERGY_DRIFT,
    }
    counts = Counter(item.checker_id for item in package.obligations)
    identifiers = Counter(item.obligation_id for item in package.obligations)
    results = []
    for checker in sorted(REQUIRED_CHECKERS):
        matches = [item for item in package.obligations if item.checker_id == checker]
        if not matches:
            results.append(CheckerResult(checker_id=checker, status="inconclusive", detail="required obligation missing"))
        elif counts[checker] != 1 or identifiers[matches[0].obligation_id] != 1 or matches[0].statement != CHECKER_STATEMENTS[checker]:
            results.append(CheckerResult(checker_id=checker, status="failed", detail="duplicate or mislabeled obligation"))
        else:
            results.append(CheckerResult(checker_id=checker, status="passed" if checks[checker] else "failed", detail="independently recomputed check"))
    formal = [item for item in package.obligations if item.checker_id == "formal-prover"]
    if len(formal) > 1 or (formal and (identifiers[formal[0].obligation_id] != 1 or formal[0].statement != CHECKER_STATEMENTS["formal-prover"])):
        results.append(CheckerResult(checker_id="formal-prover", status="failed", detail="duplicate or mislabeled optional obligation"))
    else:
        results.append(CheckerResult(checker_id="formal-prover", status="not_applicable", detail="no external formal backend configured; no formal proof claim"))
    passed = all(item.status == "passed" for item in results if item.checker_id in REQUIRED_CHECKERS) and not any(item.status == "failed" for item in results)
    return OscillatorVerification(
        results=results, passed=passed, claim_status="bounded-verified" if passed else "blocked",
        evidence_level="validated-reproduction" if passed else "demo",
        max_position_error=position_error, max_reference_delta=reference_delta,
        max_specific_energy_drift=drift,
    )
