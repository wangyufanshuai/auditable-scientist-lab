"""T3 symmetric planar three-body benchmark with an analytic orbit reference."""

from __future__ import annotations

from math import cos, hypot, isfinite, pi, sin, sqrt
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .common import TrackReceipt, make_track_receipt
from .reference_nbody_rk4 import rk4_three_body

Point = tuple[float, float]


class NBodyCase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    case_id: str = Field(min_length=1)
    split: Literal["train", "holdout"]
    masses: list[float] = Field(min_length=3, max_length=3)
    gravitational_constant: float = Field(gt=0)
    side_length: float = Field(gt=0)
    orbit_fraction: float = Field(gt=0, le=1)
    steps: int = Field(ge=100, le=10000)

    @model_validator(mode="after")
    def finite_parameters(self) -> NBodyCase:
        values = [*self.masses, self.gravitational_constant, self.side_length, self.orbit_fraction]
        if not all(isfinite(value) and value > 0 for value in values):
            raise ValueError("three-body parameters must be positive finite numbers")
        if max(values) > 1000 or min(values) < 1e-3:
            raise ValueError("three-body fixture parameters exceed the bounded scale")
        return self


class NBodyEvaluation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    evaluator_id: str = "equilateral-three-body-v1"
    solver_id: str = "velocity-verlet-pairwise-v1"
    reference_solver_id: str = "independent-cartesian-rk4-v1"
    case_results: list[dict[str, float | str]]
    max_verlet_position_error: float
    max_rk4_position_error: float
    max_backend_position_delta: float
    max_relative_energy_drift: float
    max_relative_angular_momentum_drift: float
    max_center_of_mass_drift: float
    max_pair_distance_error: float
    negative_repulsive_force_error: float
    negative_force_rejected: bool
    passed: bool
    notes: list[str]


def initial_state(case: NBodyCase) -> tuple[list[Point], list[Point], float]:
    side = case.side_length
    raw: list[Point] = [(0.0, 0.0), (side, 0.0), (side / 2, sqrt(3) * side / 2)]
    total_mass = sum(case.masses)
    center = (
        sum(m * p[0] for m, p in zip(case.masses, raw)) / total_mass,
        sum(m * p[1] for m, p in zip(case.masses, raw)) / total_mass,
    )
    positions = [(p[0] - center[0], p[1] - center[1]) for p in raw]
    omega = sqrt(case.gravitational_constant * total_mass / side**3)
    velocities = [(-omega * p[1], omega * p[0]) for p in positions]
    return positions, velocities, omega


def analytic_positions(initial: list[Point], omega: float, time: float) -> list[Point]:
    cosine, sine = cos(omega * time), sin(omega * time)
    return [(cosine * x - sine * y, sine * x + cosine * y) for x, y in initial]


def _acceleration(positions: list[Point], masses: list[float], g: float, *, repulsive: bool = False) -> list[Point]:
    acceleration = [[0.0, 0.0] for _ in positions]
    direction = -1.0 if repulsive else 1.0
    for i in range(3):
        for j in range(i + 1, 3):
            dx = positions[j][0] - positions[i][0]
            dy = positions[j][1] - positions[i][1]
            radius = hypot(dx, dy)
            if radius <= 0 or not isfinite(radius):
                raise ValueError("three-body integration encountered a collision or nonfinite separation")
            factor = direction * g / radius**3
            for axis, delta in enumerate((dx, dy)):
                acceleration[i][axis] += factor * masses[j] * delta
                acceleration[j][axis] -= factor * masses[i] * delta
    return [(row[0], row[1]) for row in acceleration]


def _invariants(positions: list[Point], velocities: list[Point], case: NBodyCase) -> tuple[float, float, float]:
    kinetic = sum(0.5 * mass * (vx * vx + vy * vy) for mass, (vx, vy) in zip(case.masses, velocities))
    potential = 0.0
    for i in range(3):
        for j in range(i + 1, 3):
            radius = hypot(positions[j][0] - positions[i][0], positions[j][1] - positions[i][1])
            potential -= case.gravitational_constant * case.masses[i] * case.masses[j] / radius
    angular = sum(mass * (x * vy - y * vx) for mass, (x, y), (vx, vy) in zip(case.masses, positions, velocities))
    center_x = sum(mass * point[0] for mass, point in zip(case.masses, positions)) / sum(case.masses)
    center_y = sum(mass * point[1] for mass, point in zip(case.masses, positions)) / sum(case.masses)
    return kinetic + potential, angular, hypot(center_x, center_y)


