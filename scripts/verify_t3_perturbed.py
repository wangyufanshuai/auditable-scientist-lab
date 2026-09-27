"""Optional pinned-SciPy audit of two finite-horizon perturbed three-body cases."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from math import hypot, isfinite, pi
from pathlib import Path

import numpy as np
from scipy.integrate import solve_ivp

from auditable_scientist.tracks.nbody import (
    NBodyCase,
    _acceleration,
    _invariants,
    analytic_positions,
    initial_state,
)
from auditable_scientist.tracks.reference_nbody_rk4 import rk4_three_body
from verify_t3_external_scipy import sha256, verify_environment


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "examples/dynamics/nbody-fixture.json"
OUTPUT = ROOT / "artifacts/t3-perturbed-audit.json"
GRID = (("equal-train", 0.02, 0.35), ("unequal-holdout", 0.03, 0.35))
RTOL, ATOL = 1e-12, 1e-14
GATES = {
    "fine_verlet_position_error_max": 1e-4,
    "fine_verlet_velocity_error_max": 1e-4,
    "rk4_position_error_max": 1e-7,
    "verlet_convergence_ratio_min": 3.0,
    "relative_energy_drift_max": 1e-4,
    "relative_angular_momentum_drift_max": 1e-10,
    "center_of_mass_drift_max": 1e-10,
    "minimum_pair_separation_ratio_min": 0.5,
    "perturbation_effect_min": 1e-4,
    "repulsive_force_error_min": 0.1,
}


def _point_error(left: list[tuple[float, float]], right: list[tuple[float, float]], scale: float) -> float:
    return max(hypot(x - rx, y - ry) / scale for (x, y), (rx, ry) in zip(left, right))


def _perturbed_state(case: NBodyCase, fraction: float) -> tuple[list[tuple[float, float]], list[tuple[float, float]], float]:
    positions, original_velocities, omega = initial_state(case)
    impulse = fraction * omega * case.side_length
    velocities = original_velocities[:]
    velocities[0] = (velocities[0][0], velocities[0][1] + impulse)
    velocities[1] = (velocities[1][0], velocities[1][1] - impulse * case.masses[0] / case.masses[1])
    return positions, velocities, omega


def _minimum_separation(positions: list[tuple[float, float]], side: float) -> float:
    return min(hypot(positions[j][0] - positions[i][0], positions[j][1] - positions[i][1]) / side
               for i in range(3) for j in range(i + 1, 3))


def _verlet(case: NBodyCase, positions: list[tuple[float, float]], velocities: list[tuple[float, float]],
            duration: float, steps: int, *, repulsive: bool = False) -> dict[str, object]:
    positions, velocities = positions[:], velocities[:]
    dt = duration / steps
    energy0, angular0, _ = _invariants(positions, velocities, case)
    if abs(energy0) <= 1e-12 or abs(angular0) <= 1e-12:
        raise ValueError("the perturbed fixture requires nonzero initial invariants")
    energy_drift = angular_drift = center_drift = 0.0
    minimum_separation = _minimum_separation(positions, case.side_length)
    acceleration = _acceleration(positions, case.masses, case.gravitational_constant, repulsive=repulsive)
    for _ in range(steps):
        next_positions = [(x + dt * vx + 0.5 * dt * dt * ax, y + dt * vy + 0.5 * dt * dt * ay)
                          for (x, y), (vx, vy), (ax, ay) in zip(positions, velocities, acceleration)]
        next_acceleration = _acceleration(next_positions, case.masses, case.gravitational_constant, repulsive=repulsive)
        velocities = [(vx + 0.5 * dt * (ax + bx), vy + 0.5 * dt * (ay + by))
                      for (vx, vy), (ax, ay), (bx, by) in zip(velocities, acceleration, next_acceleration)]
        positions, acceleration = next_positions, next_acceleration
        if not all(isfinite(value) for point in [*positions, *velocities] for value in point):
            raise ValueError("perturbed three-body integration diverged")
        minimum_separation = min(minimum_separation, _minimum_separation(positions, case.side_length))
        if not repulsive:
            energy, angular, center = _invariants(positions, velocities, case)
            energy_drift = max(energy_drift, abs((energy - energy0) / energy0))
            angular_drift = max(angular_drift, abs((angular - angular0) / angular0))
            center_drift = max(center_drift, center / case.side_length)
    return {
        "positions": positions, "velocities": velocities,
        "relative_energy_drift": energy_drift,
        "relative_angular_momentum_drift": angular_drift,
        "center_of_mass_drift": center_drift,
        "minimum_pair_separation_ratio": minimum_separation,
    }


def _dop853(case: NBodyCase, positions: list[tuple[float, float]], velocities: list[tuple[float, float]],
            duration: float, *, repulsive: bool = False) -> dict[str, object]:
    initial = np.array([value for point in [*positions, *velocities] for value in point], dtype=float)

    def derivative(_time: float, state: np.ndarray) -> np.ndarray:
        slope = np.zeros(12, dtype=float)
        slope[:6] = state[6:]
        sign = -1.0 if repulsive else 1.0
        for i in range(3):
            for j in range(3):
                if i == j:
                    continue
                dx, dy = state[2*j:2*j+2] - state[2*i:2*i+2]
                distance = hypot(float(dx), float(dy))
                if distance <= 0 or not isfinite(distance):
                    raise ValueError("DOP853 reference encountered invalid separation")
                slope[6+2*i:8+2*i] += sign * case.gravitational_constant * case.masses[j] * np.array((dx, dy)) / distance**3
        return slope

    result = solve_ivp(derivative, (0.0, duration), initial, method="DOP853", rtol=RTOL, atol=ATOL,
                       t_eval=np.linspace(0.0, duration, 101))
    if not result.success or result.status != 0 or result.y.shape != (12, 101):
        raise ValueError(f"DOP853 reference failed for {case.case_id}")
    final = result.y[:, -1]
    sampled_minimum = min(
        _minimum_separation([(float(result.y[2*i, k]), float(result.y[2*i+1, k])) for i in range(3)], case.side_length)
        for k in range(101)
    )
    return {
        "positions": [(float(final[2*i]), float(final[2*i+1])) for i in range(3)],
        "velocities": [(float(final[6+2*i]), float(final[7+2*i])) for i in range(3)],
        "minimum_pair_separation_ratio": sampled_minimum,
        "function_calls": int(result.nfev),
    }


def build_receipt() -> dict[str, object]:
    environment = verify_environment()
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    if fixture.get("schema_version") != "nbody-fixture-v1":
        raise ValueError("T3N fixture version differs")
    cases = {case.case_id: case for case in (NBodyCase.model_validate(row) for row in fixture["cases"])}
    if set(cases) != {name for name, _, _ in GRID}:
        raise ValueError("perturbed grid and source cases differ")
    rows: list[dict[str, float | int | str]] = []
    for case_id, perturbation, horizon_fraction in GRID:
        case = cases[case_id]
        positions, velocities, omega = _perturbed_state(case, perturbation)
        duration = 2 * pi * horizon_fraction / omega
        reference = _dop853(case, positions, velocities, duration)
        coarse = _verlet(case, positions, velocities, duration, case.steps)
        fine = _verlet(case, positions, velocities, duration, 2 * case.steps)
        rk4_positions, _ = rk4_three_body(positions, velocities, case.masses, case.gravitational_constant,
                                           duration / (2 * case.steps), 2 * case.steps)
        coarse_error = _point_error(coarse["positions"], reference["positions"], case.side_length)
        fine_error = _point_error(fine["positions"], reference["positions"], case.side_length)
        if not 0 < fine_error < coarse_error:
            raise ValueError("Verlet refinement did not produce a finite, nonzero improvement")
        rows.append({
            "case_id": case_id, "split": case.split, "perturbation_fraction": perturbation,
            "horizon_fraction_of_unperturbed_orbit": horizon_fraction,
            "coarse_steps": case.steps, "fine_steps": 2 * case.steps,
            "coarse_verlet_position_error": coarse_error,
            "fine_verlet_position_error": fine_error,
            "fine_verlet_velocity_error": _point_error(fine["velocities"], reference["velocities"], omega * case.side_length),
            "rk4_position_error": _point_error(rk4_positions, reference["positions"], case.side_length),
            "verlet_convergence_ratio": coarse_error / fine_error,
            "relative_energy_drift": fine["relative_energy_drift"],
            "relative_angular_momentum_drift": fine["relative_angular_momentum_drift"],
            "center_of_mass_drift": fine["center_of_mass_drift"],
            "minimum_pair_separation_ratio": min(fine["minimum_pair_separation_ratio"], reference["minimum_pair_separation_ratio"]),
            "perturbation_effect": _point_error(reference["positions"], analytic_positions(positions, omega, duration), case.side_length),
            "dop853_function_calls": reference["function_calls"],
        })
    negative_case = cases[GRID[1][0]]
    negative_positions, negative_velocities, negative_omega = _perturbed_state(negative_case, GRID[1][1])
    negative_duration = 2 * pi * GRID[1][2] / negative_omega
    attractive = _dop853(negative_case, negative_positions, negative_velocities, negative_duration)
    repulsive = _verlet(negative_case, negative_positions, negative_velocities, negative_duration, negative_case.steps,
                        repulsive=True)
    negative_error = _point_error(repulsive["positions"], attractive["positions"], negative_case.side_length)
    checks = {
        "train_and_holdout_present": {row["split"] for row in rows} == {"train", "holdout"},
        "fine_verlet_position": all(row["fine_verlet_position_error"] <= GATES["fine_verlet_position_error_max"] for row in rows),
        "fine_verlet_velocity": all(row["fine_verlet_velocity_error"] <= GATES["fine_verlet_velocity_error_max"] for row in rows),
        "rk4_position": all(row["rk4_position_error"] <= GATES["rk4_position_error_max"] for row in rows),
        "verlet_convergence": all(row["verlet_convergence_ratio"] >= GATES["verlet_convergence_ratio_min"] for row in rows),
        "energy_drift": all(row["relative_energy_drift"] <= GATES["relative_energy_drift_max"] for row in rows),
        "angular_momentum_drift": all(row["relative_angular_momentum_drift"] <= GATES["relative_angular_momentum_drift_max"] for row in rows),
        "center_of_mass_drift": all(row["center_of_mass_drift"] <= GATES["center_of_mass_drift_max"] for row in rows),
        "collision_avoided": all(row["minimum_pair_separation_ratio"] >= GATES["minimum_pair_separation_ratio_min"] for row in rows),
        "perturbation_effect": all(row["perturbation_effect"] >= GATES["perturbation_effect_min"] for row in rows),
        "repulsive_force_rejected": negative_error >= GATES["repulsive_force_error_min"],
    }
    sources = (Path(__file__).resolve(), FIXTURE, ROOT / "src/auditable_scientist/tracks/nbody.py",
               ROOT / "src/auditable_scientist/tracks/reference_nbody_rk4.py",
               ROOT / "scripts/verify_t3_external_scipy.py", ROOT / "requirements-t3-scipy-win-py312.txt",
               ROOT / "docs/T3_PERTURBED_METHOD.md")
    return {
        "schema_version": "t3-perturbed-audit-v1",
        "status": "passed-optional-finite-horizon-cross-check" if all(checks.values()) else "failed",
        "scope": "two synthetic, momentum-balanced velocity perturbations of bounded planar Newtonian three-body initial states",
        "environment": environment,
        "solver": {"reference": "scipy.integrate.solve_ivp:DOP853", "rtol": RTOL, "atol": ATOL,
                   "local": "velocity-Verlet", "secondary": "independent Cartesian RK4"},
        "grid": [{"case_id": name, "perturbation_fraction": perturbation, "horizon_fraction": horizon}
                 for name, perturbation, horizon in GRID],
        "gates": GATES, "rows": rows, "negative_repulsive_force_error": negative_error, "checks": checks,
        "source_files": [{"path": path.relative_to(ROOT).as_posix(), "sha256": sha256(path), "bytes": path.stat().st_size}
                         for path in sources],
        "boundaries": {
            "core_run_evidence": False, "real_ephemerides": False, "mission_validation": False,
            "chaos_or_long_horizon_validation": False, "general_nbody_validity": False,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true")
    mode.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    receipt = build_receipt()
    if args.write:
        receipt["recorded_at"] = datetime.now(timezone.utc).isoformat()
        OUTPUT.write_text(json.dumps(receipt, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")
    else:
        saved = json.loads(OUTPUT.read_text(encoding="utf-8"))
        saved.pop("recorded_at", None)
        if saved != receipt:
            raise SystemExit("perturbed audit differs from the recomputed source and solver result")
    if receipt["status"] == "failed":
        raise SystemExit("perturbed three-body gate failed")
    print(json.dumps({"status": receipt["status"], "rows": receipt["rows"],
                      "negative_repulsive_force_error": receipt["negative_repulsive_force_error"],
                      "checks": receipt["checks"]}, indent=2))


if __name__ == "__main__":
    main()
