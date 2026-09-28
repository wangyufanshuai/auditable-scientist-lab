"""Recompute the predeclared Pythagorean close-encounter numerical audit."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
from math import hypot, isfinite
from pathlib import Path

import numpy as np
from scipy.integrate import solve_ivp

from verify_t3_external_scipy import verify_environment


ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = ROOT / "docs/T3_PYTHAGOREAN_PROTOCOL.json"
PROTOCOL_SHA256 = "f9848ae9fb01565f51d3560688a6e5cc30cfd09a274dba2d165bfa309de29927"
PREREGISTRATION_COMMIT = "e74409e"
SOURCES = {
    "initial_state": ROOT / "data/references/boekholt_2021_pythagorean.pdf",
    "historical_comparison": ROOT / "data/references/szebehely_peters_1967.pdf",
}
AUDIT = ROOT / "artifacts/t3-pythagorean-audit.json"
SOURCE_FILES = (Path(__file__).resolve(), PROTOCOL, ROOT / "docs/T3_PYTHAGOREAN_PROTOCOL.md",
                ROOT / "scripts/verify_t3_external_scipy.py",
                ROOT / "requirements-t3-scipy-win-py312.txt")


def _source(path: Path) -> dict:
    data = path.read_bytes()
    return {"path": path.relative_to(ROOT).as_posix(), "sha256": sha256(data).hexdigest(),
            "bytes": len(data)}


def _config() -> dict:
    if sha256(PROTOCOL.read_bytes()).hexdigest() != PROTOCOL_SHA256:
        raise ValueError("precommitted Pythagorean protocol bytes differ")
    config = json.loads(PROTOCOL.read_text(encoding="utf-8"))
    if (config["schema_version"] != "t3-pythagorean-protocol-v1"
            or config["scientific_boundaries"]["claim_status"] != "unverified"
            or config["scientific_boundaries"]["chaotic_regime_validated"] is not False):
        raise ValueError("Pythagorean scientific boundary differs")
    for name, path in SOURCES.items():
        if sha256(path.read_bytes()).hexdigest() != config["source"][name]["local_pdf_sha256"]:
            raise ValueError(f"Pythagorean source PDF differs: {name}")
    return config


def _initial(config: dict, offset: float) -> list[float]:
    system = config["system"]
    positions = [list(point) for point in system["initial_positions"]]
    positions[0][0] += offset
    return [float(x) for point in positions for x in point] + [
        float(x) for point in system["initial_velocities"] for x in point]


def _minimum_pair(state: list[float] | np.ndarray) -> tuple[float, int]:
    return min((hypot(float(state[2*i]-state[2*j]), float(state[2*i+1]-state[2*j+1])),
                3*i+j) for i, j in ((0, 1), (0, 2), (1, 2)))


def _invariants(state: list[float] | np.ndarray, masses: list[float], g: float,
                initial_center: tuple[float, float]) -> dict[str, float]:
    energy = sum(0.5*m*(float(state[6+2*i])**2 + float(state[7+2*i])**2)
                 for i, m in enumerate(masses))
    for i, j in ((0, 1), (0, 2), (1, 2)):
        distance = hypot(float(state[2*i]-state[2*j]), float(state[2*i+1]-state[2*j+1]))
        energy -= g*masses[i]*masses[j]/distance
    angular = sum(m*(float(state[2*i])*float(state[7+2*i])
                     - float(state[2*i+1])*float(state[6+2*i]))
                  for i, m in enumerate(masses))
    center = tuple(sum(m*float(state[2*i+axis]) for i, m in enumerate(masses))/sum(masses)
                   for axis in (0, 1))
    return {"energy": energy, "angular_momentum": angular,
            "center_of_mass_drift": hypot(center[0]-initial_center[0],
                                           center[1]-initial_center[1])}


def _initial_center(initial: list[float], masses: list[float]) -> tuple[float, float]:
    return tuple(sum(m*initial[2*i+axis] for i, m in enumerate(masses))/sum(masses)
                 for axis in (0, 1))


def _point_error(a: list[float] | np.ndarray, b: list[float] | np.ndarray,
                 offset: int, scale: float) -> float:
    return max(hypot(float(a[offset+2*i]-b[offset+2*i]),
                     float(a[offset+2*i+1]-b[offset+2*i+1]))/scale for i in range(3))


def _reference(config: dict, initial: list[float], *, repulsive: bool = False,
               end: float | None = None) -> dict:
    masses = config["system"]["masses"]
    g = config["system"]["gravitational_constant"]*(-1 if repulsive else 1)
    cfg = config["solvers"]
    threshold = config["collision_monitor"]["minimum_pair_separation"]
    final_time = end if end is not None else config["sampling"]["maximum_time"]

    def derivative(_t: float, state: np.ndarray) -> np.ndarray:
        result = np.zeros(12)
        result[:6] = state[6:]
        for i, j in ((0, 1), (0, 2), (1, 2)):
            difference = state[2*j:2*j+2]-state[2*i:2*i+2]
            radius = hypot(float(difference[0]), float(difference[1]))
            if radius <= 0 or not isfinite(radius):
                raise ValueError("DOP853 encountered collision or nonfinite radius")
            acceleration = g*difference/radius**3
            result[6+2*i:8+2*i] += masses[j]*acceleration
            result[6+2*j:8+2*j] -= masses[i]*acceleration
        return result

    events = []
    if not repulsive:
        for i, j in ((0, 1), (0, 2), (1, 2)):
            def event(_t: float, state: np.ndarray, left: int = i, right: int = j) -> float:
                return hypot(float(state[2*left]-state[2*right]),
                             float(state[2*left+1]-state[2*right+1]))-threshold
            event.direction = -1  # type: ignore[attr-defined]
            event.terminal = True  # type: ignore[attr-defined]
            events.append(event)
    solution = solve_ivp(derivative, (0.0, final_time), np.asarray(initial),
                         method="DOP853", rtol=cfg["external_reference_rtol"],
                         atol=cfg["external_reference_atol"],
                         max_step=cfg["external_reference_max_step"],
                         dense_output=True, events=events if events else None)
    if not solution.success or solution.sol is None or not np.all(np.isfinite(solution.y)):
        raise ValueError("DOP853 Pythagorean reference failed")
    event_rows = [(float(group[0]), idx) for idx, group in enumerate(solution.t_events)
                  if len(group)] if solution.t_events is not None else []
    if len(event_rows) > 1:
        raise ValueError("DOP853 reported simultaneous terminal close approaches")
    event_time, event_pair = event_rows[0] if event_rows else (None, None)
    sample_times = [] if repulsive or end is not None else config["sampling"]["comparison_times"]
    if sample_times and max(sample_times) >= float(solution.t[-1]):
        raise ValueError("DOP853 guard triggered before comparison horizon")
    initial_center = _initial_center(initial, masses)
    baseline = _invariants(initial, masses, g, initial_center)
    diagnostic = {"relative_energy_drift": 0.0, "angular_momentum_drift": 0.0,
                  "center_of_mass_drift": 0.0,
                  "sampled_minimum_pair_separation": _minimum_pair(initial)[0]}
    for k in range(solution.y.shape[1]):
        state = solution.y[:, k]
        current = _invariants(state, masses, g, initial_center)
        diagnostic["relative_energy_drift"] = max(diagnostic["relative_energy_drift"],
            abs(current["energy"]-baseline["energy"])/abs(baseline["energy"]))
        diagnostic["angular_momentum_drift"] = max(diagnostic["angular_momentum_drift"],
            abs(current["angular_momentum"]-baseline["angular_momentum"]))
        diagnostic["center_of_mass_drift"] = max(diagnostic["center_of_mass_drift"],
            current["center_of_mass_drift"])
        diagnostic["sampled_minimum_pair_separation"] = min(
            diagnostic["sampled_minimum_pair_separation"], _minimum_pair(state)[0])
    return {"samples": {str(t): solution.sol(t).tolist() for t in sample_times},
            "final_state": solution.y[:, -1].tolist(), "end_time": float(solution.t[-1]),
            "event_time": event_time, "event_pair": event_pair,
            "rhs_calls": int(solution.nfev), "diagnostics": diagnostic}


def _adaptive_rk4(config: dict, initial: list[float]) -> dict:
    """Independent per-body force and step-doubling RK4; no SciPy RHS is reused."""
    masses = config["system"]["masses"]
    g = config["system"]["gravitational_constant"]
    solver = config["solvers"]
    threshold = config["collision_monitor"]["minimum_pair_separation"]
    targets = [*config["sampling"]["comparison_times"], config["sampling"]["maximum_time"]]
    budget = config["compute_budget"]
    rhs_calls = attempts = 0

    def derivative(y: list[float]) -> list[float]:
        nonlocal rhs_calls
        rhs_calls += 1
        if rhs_calls > budget["independent_rhs_calls_total_max"]:
            raise ValueError("adaptive RK4 RHS budget exceeded")
        result = y[6:].copy()
        for i in range(3):
            ax = ay = 0.0
            for j in range(3):
                if i == j:
                    continue
                dx, dy = y[2*j]-y[2*i], y[2*j+1]-y[2*i+1]
                radius = hypot(dx, dy)
                if radius <= 0 or not isfinite(radius):
                    raise ValueError("adaptive RK4 encountered collision or nonfinite radius")
                factor = g*masses[j]/radius**3
                ax += factor*dx
                ay += factor*dy
            result.extend((ax, ay))
        return result

    def step(y: list[float], h: float) -> list[float]:
        k1 = derivative(y)
        k2 = derivative([v+h*s/2 for v, s in zip(y, k1)])
        k3 = derivative([v+h*s/2 for v, s in zip(y, k2)])
        k4 = derivative([v+h*s for v, s in zip(y, k3)])
        return [v+h*(a+2*b+2*c+d)/6 for v, a, b, c, d in zip(y, k1, k2, k3, k4)]

    y = initial.copy()
    time = 0.0
    h = solver["independent_backend_initial_step"]
    center = _initial_center(initial, masses)
    baseline = _invariants(initial, masses, g, center)
    diagnostics = {"relative_energy_drift": 0.0, "angular_momentum_drift": 0.0,
                   "center_of_mass_drift": 0.0,
                   "sampled_minimum_pair_separation": _minimum_pair(y)[0]}
    samples = {}
    event_time = event_pair = None
    accepted = rejected = 0
    for target in targets:
        while time < target-1e-14:
            attempts += 1
            if attempts > budget["independent_step_attempts_total_max"]:
                raise ValueError("adaptive RK4 step budget exceeded")
            h = min(h, target-time, solver["independent_backend_max_step"])
            if h < solver["independent_backend_min_step"]:
                raise ValueError("adaptive RK4 minimum step reached")
            full = step(y, h)
            mid = step(y, h/2)
            half = step(mid, h/2)
            error = max(abs(a-b)/(15*(solver["independent_backend_atol"]
                         + solver["independent_backend_rtol"]*max(abs(x), abs(a))))
                        for x, a, b in zip(y, half, full))
            if not isfinite(error):
                raise ValueError("adaptive RK4 nonfinite local error")
            factor = 3.0 if error == 0 else max(0.2, min(3.0, 0.9*error**(-0.2)))
            if error > 1:
                rejected += 1
                h *= min(factor, 0.8)
                continue
            new = [a+(a-b)/15 for a, b in zip(half, full)]
            if not all(isfinite(v) for v in new):
                raise ValueError("adaptive RK4 nonfinite state")
            old_separation, _ = _minimum_pair(y)
            new_separation, pair = _minimum_pair(new)
            if old_separation > threshold >= new_separation:
                fraction = (old_separation-threshold)/(old_separation-new_separation)
                event_time = time+h*fraction
                event_pair = ((0, 1), (0, 2), (1, 2)).index(
                    ((pair//3), (pair % 3)))
                y = [a+fraction*(b-a) for a, b in zip(y, new)]
                time = event_time
                break
            y = new
            time = target if abs(time+h-target) <= 1e-14 else time+h
            accepted += 1
            current = _invariants(y, masses, g, center)
            diagnostics["relative_energy_drift"] = max(diagnostics["relative_energy_drift"],
                abs(current["energy"]-baseline["energy"])/abs(baseline["energy"]))
            diagnostics["angular_momentum_drift"] = max(diagnostics["angular_momentum_drift"],
                abs(current["angular_momentum"]-baseline["angular_momentum"]))
            diagnostics["center_of_mass_drift"] = max(diagnostics["center_of_mass_drift"],
                current["center_of_mass_drift"])
            diagnostics["sampled_minimum_pair_separation"] = min(
                diagnostics["sampled_minimum_pair_separation"], new_separation)
            h *= factor
        if event_time is not None:
            break
        if target in config["sampling"]["comparison_times"]:
            samples[str(target)] = y.copy()
    if set(samples) != {str(t) for t in config["sampling"]["comparison_times"]}:
        raise ValueError("adaptive RK4 guard triggered before comparison horizon")
    return {"samples": samples, "final_state": y, "end_time": time,
            "event_time": event_time, "event_pair": event_pair,
            "rhs_calls": rhs_calls, "step_attempts": attempts,
            "accepted_steps": accepted, "rejected_steps": rejected,
            "diagnostics": diagnostics}


def build_audit() -> dict:
    config = _config()
    environment = verify_environment()
    versions = environment.get("platform_and_packages", {})
    if versions.get("scipy") != "1.18.1" or versions.get("numpy") != "2.2.6":
        raise ValueError("pinned Pythagorean SciPy/NumPy environment differs")
    system = config["system"]
    masses = system["masses"]
    initial = _initial(config, 0.0)
    initial_energy = _invariants(initial, masses, system["gravitational_constant"],
                                  _initial_center(initial, masses))["energy"]
    if (abs(initial_energy-system["initial_energy"]) > 1e-13
            or _initial_center(initial, masses) != (0.0, 0.0)):
        raise ValueError("Pythagorean initial invariants differ")
    rows = []
    total_external = total_independent = total_attempts = 0
    for scenario in config["scenarios"]:
        state = _initial(config, scenario["body_zero_x_offset"])
        reference = _reference(config, state)
        independent = _adaptive_rk4(config, state)
        total_external += reference["rhs_calls"]
        total_independent += independent["rhs_calls"]
        total_attempts += independent["step_attempts"]
        errors = []
        for time in config["sampling"]["comparison_times"]:
            left, right = reference["samples"][str(time)], independent["samples"][str(time)]
            errors.append({"time": time,
                           "position": _point_error(left, right, 0, system["position_normalizer"]),
                           "velocity": _point_error(left, right, 6, system["velocity_normalizer"])})
        rows.append({"id": scenario["id"], "body_zero_x_offset": scenario["body_zero_x_offset"],
                     "reference": reference, "independent": independent,
                     "comparison_errors": errors})
    negative = _reference(config, initial, repulsive=True, end=1.0)
    attractive = _reference(config, initial, end=1.0)
    total_external += negative["rhs_calls"]+attractive["rhs_calls"]
    wrong_force_error = _point_error(negative["final_state"], attractive["final_state"],
                                     0, system["position_normalizer"])
    gates = config["engineering_gates"]
    event_window = config["collision_monitor"]["published_state_event_time_window"]
    checks = {
        "initial_state": abs(initial_energy+769/60) < 1e-13,
        "finite_pre_event_comparison": all(
            all(isfinite(e[k]) and e[k] <= gates[f"comparison_{k}_error_max"]
                for k in ("position", "velocity") for e in row["comparison_errors"])
            for row in rows),
        "external_energy": all(row["reference"]["diagnostics"]["relative_energy_drift"] <=
                               gates["external_relative_energy_drift_max"] for row in rows),
        "independent_energy": all(row["independent"]["diagnostics"]["relative_energy_drift"] <=
                                  gates["independent_relative_energy_drift_max"] for row in rows),
        "angular_momentum": all(max(row[solver]["diagnostics"]["angular_momentum_drift"]
                                    for solver in ("reference", "independent")) <=
                                gates["absolute_angular_momentum_drift_max"] for row in rows),
        "center_of_mass": all(max(row[solver]["diagnostics"]["center_of_mass_drift"]
                                  for solver in ("reference", "independent")) <=
                              gates["center_of_mass_drift_max"] for row in rows),
        "terminal_close_approach": all(row[solver]["event_time"] is not None
                                       for row in rows for solver in ("reference", "independent")),
        "event_pair_match": all(row["reference"]["event_pair"] == row["independent"]["event_pair"]
                                for row in rows),
        "event_time_agreement": all(row["reference"]["event_time"] is not None
                                    and row["independent"]["event_time"] is not None
                                    and abs(row["reference"]["event_time"]
                                            -row["independent"]["event_time"]) <=
                                    gates["event_time_agreement_max"] for row in rows),
        "historical_event_window": rows[0]["reference"]["event_time"] is not None
                                   and event_window[0] <= rows[0]["reference"]["event_time"] <= event_window[1],
        "negative_wrong_force": wrong_force_error >= gates["negative_repulsive_position_error_min"],
        "compute_budget": total_external <= config["compute_budget"]["external_rhs_calls_total_max"]
                          and total_independent <= config["compute_budget"]["independent_rhs_calls_total_max"]
                          and total_attempts <= config["compute_budget"]["independent_step_attempts_total_max"],
    }
    return {"schema_version": "t3-pythagorean-audit-v1",
            "status": "passed-bounded-close-encounter-numerics-only" if all(checks.values()) else "failed",
            "protocol_sha256": PROTOCOL_SHA256,
            "preregistration_commit": PREREGISTRATION_COMMIT,
            "environment": environment,
            "observed_budget": {"external_rhs_calls_total": total_external,
                                "independent_rhs_calls_total": total_independent,
                                "independent_step_attempts_total": total_attempts},
            "rows": rows, "negative_repulsive_position_error": wrong_force_error,
            "negative_control_rhs_calls": {"repulsive": negative["rhs_calls"],
                                           "attractive": attractive["rhs_calls"]},
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
                raise ValueError("refusing to overwrite a different Pythagorean audit")
        audit["recorded_at"] = datetime.now(timezone.utc).isoformat()
        AUDIT.write_text(json.dumps(audit, indent=2, sort_keys=True, allow_nan=False)+"\n",
                         encoding="utf-8", newline="\n")
    else:
        saved = json.loads(AUDIT.read_text(encoding="utf-8"))
        timestamp = saved.pop("recorded_at", None)
        if not timestamp or datetime.fromisoformat(timestamp).tzinfo is None or saved != audit:
            raise ValueError("Pythagorean audit differs from recomputation or source bytes")
    print(json.dumps({"status": audit["status"], "checks": audit["checks"],
                      "observed_budget": audit["observed_budget"],
                      "rows": [{"id": row["id"],
                                "reference_event_time": row["reference"]["event_time"],
                                "independent_event_time": row["independent"]["event_time"],
                                "maximum_position_error": max(e["position"] for e in row["comparison_errors"])}
                               for row in audit["rows"]]}, indent=2))
    if audit["status"] == "failed":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
