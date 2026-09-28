"""Pinned-SciPy T3 finite-horizon extension with close-approach rejection."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from math import hypot, isfinite, pi
from pathlib import Path

import numpy as np
from scipy.integrate import solve_ivp

from auditable_scientist.tracks.nbody import NBodyCase
from auditable_scientist.tracks.reference_nbody_rk4 import rk4_three_body
from verify_t3_external_scipy import verify_environment
from verify_t3_perturbed import _perturbed_state, _point_error, _verlet


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "examples/dynamics/nbody-fixture.json"
AUDIT = ROOT / "artifacts/t3-horizon-grid-audit.json"
GRID_ADMITTED = (("equal-train", 0.02, 0.75), ("unequal-holdout", 0.02, 0.75))
GRID_STRESS = (("equal-train", 0.02, 1.0), ("unequal-holdout", 0.02, 1.0))
RTOL, ATOL = 1e-12, 1e-14
SEPARATION_THRESHOLD = 0.5
GATES = {
    "fine_verlet_position_error_max": 1e-5,
    "fine_verlet_velocity_error_max": 1e-5,
    "rk4_position_error_max": 1e-8,
    "verlet_convergence_ratio_min": 3.0,
    "relative_energy_drift_max": 1e-5,
    "relative_angular_momentum_drift_max": 1e-10,
    "center_of_mass_drift_max": 1e-10,
    "minimum_sampled_pair_separation_ratio_min": SEPARATION_THRESHOLD,
}
BUDGET = {"dop853_function_calls_total_max": 12000, "fixed_steps_total_max": 35000}
SOURCE_PATHS = (
    Path(__file__).resolve(),
    ROOT / "scripts/verify_t3_perturbed.py",
    ROOT / "scripts/verify_t3_external_scipy.py",
    ROOT / "src/auditable_scientist/tracks/nbody.py",
    ROOT / "src/auditable_scientist/tracks/reference_nbody_rk4.py",
    ROOT / "requirements-t3-scipy-win-py312.txt",
    ROOT / "docs/T3_HORIZON_GRID.md",
    FIXTURE,
    ROOT / "artifacts/t3-perturbed-audit.json",
)
PRIOR_AUDIT = ROOT / "artifacts/t3-perturbed-audit.json"


def _source_record(path: Path) -> dict:
    data = path.read_bytes()
    record = {"path": path.relative_to(ROOT).as_posix()}
    if path == PRIOR_AUDIT:
        # Git's text=lf attribute stores this older CRLF-generated JSON with LF bytes.
        # Bind the portable repository representation, not the checkout's line endings.
        data = data.replace(b"\r\n", b"\n")
        record["normalization"] = "crlf-to-lf"
    return {**record, "sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)}


def _separation(state: np.ndarray, i: int, j: int, side: float) -> float:
    dx = float(state[2*j] - state[2*i])
    dy = float(state[2*j+1] - state[2*i+1])
    return hypot(dx, dy) / side


def _reference(case: NBodyCase, positions: list[tuple[float, float]],
               velocities: list[tuple[float, float]], duration: float) -> dict:
    initial = np.array([value for point in [*positions, *velocities] for value in point], dtype=float)

    def derivative(_time: float, state: np.ndarray) -> np.ndarray:
        slope = np.zeros(12, dtype=float)
        slope[:6] = state[6:]
        for i in range(3):
            for j in range(i + 1, 3):
                dx = state[2*j:2*j+2] - state[2*i:2*i+2]
                radius = hypot(float(dx[0]), float(dx[1]))
                if radius <= 0 or not isfinite(radius):
                    raise ValueError("DOP853 horizon reference encountered invalid separation")
                acceleration = case.gravitational_constant * dx / radius**3
                slope[6+2*i:8+2*i] += case.masses[j] * acceleration
                slope[6+2*j:8+2*j] -= case.masses[i] * acceleration
        return slope

    events = []
    pairs = ((0, 1), (0, 2), (1, 2))
    for i, j in pairs:
        def inward_threshold(_time: float, state: np.ndarray, i: int = i, j: int = j) -> float:
            return _separation(state, i, j, case.side_length) - SEPARATION_THRESHOLD

        inward_threshold.direction = -1  # type: ignore[attr-defined]
        inward_threshold.terminal = False  # type: ignore[attr-defined]
        events.append(inward_threshold)
    solution = solve_ivp(
        derivative, (0.0, duration), initial, method="DOP853", rtol=RTOL, atol=ATOL,
        max_step=duration / 128, t_eval=np.linspace(0.0, duration, 501), events=events,
    )
    if not solution.success or solution.status != 0 or solution.y.shape != (12, 501):
        raise ValueError(f"DOP853 horizon reference failed for {case.case_id}")
    sampled_minimum = min(
        _separation(solution.y[:, index], i, j, case.side_length)
        for index in range(solution.y.shape[1]) for i, j in pairs
    )
    event_times = [float(time / duration) for pair_events in solution.t_events for time in pair_events]
    final = solution.y[:, -1]
    return {
        "positions": [(float(final[2*i]), float(final[2*i+1])) for i in range(3)],
        "velocities": [(float(final[6+2*i]), float(final[7+2*i])) for i in range(3)],
        "sampled_minimum_pair_separation_ratio": sampled_minimum,
        "inward_threshold_event_count": len(event_times),
        "first_inward_event_fraction_of_horizon": min(event_times) if event_times else None,
        "function_calls": int(solution.nfev),
    }


def _steps(case: NBodyCase, horizon_fraction: float) -> tuple[int, int]:
    coarse = round(case.steps * horizon_fraction / 0.35)
    return coarse, 2 * coarse


def build_audit() -> dict:
    environment = verify_environment()
    source = json.loads(FIXTURE.read_text(encoding="utf-8"))
    if source.get("schema_version") != "nbody-fixture-v1":
        raise ValueError("T3 horizon source fixture version differs")
    cases = {case.case_id: case for case in (NBodyCase.model_validate(row) for row in source["cases"])}
    if set(cases) != {"equal-train", "unequal-holdout"}:
        raise ValueError("T3 horizon source fixture inventory differs")
    admitted: list[dict] = []
    stress: list[dict] = []
    total_nfev = total_fixed = 0
    for case_id, perturbation, horizon in GRID_ADMITTED:
        case = cases[case_id]
        positions, velocities, omega = _perturbed_state(case, perturbation)
        duration = 2 * pi * horizon / omega
        reference = _reference(case, positions, velocities, duration)
        coarse_steps, fine_steps = _steps(case, horizon)
        coarse = _verlet(case, positions, velocities, duration, coarse_steps)
        fine = _verlet(case, positions, velocities, duration, fine_steps)
        rk4_positions, _ = rk4_three_body(
            positions, velocities, case.masses, case.gravitational_constant,
            duration / fine_steps, fine_steps,
        )
        coarse_error = _point_error(coarse["positions"], reference["positions"], case.side_length)
        fine_error = _point_error(fine["positions"], reference["positions"], case.side_length)
        if not 0 < fine_error < coarse_error:
            raise ValueError("T3 horizon refinement did not improve position error")
        total_nfev += reference["function_calls"]
        total_fixed += coarse_steps + fine_steps + fine_steps
        admitted.append({
            "case_id": case_id, "source_split": case.split,
            "perturbation_fraction": perturbation, "horizon_fraction": horizon,
            "coarse_steps": coarse_steps, "fine_steps": fine_steps,
            "dop853_function_calls": reference["function_calls"],
            "coarse_verlet_position_error": coarse_error,
            "fine_verlet_position_error": fine_error,
            "fine_verlet_velocity_error": _point_error(fine["velocities"], reference["velocities"], omega * case.side_length),
            "rk4_position_error": _point_error(rk4_positions, reference["positions"], case.side_length),
            "verlet_convergence_ratio": coarse_error / fine_error,
            "relative_energy_drift": fine["relative_energy_drift"],
            "relative_angular_momentum_drift": fine["relative_angular_momentum_drift"],
            "center_of_mass_drift": fine["center_of_mass_drift"],
            "sampled_minimum_pair_separation_ratio": min(
                reference["sampled_minimum_pair_separation_ratio"], fine["minimum_pair_separation_ratio"],
            ),
            "inward_threshold_event_count": reference["inward_threshold_event_count"],
        })
    for case_id, perturbation, horizon in GRID_STRESS:
        case = cases[case_id]
        positions, velocities, omega = _perturbed_state(case, perturbation)
        reference = _reference(case, positions, velocities, 2 * pi * horizon / omega)
        total_nfev += reference["function_calls"]
        stress.append({
            "case_id": case_id, "source_split": case.split,
            "perturbation_fraction": perturbation, "horizon_fraction": horizon,
            "dop853_function_calls": reference["function_calls"],
            "sampled_minimum_pair_separation_ratio": reference["sampled_minimum_pair_separation_ratio"],
            "inward_threshold_event_count": reference["inward_threshold_event_count"],
            "first_inward_event_fraction_of_horizon": reference["first_inward_event_fraction_of_horizon"],
            "admission": "excluded-close-approach",
        })
    checks = {
        "two_smooth_source_configurations": len(admitted) == 2 and {row["case_id"] for row in admitted} == set(cases),
        "fine_verlet_position": all(row["fine_verlet_position_error"] <= GATES["fine_verlet_position_error_max"] for row in admitted),
        "fine_verlet_velocity": all(row["fine_verlet_velocity_error"] <= GATES["fine_verlet_velocity_error_max"] for row in admitted),
        "rk4_position": all(row["rk4_position_error"] <= GATES["rk4_position_error_max"] for row in admitted),
        "verlet_convergence": all(row["verlet_convergence_ratio"] >= GATES["verlet_convergence_ratio_min"] for row in admitted),
        "energy_drift": all(row["relative_energy_drift"] <= GATES["relative_energy_drift_max"] for row in admitted),
        "angular_momentum_drift": all(row["relative_angular_momentum_drift"] <= GATES["relative_angular_momentum_drift_max"] for row in admitted),
        "center_of_mass_drift": all(row["center_of_mass_drift"] <= GATES["center_of_mass_drift_max"] for row in admitted),
        "smooth_separation": all(row["sampled_minimum_pair_separation_ratio"] > SEPARATION_THRESHOLD and row["inward_threshold_event_count"] == 0 for row in admitted),
        "stress_excluded": len(stress) == 2 and all(
            row["sampled_minimum_pair_separation_ratio"] < SEPARATION_THRESHOLD
            and row["inward_threshold_event_count"] >= 1
            and row["first_inward_event_fraction_of_horizon"] is not None
            for row in stress
        ),
        "compute_budget": total_nfev <= BUDGET["dop853_function_calls_total_max"] and total_fixed <= BUDGET["fixed_steps_total_max"],
    }
    return {
        "schema_version": "t3-horizon-grid-audit-v1",
        "status": "verified-finite-0.75-period-and-stress-rejection" if all(checks.values()) else "failed",
        "scope": "synthetic momentum-balanced planar three-body initial states; preflight-selected finite grid",
        "provider_environment": environment,
        "solver": {"reference": "scipy.integrate.solve_ivp:DOP853", "rtol": RTOL, "atol": ATOL,
                   "max_step_fraction_of_horizon": 1 / 128, "local": "velocity-Verlet",
                   "secondary": "independent Cartesian RK4", "event_threshold_ratio": SEPARATION_THRESHOLD},
        "admitted_grid": [{"case_id": case_id, "perturbation_fraction": epsilon, "horizon_fraction": horizon}
                          for case_id, epsilon, horizon in GRID_ADMITTED],
        "stress_grid": [{"case_id": case_id, "perturbation_fraction": epsilon, "horizon_fraction": horizon}
                        for case_id, epsilon, horizon in GRID_STRESS],
        "gates": GATES, "budget": BUDGET,
        "observed_budget": {"dop853_function_calls_total": total_nfev, "fixed_steps_total": total_fixed},
        "admitted_rows": admitted, "excluded_stress_rows": stress, "checks": checks,
        "source_files": [_source_record(path) for path in SOURCE_PATHS],
        "boundaries": {
            "smooth_synthetic_0_75_period_grid": all(checks.values()),
            "one_period_stress_cases_admitted": False,
            "chaotic_long_horizon_validated": False,
            "general_nbody_validated": False,
            "real_ephemerides": False,
            "mission_validation": False,
            "publication_ready": False,
            "core_t3_run_changed": False,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--write", action="store_true")
    action.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    current = build_audit()
    if current["status"] != "verified-finite-0.75-period-and-stress-rejection":
        raise SystemExit(f"T3 horizon grid failed: {current['checks']}")
    if args.write:
        current["recorded_at"] = datetime.now(timezone.utc).isoformat()
        AUDIT.write_text(json.dumps(current, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8", newline="\n")
    else:
        saved = json.loads(AUDIT.read_text(encoding="utf-8"))
        timestamp = saved.pop("recorded_at", None)
        if not timestamp or datetime.fromisoformat(timestamp).tzinfo is None or saved != current:
            raise SystemExit("T3 horizon audit differs from recomputed grid or source bytes")
    print(json.dumps({"status": current["status"], "checks": current["checks"],
                      "observed_budget": current["observed_budget"]}, sort_keys=True))


if __name__ == "__main__":
    main()
