"""Recompute a predeclared finite figure-eight three-body comparison."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
from math import hypot, isfinite
from pathlib import Path

import numpy as np
from scipy.integrate import solve_ivp

from auditable_scientist.tracks.reference_nbody_rk4 import rk4_three_body
from verify_t3_external_scipy import verify_environment


ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = ROOT / "docs/T3_FIGURE_EIGHT_PROTOCOL.json"
PROTOCOL_SHA256 = "7828754b52af988780a5e4679b017ff5c20d1aa490cc9720d250b1e719643a3d"
PREREGISTRATION_COMMIT = "4a75872"
PDF = ROOT / "data/references/chenciner_montgomery_figure_eight.pdf"
AUDIT = ROOT / "artifacts/t3-figure-eight-audit.json"
SOURCE_FILES = (
    Path(__file__).resolve(), PROTOCOL, ROOT / "docs/T3_FIGURE_EIGHT_PROTOCOL.md",
    ROOT / "src/auditable_scientist/tracks/reference_nbody_rk4.py",
    ROOT / "scripts/verify_t3_external_scipy.py",
    ROOT / "requirements-t3-scipy-win-py312.txt",
)


def _source(path: Path) -> dict:
    data = path.read_bytes()
    return {"path": path.relative_to(ROOT).as_posix(), "sha256": sha256(data).hexdigest(),
            "bytes": len(data)}


def _protocol() -> dict:
    contents = PROTOCOL.read_bytes()
    if sha256(contents).hexdigest() != PROTOCOL_SHA256:
        raise ValueError("precommitted figure-eight protocol bytes differ")
    config = json.loads(contents)
    if (config.get("schema_version") != "t3-figure-eight-protocol-v1"
            or config.get("scientific_boundaries", {}).get("claim_status") != "unverified"
            or config.get("scientific_boundaries", {}).get("real_mission_validated") is not False):
        raise ValueError("figure-eight protocol or claim boundary differs")
    if sha256(PDF.read_bytes()).hexdigest() != config["source"]["download_sha256"]:
        raise ValueError("source paper PDF differs from pinned bytes")
    return config


def _initial(config: dict, delta: float) -> tuple[list[tuple[float, float]], list[tuple[float, float]]]:
    system = config["system"]
    positions = [tuple(float(x) for x in point) for point in system["initial_positions"]]
    velocities = [tuple(float(x) for x in point) for point in system["initial_velocities"]]
    velocities[0] = (velocities[0][0], velocities[0][1] + delta)
    velocities[1] = (velocities[1][0], velocities[1][1] - delta)
    if (len(positions) != 3 or len(velocities) != 3
            or any(len(point) != 2 or not all(isfinite(value) for value in point)
                   for point in [*positions, *velocities])):
        raise ValueError("figure-eight initial state is not finite and planar")
    return positions, velocities


def _flatten(positions: list[tuple[float, float]], velocities: list[tuple[float, float]]) -> np.ndarray:
    return np.asarray([value for point in [*positions, *velocities] for value in point], dtype=float)


def _points(state: np.ndarray, offset: int) -> list[tuple[float, float]]:
    return [(float(state[offset+2*i]), float(state[offset+2*i+1])) for i in range(3)]


def _point_error(left: list[tuple[float, float]], right: list[tuple[float, float]], scale: float) -> float:
    return max(hypot(x-u, y-v) / scale for (x, y), (u, v) in zip(left, right, strict=True))


def _minimum_separation(positions: list[tuple[float, float]]) -> float:
    return min(hypot(positions[i][0]-positions[j][0], positions[i][1]-positions[j][1])
               for i in range(3) for j in range(i+1, 3))


def _invariants(positions: list[tuple[float, float]], velocities: list[tuple[float, float]],
                masses: list[float], g: float) -> dict[str, float]:
    kinetic = sum(0.5*m*(vx*vx+vy*vy) for m, (vx, vy) in zip(masses, velocities, strict=True))
    potential = -sum(g*masses[i]*masses[j] /
                     hypot(positions[i][0]-positions[j][0], positions[i][1]-positions[j][1])
                     for i in range(3) for j in range(i+1, 3))
    angular = sum(m*(x*vy-y*vx) for m, (x, y), (vx, vy) in
                  zip(masses, positions, velocities, strict=True))
    mass_total = sum(masses)
    center = (sum(m*x for m, (x, _) in zip(masses, positions, strict=True))/mass_total,
              sum(m*y for m, (_, y) in zip(masses, positions, strict=True))/mass_total)
    momentum = (sum(m*vx for m, (vx, _) in zip(masses, velocities, strict=True)),
                sum(m*vy for m, (_, vy) in zip(masses, velocities, strict=True)))
    return {"energy": kinetic+potential, "angular_momentum": angular,
            "center_of_mass_norm": hypot(*center), "linear_momentum_norm": hypot(*momentum)}


def _reference(config: dict, positions: list[tuple[float, float]],
               velocities: list[tuple[float, float]], duration: float,
               *, repulsive: bool = False) -> dict:
    masses = config["system"]["masses"]
    g = config["system"]["gravitational_constant"] * (-1 if repulsive else 1)
    threshold = config["solvers"]["event_min_pair_separation"]
    period = config["system"]["published_approximate_period"]
    initial = _flatten(positions, velocities)

    def derivative(_time: float, state: np.ndarray) -> np.ndarray:
        result = np.zeros(12, dtype=float)
        result[:6] = state[6:]
        for i in range(3):
            for j in range(i+1, 3):
                difference = state[2*j:2*j+2] - state[2*i:2*i+2]
                radius = hypot(float(difference[0]), float(difference[1]))
                if radius <= 0 or not isfinite(radius):
                    raise ValueError("DOP853 encountered a collision or nonfinite separation")
                acceleration = g * difference / radius**3
                result[6+2*i:8+2*i] += masses[j]*acceleration
                result[6+2*j:8+2*j] -= masses[i]*acceleration
        return result

    events = []
    if not repulsive:
        for i, j in ((0, 1), (0, 2), (1, 2)):
            def approaching(_time: float, state: np.ndarray,
                            left: int = i, right: int = j) -> float:
                return hypot(float(state[2*left]-state[2*right]),
                             float(state[2*left+1]-state[2*right+1])) - threshold

            approaching.direction = -1  # type: ignore[attr-defined]
            approaching.terminal = False  # type: ignore[attr-defined]
            events.append(approaching)
    sample_count = 501 if duration <= period else 2001
    solution = solve_ivp(
        derivative, (0.0, duration), initial, method="DOP853",
        rtol=config["solvers"]["rtol"], atol=config["solvers"]["atol"],
        max_step=period*config["solvers"]["max_step_as_period_fraction"],
        t_eval=np.linspace(0.0, duration, sample_count), events=events if events else None,
    )
    if (not solution.success or solution.status != 0
            or solution.y.shape != (12, sample_count)
            or not np.all(np.isfinite(solution.y))):
        raise ValueError("DOP853 figure-eight reference failed")
    minimum = min(_minimum_separation(_points(solution.y[:, index], 0))
                  for index in range(sample_count))
    final = solution.y[:, -1]
    crossings = sum(len(group) for group in solution.t_events) if solution.t_events is not None else 0
    return {"positions": _points(final, 0), "velocities": _points(final, 6),
            "sampled_minimum_pair_separation": minimum,
            "inward_threshold_crossings": crossings,
            "rhs_calls": int(solution.nfev)}


def _rk4(config: dict, positions: list[tuple[float, float]],
         velocities: list[tuple[float, float]], periods: int, steps_per_period: int) -> dict:
    masses = config["system"]["masses"]
    g = config["system"]["gravitational_constant"]
    dt = config["system"]["published_approximate_period"] / steps_per_period
    initial = _invariants(positions, velocities, masses, g)
    diagnostics = {"relative_energy_drift": 0.0, "absolute_angular_momentum_drift": 0.0,
                   "center_of_mass_drift": 0.0, "linear_momentum_drift": 0.0,
                   "sampled_minimum_pair_separation": _minimum_separation(positions)}
    total_steps = periods*steps_per_period
    for start in range(0, total_steps, 100):
        length = min(100, total_steps-start)
        positions, velocities = rk4_three_body(positions, velocities, masses, g, dt, length)
        if any(not isfinite(value) for point in [*positions, *velocities] for value in point):
            raise ValueError("RK4 figure-eight state diverged")
        current = _invariants(positions, velocities, masses, g)
        diagnostics["relative_energy_drift"] = max(
            diagnostics["relative_energy_drift"],
            abs(current["energy"]-initial["energy"])/max(abs(initial["energy"]), 1.0))
        diagnostics["absolute_angular_momentum_drift"] = max(
            diagnostics["absolute_angular_momentum_drift"],
            abs(current["angular_momentum"]-initial["angular_momentum"]))
        diagnostics["center_of_mass_drift"] = max(
            diagnostics["center_of_mass_drift"], current["center_of_mass_norm"])
        diagnostics["linear_momentum_drift"] = max(
            diagnostics["linear_momentum_drift"], current["linear_momentum_norm"])
        diagnostics["sampled_minimum_pair_separation"] = min(
            diagnostics["sampled_minimum_pair_separation"], _minimum_separation(positions))
    return {"positions": positions, "velocities": velocities,
            "steps": total_steps, "sampled_diagnostics": diagnostics}


def build_audit() -> dict:
    config = _protocol()
    environment = verify_environment()
    versions = environment.get("platform_and_packages", {})
    if (versions.get("scipy") != config["solvers"]["scipy_version"]
            or versions.get("numpy") != config["solvers"]["numpy_version"]):
        raise ValueError("pinned SciPy/NumPy versions differ")
    period = config["system"]["published_approximate_period"]
    normalizer = config["system"]["position_normalizer"]
    gates = config["engineering_gates"]
    scenarios = config["scenarios"]
    if [row["id"] for row in scenarios] != [
            "published-one-period", "published-ten-period", "perturbed-ten-period"]:
        raise ValueError("figure-eight case inventory differs")
    rows = []
    total_rhs_calls = total_fixed_steps = 0
    for spec in scenarios:
        positions, velocities = _initial(config, spec["opposite_y_velocity_perturbation"])
        duration = period*spec["periods"]
        reference = _reference(config, positions, velocities, duration)
        coarse = _rk4(config, positions, velocities, spec["periods"],
                      config["solvers"]["coarse_steps_per_period"])
        fine = _rk4(config, positions, velocities, spec["periods"],
                    config["solvers"]["fine_steps_per_period"])
        coarse_error = _point_error(coarse["positions"], reference["positions"], normalizer)
        fine_error = _point_error(fine["positions"], reference["positions"], normalizer)
        if not 0 < fine_error < coarse_error:
            raise ValueError("RK4 refinement failed to produce a finite improvement")
        total_rhs_calls += reference["rhs_calls"]
        total_fixed_steps += coarse["steps"]+fine["steps"]
        diagnostics = fine["sampled_diagnostics"]
        rows.append({
            "id": spec["id"], "periods": spec["periods"],
            "opposite_y_velocity_perturbation": spec["opposite_y_velocity_perturbation"],
            "duration": duration,
            "reference_endpoint_positions": [list(point) for point in reference["positions"]],
            "reference_endpoint_velocities": [list(point) for point in reference["velocities"]],
            "fine_rk4_endpoint_positions": [list(point) for point in fine["positions"]],
            "fine_rk4_endpoint_velocities": [list(point) for point in fine["velocities"]],
            "coarse_rk4_endpoint_position_error": coarse_error,
            "fine_rk4_endpoint_position_error": fine_error,
            "fine_rk4_endpoint_velocity_error": _point_error(
                fine["velocities"], reference["velocities"], config["system"]["velocity_normalizer"]),
            "coarse_to_fine_error_ratio": coarse_error/fine_error,
            "fine_rk4_sampled_diagnostics": diagnostics,
            "reference_sampled_minimum_pair_separation": reference["sampled_minimum_pair_separation"],
            "reference_inward_threshold_crossings": reference["inward_threshold_crossings"],
            "reference_rhs_calls": reference["rhs_calls"],
            "coarse_rk4_steps": coarse["steps"], "fine_rk4_steps": fine["steps"],
            "published_state_closure_error": _point_error(reference["positions"], positions, normalizer),
        })
    negative_positions, negative_velocities = _initial(config, 0.0)
    attractive = _reference(config, negative_positions, negative_velocities, period/4)
    repulsive = _reference(config, negative_positions, negative_velocities, period/4, repulsive=True)
    total_rhs_calls += attractive["rhs_calls"]+repulsive["rhs_calls"]
    negative_error = _point_error(repulsive["positions"], attractive["positions"], normalizer)
    checks = {
        "finite_three_case_inventory": len(rows) == 3 and all(
            all(isfinite(x) for x in (row["fine_rk4_endpoint_position_error"],
                                      row["fine_rk4_endpoint_velocity_error"],
                                      row["coarse_to_fine_error_ratio"])) for row in rows),
        "endpoint_position": all(row["fine_rk4_endpoint_position_error"] <=
                                 gates["fine_rk4_endpoint_position_error_max"] for row in rows),
        "endpoint_velocity": all(row["fine_rk4_endpoint_velocity_error"] <=
                                 gates["fine_rk4_endpoint_velocity_error_max"] for row in rows),
        "refinement": all(row["coarse_to_fine_error_ratio"] >=
                          gates["coarse_to_fine_endpoint_position_error_ratio_min"] for row in rows),
        "energy": all(row["fine_rk4_sampled_diagnostics"]["relative_energy_drift"] <=
                      gates["fine_rk4_relative_energy_drift_max"] for row in rows),
        "angular_momentum": all(row["fine_rk4_sampled_diagnostics"]["absolute_angular_momentum_drift"] <=
                                gates["fine_rk4_absolute_angular_momentum_drift_max"] for row in rows),
        "center_of_mass": all(row["fine_rk4_sampled_diagnostics"]["center_of_mass_drift"] <=
                              gates["fine_rk4_center_of_mass_drift_max"] for row in rows),
        "separation": all(row["fine_rk4_sampled_diagnostics"]["sampled_minimum_pair_separation"] >
                          gates["minimum_pair_separation_min"]
                          and row["reference_sampled_minimum_pair_separation"] >
                          gates["minimum_pair_separation_min"]
                          and row["reference_inward_threshold_crossings"] == 0 for row in rows),
        "one_period_closure": rows[0]["published_state_closure_error"] <=
                              gates["one_period_published_state_closure_error_max"],
        "negative_repulsive_force": negative_error >= gates["negative_repulsive_position_error_min"],
        "compute_budget": total_rhs_calls <= config["compute_budget"]["dop853_rhs_calls_total_max"]
                          and total_fixed_steps <= config["compute_budget"]["fixed_rk4_steps_total_max"],
    }
    return {"schema_version": "t3-figure-eight-audit-v1",
            "status": "passed-finite-published-figure-eight-numerics-only" if all(checks.values()) else "failed",
            "protocol_sha256": PROTOCOL_SHA256,
            "preregistration_commit": PREREGISTRATION_COMMIT,
            "source_paper_sha256": config["source"]["download_sha256"],
            "environment": environment,
            "solvers": config["solvers"],
            "engineering_gates": gates,
            "compute_budget": config["compute_budget"],
            "observed_budget": {"dop853_rhs_calls_total": total_rhs_calls,
                                "fixed_rk4_steps_total": total_fixed_steps},
            "rows": rows,
            "negative_repulsive_position_error": negative_error,
            "negative_control_rhs_calls": {"attractive": attractive["rhs_calls"],
                                           "repulsive": repulsive["rhs_calls"]},
            "checks": checks,
            "source_files": [_source(path) for path in SOURCE_FILES],
            "scientific_boundaries": config["scientific_boundaries"]}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true")
    mode.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    audit = build_audit()
    if args.write:
        if AUDIT.exists():
            existing = json.loads(AUDIT.read_text(encoding="utf-8"))
            existing.pop("recorded_at", None)
            if existing != audit:
                raise ValueError("refusing to overwrite a different figure-eight audit")
        audit["recorded_at"] = datetime.now(timezone.utc).isoformat()
        AUDIT.write_text(json.dumps(audit, indent=2, sort_keys=True, allow_nan=False) + "\n",
                         encoding="utf-8", newline="\n")
    else:
        saved = json.loads(AUDIT.read_text(encoding="utf-8"))
        timestamp = saved.pop("recorded_at", None)
        if not timestamp or datetime.fromisoformat(timestamp).tzinfo is None or saved != audit:
            raise ValueError("figure-eight audit differs from recomputation or source bytes")
    print(json.dumps({"status": audit["status"], "checks": audit["checks"],
                      "observed_budget": audit["observed_budget"],
                      "rows": [{"id": row["id"],
                                "fine_position_error": row["fine_rk4_endpoint_position_error"],
                                "minimum_separation": row["reference_sampled_minimum_pair_separation"]}
                               for row in audit["rows"]]}, indent=2))
    if audit["status"] == "failed":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