def _integrate(case: NBodyCase, *, repulsive: bool = False) -> tuple[list[Point], dict[str, float]]:
    initial, velocities, omega = initial_state(case)
    positions = initial[:]
    dt = 2 * pi * case.orbit_fraction / (omega * case.steps)
    energy0, angular0, _ = _invariants(positions, velocities, case)
    max_energy = max_angular = max_center = max_pair = 0.0
    acceleration = _acceleration(positions, case.masses, case.gravitational_constant, repulsive=repulsive)
    for step in range(case.steps):
        next_positions = [
            (x + dt * vx + 0.5 * dt * dt * ax, y + dt * vy + 0.5 * dt * dt * ay)
            for (x, y), (vx, vy), (ax, ay) in zip(positions, velocities, acceleration)
        ]
        next_acceleration = _acceleration(next_positions, case.masses, case.gravitational_constant, repulsive=repulsive)
        velocities = [
            (vx + 0.5 * dt * (ax + nax), vy + 0.5 * dt * (ay + nay))
            for (vx, vy), (ax, ay), (nax, nay) in zip(velocities, acceleration, next_acceleration)
        ]
        positions, acceleration = next_positions, next_acceleration
        if not all(isfinite(value) for point in [*positions, *velocities] for value in point):
            raise ValueError("three-body integration diverged")
        if not repulsive:
            energy, angular, center = _invariants(positions, velocities, case)
            max_energy = max(max_energy, abs((energy - energy0) / energy0))
            max_angular = max(max_angular, abs((angular - angular0) / angular0))
            max_center = max(max_center, center / case.side_length)
            for i in range(3):
                for j in range(i + 1, 3):
                    distance = hypot(positions[j][0] - positions[i][0], positions[j][1] - positions[i][1])
                    max_pair = max(max_pair, abs(distance / case.side_length - 1))
    return positions, {"energy": max_energy, "angular": max_angular, "center": max_center, "pair": max_pair, "dt": dt}


def evaluate_nbody_fixture(cases: list[NBodyCase]) -> tuple[NBodyEvaluation, TrackReceipt]:
    if not cases or {case.split for case in cases} != {"train", "holdout"}:
        raise ValueError("three-body fixture requires train and holdout cases")
    if len({case.case_id for case in cases}) != len(cases):
        raise ValueError("three-body case IDs must be distinct")
    rows: list[dict[str, float | str]] = []
    for case in cases:
        initial, velocities, omega = initial_state(case)
        verlet, diagnostic = _integrate(case)
        rk4, _ = rk4_three_body(initial, velocities, case.masses, case.gravitational_constant, diagnostic["dt"], case.steps)
        exact = analytic_positions(initial, omega, diagnostic["dt"] * case.steps)
        scale = case.side_length
        rows.append({
            "case_id": case.case_id, "split": case.split,
            "verlet_position_error": max(hypot(x - ex, y - ey) / scale for (x, y), (ex, ey) in zip(verlet, exact)),
            "rk4_position_error": max(hypot(x - ex, y - ey) / scale for (x, y), (ex, ey) in zip(rk4, exact)),
            "backend_position_delta": max(hypot(x - rx, y - ry) / scale for (x, y), (rx, ry) in zip(verlet, rk4)),
            "relative_energy_drift": diagnostic["energy"],
            "relative_angular_momentum_drift": diagnostic["angular"],
            "center_of_mass_drift": diagnostic["center"],
            "pair_distance_error": diagnostic["pair"],
        })
    negative_case = next(case for case in cases if case.split == "holdout")
    initial, _, omega = initial_state(negative_case)
    wrong, diagnostic = _integrate(negative_case, repulsive=True)
    exact = analytic_positions(initial, omega, diagnostic["dt"] * negative_case.steps)
    negative_error = max(hypot(x - ex, y - ey) / negative_case.side_length for (x, y), (ex, ey) in zip(wrong, exact))
    maxima = {key: max(float(row[key]) for row in rows) for key in (
        "verlet_position_error", "rk4_position_error", "backend_position_delta", "relative_energy_drift",
        "relative_angular_momentum_drift", "center_of_mass_drift", "pair_distance_error",
    )}
    rejected = negative_error > 0.1
    passed = (
        maxima["verlet_position_error"] <= 1e-3
        and maxima["rk4_position_error"] <= 1e-5
        and maxima["backend_position_delta"] <= 1e-3
        and maxima["relative_energy_drift"] <= 1e-4
        and maxima["relative_angular_momentum_drift"] <= 1e-10
        and maxima["center_of_mass_drift"] <= 1e-10
        and maxima["pair_distance_error"] <= 1e-3
        and rejected
    )
    evaluation = NBodyEvaluation(
        case_results=rows,
        max_verlet_position_error=maxima["verlet_position_error"],
        max_rk4_position_error=maxima["rk4_position_error"],
        max_backend_position_delta=maxima["backend_position_delta"],
        max_relative_energy_drift=maxima["relative_energy_drift"],
        max_relative_angular_momentum_drift=maxima["relative_angular_momentum_drift"],
        max_center_of_mass_drift=maxima["center_of_mass_drift"],
        max_pair_distance_error=maxima["pair_distance_error"],
        negative_repulsive_force_error=negative_error,
        negative_force_rejected=rejected,
        passed=passed,
        notes=[
            "Dimensionless, equilateral circular initial conditions only; the orbit has a direct analytic reference.",
            "Velocity-Verlet and a separately coded Cartesian RK4 are compared to that reference.",
            "No perturbed three-body, real mission, or general N-body validity is inferred.",
        ],
    )
    receipt = make_track_receipt(
        track_id="T3N", evaluator_id=evaluation.evaluator_id,
        input_payload=[case.model_dump(mode="json") for case in cases],
        evidence_level="validated-reproduction" if passed else "demo",
        passed=passed, negative_case_passed=rejected,
        result=evaluation.model_dump(mode="json"),
        blocked_gates=["perturbed or nonintegrable multi-body validation", "real-mission provenance and source-rights review"],
    )
    return evaluation, receipt
