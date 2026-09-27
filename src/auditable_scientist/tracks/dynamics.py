"""T3: replayable harmonic dynamics with conservation and negative-solver gates."""

from __future__ import annotations

from math import cos, sin
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from .common import TrackReceipt, make_track_receipt
from .reference_rk4 import rk4_oscillator


class DynamicsCase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    case_id: str = Field(min_length=1)
    split: Literal["train", "holdout"]
    omega: float = Field(gt=0)
    dt: float = Field(gt=0)
    steps: int = Field(gt=0)
    x0: float
    v0: float


class DynamicsEvaluation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    evaluator_id: str = "harmonic-dynamics-v2"
    solver_id: str = "velocity-verlet-v1"
    reference_solver_id: str = "fixed-step-rk4-v1"
    train_max_position_error: float = Field(ge=0)
    holdout_max_position_error: float = Field(ge=0)
    max_energy_drift: float = Field(ge=0)
    max_reference_position_error: float = Field(ge=0)
    max_reference_energy_drift: float = Field(ge=0)
    max_backend_position_delta: float = Field(ge=0)
    backend_agreement_passed: bool
    negative_euler_rejected: bool
    passed: bool
    notes: list[str]


def _energy(x: float, v: float, omega: float) -> float:
    return 0.5 * (v * v + (omega * x) ** 2)


def _verlet(case: DynamicsCase) -> tuple[float, float, float]:
    x, v = case.x0, case.v0
    initial_energy = _energy(x, v, case.omega)
    max_drift = 0.0
    for _ in range(case.steps):
        acceleration = -(case.omega**2) * x
        x_next = x + v * case.dt + 0.5 * acceleration * case.dt**2
        acceleration_next = -(case.omega**2) * x_next
        v = v + 0.5 * (acceleration + acceleration_next) * case.dt
        x = x_next
        max_drift = max(max_drift, abs(_energy(x, v, case.omega) - initial_energy))
    exact_x = case.x0 * cos(case.omega * case.dt * case.steps) + (case.v0 / case.omega) * sin(case.omega * case.dt * case.steps)
    return x, exact_x, max_drift


def _euler(case: DynamicsCase) -> tuple[float, float]:
    x, v = case.x0, case.v0
    for _ in range(case.steps):
        x, v = x + v * case.dt, v - (case.omega**2) * x * case.dt
    return x, _energy(x, v, case.omega)


def evaluate_dynamics_fixture(
    cases: list[DynamicsCase], *, max_holdout_error: float = 2e-3,
    max_energy_drift: float = 2e-3, max_backend_delta: float = 2e-3,
    max_reference_error: float = 1e-5,
) -> tuple[DynamicsEvaluation, TrackReceipt]:
    train = [item for item in cases if item.split == "train"]
    holdout = [item for item in cases if item.split == "holdout"]
    if not train or not holdout:
        raise ValueError("dynamics fixture requires train and holdout cases")
    train_errors: list[float] = []
    holdout_errors: list[float] = []
    energy_drifts: list[float] = []
    reference_errors: list[float] = []
    reference_drifts: list[float] = []
    backend_deltas: list[float] = []
    for item in train:
        numerical, exact, drift = _verlet(item)
        reference_x, _, reference_drift = rk4_oscillator(item.x0, item.v0, item.omega, item.dt, item.steps)
        train_errors.append(abs(numerical - exact))
        energy_drifts.append(drift)
        reference_errors.append(abs(reference_x - exact))
        reference_drifts.append(reference_drift)
        backend_deltas.append(abs(numerical - reference_x))
    for item in holdout:
        numerical, exact, drift = _verlet(item)
        reference_x, _, reference_drift = rk4_oscillator(item.x0, item.v0, item.omega, item.dt, item.steps)
        holdout_errors.append(abs(numerical - exact))
        energy_drifts.append(drift)
        reference_errors.append(abs(reference_x - exact))
        reference_drifts.append(reference_drift)
        backend_deltas.append(abs(numerical - reference_x))
    negative_case = holdout[0]
    _, euler_energy = _euler(negative_case)
    initial_energy = _energy(negative_case.x0, negative_case.v0, negative_case.omega)
    negative_rejected = abs(euler_energy - initial_energy) > max_energy_drift
    backend_agreement = (
        max(backend_deltas) <= max_backend_delta
        and max(reference_errors) <= max_reference_error
        and max(reference_drifts) <= max_energy_drift
    )
    passed = max(holdout_errors) <= max_holdout_error and max(energy_drifts) <= max_energy_drift and negative_rejected and backend_agreement
    evaluation = DynamicsEvaluation(
        train_max_position_error=max(train_errors),
        holdout_max_position_error=max(holdout_errors),
        max_energy_drift=max(energy_drifts),
        max_reference_position_error=max(reference_errors),
        max_reference_energy_drift=max(reference_drifts),
        max_backend_position_delta=max(backend_deltas),
        backend_agreement_passed=backend_agreement,
        negative_euler_rejected=negative_rejected,
        passed=passed,
        notes=[
            "Velocity-Verlet and independently implemented fixed-step RK4 are compared with the closed-form harmonic solution.",
            "Explicit Euler is a required negative control for conservation drift.",
            "The RK4 method citation is a reference, not an imported software or data dependency.",
        ],
    )
    receipt = make_track_receipt(
        track_id="T3",
        evaluator_id=evaluation.evaluator_id,
        input_payload=[item.model_dump(mode="json") for item in cases],
        evidence_level="validated-reproduction" if passed else "demo",
        passed=passed,
        negative_case_passed=negative_rejected,
        result=evaluation.model_dump(mode="json"),
        blocked_gates=["multi-body and real mission validation", "external solver and source-rights review"],
    )
    return evaluation, receipt
