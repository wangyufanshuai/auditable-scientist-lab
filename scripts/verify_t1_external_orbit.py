"""Optional pinned-SciPy, event-driven two-body cross-check for T1 Hohmann TOF."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from math import hypot, pi, sqrt
from pathlib import Path

import numpy as np
from scipy.integrate import solve_ivp

from auditable_scientist.tools.numerical import hohmann_baseline
from verify_t1_nasa_factsheets import verify_snapshot
from verify_t3_external_scipy import sha256, verify_environment


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "artifacts/t1-external-orbit-audit.json"
RTOL = 3e-12
ATOL = 3e-14
GATES = {
    "case_count": 10,
    "relative_tof_error_max": 1e-9,
    "relative_final_position_error_max": 1e-9,
    "relative_final_velocity_error_max": 1e-9,
    "relative_energy_drift_max": 1e-9,
    "relative_angular_momentum_drift_max": 1e-9,
}


def integrate_to_apoapsis(r1_km: float, r2_km: float, mu_km3_s2: float, *, gravity_sign: int = 1) -> dict[str, float | int | bool]:
    """Integrate dimensionless Cartesian motion; detect apocenter without supplying TOF."""
    if not (0 < r1_km < r2_km and mu_km3_s2 > 0) or gravity_sign not in (-1, 1):
        raise ValueError("outward two-body case and signed gravity are required")
    radius_ratio = r2_km / r1_km
    transfer_a = (1 + radius_ratio) / 2
    initial_tangential_speed = sqrt(2 - 1 / transfer_a)
    initial_state = np.array([1.0, 0.0, 0.0, initial_tangential_speed])

    def acceleration(_time: float, state: np.ndarray) -> tuple[float, float, float, float]:
        x, y, vx, vy = state
        radius_cubed = hypot(x, y) ** 3
        return vx, vy, -gravity_sign * x / radius_cubed, -gravity_sign * y / radius_cubed

    def outward_to_inward(_time: float, state: np.ndarray) -> float:
        return float(state[0] * state[2] + state[1] * state[3])

    outward_to_inward.direction = -1  # type: ignore[attr-defined]
    outward_to_inward.terminal = True  # type: ignore[attr-defined]
    result = solve_ivp(
        acceleration, (0, 4 * pi * sqrt(transfer_a**3)), initial_state,
        method="DOP853", events=outward_to_inward, rtol=RTOL, atol=ATOL,
    )
    if not result.success or result.status not in (0, 1):
        raise ValueError("external two-body integrator failed")
    event_detected = len(result.t_events[0]) == 1
    if not event_detected:
        return {"event_detected": False, "function_calls": int(result.nfev)}
    if gravity_sign != 1 or result.status != 1:
        raise ValueError("unexpected terminal event for the wrong-gravity control")

    x, y, vx, vy = result.y_events[0][0]
    numerical_tof_s = float(result.t_events[0][0]) * sqrt(r1_km**3 / mu_km3_s2)
    reference = hohmann_baseline(r1_km, r2_km, mu_km3_s2)
    expected_final_speed = sqrt(2 / radius_ratio - 1 / transfer_a)
    radii = np.hypot(result.y[0], result.y[1])
    energies = (result.y[2] ** 2 + result.y[3] ** 2) / 2 - 1 / radii
    angular_momenta = result.y[0] * result.y[3] - result.y[1] * result.y[2]
    initial_energy = initial_tangential_speed**2 / 2 - 1
    return {
        "event_detected": True,
        "function_calls": int(result.nfev),
        "numerical_tof_days": numerical_tof_s / 86400,
        "analytic_tof_days": reference.time_of_flight_days,
        "relative_tof_error": abs(numerical_tof_s - reference.time_of_flight_s) / reference.time_of_flight_s,
        "relative_final_position_error": hypot(x + radius_ratio, y) / radius_ratio,
        "relative_final_velocity_error": hypot(vx, vy + expected_final_speed) / expected_final_speed,
        "relative_energy_drift": float(np.max(np.abs(energies - initial_energy))) / abs(initial_energy),
        "relative_angular_momentum_drift": float(np.max(np.abs(angular_momenta - initial_tangential_speed))) / initial_tangential_speed,
    }


def build_receipt() -> dict[str, object]:
    environment = verify_environment()
    fixture_path = ROOT / "examples/hohmann/dataset.json"
    dataset = json.loads(fixture_path.read_text(encoding="utf-8"))
    cases = dataset["cases"]
    if (dataset.get("schema_version") != "hohmann-dataset-v1"
            or len(cases) != 9
            or [item["split"] for item in cases] != ["train"] * 6 + ["holdout"] * 3):
        raise ValueError("T1 source fixture or declared splits differ")
    snapshot = json.loads((ROOT / "artifacts/t1-nasa-factsheet-snapshot.json").read_text(encoding="utf-8"))
    nasa_audit = verify_snapshot(snapshot)
    if nasa_audit != json.loads((ROOT / "artifacts/t1-nasa-factsheet-audit.json").read_text(encoding="utf-8")):
        raise ValueError("NASA short-row snapshot is not the accepted offline audit")
    mu = cases[0]["mu_km3_s2"]
    if any(item["mu_km3_s2"] != mu for item in cases):
        raise ValueError("T1 fixture changes the central parameter across cases")
    orbit_inputs = [
        {"case_id": item["case_id"], "split": item["split"], "r1_km": item["r1_km"], "r2_km": item["r2_km"], "mu_km3_s2": mu}
        for item in cases
    ]
    orbit_inputs.append({
        "case_id": "nasa-rounded-axes", "split": "external-parameter-sensitivity",
        "r1_km": float(nasa_audit["rounded_axes_million_km"]["earth"]) * 1_000_000,
        "r2_km": float(nasa_audit["rounded_axes_million_km"]["mars"]) * 1_000_000,
        "mu_km3_s2": mu,
    })
    rows = []
    for item in orbit_inputs:
        result = integrate_to_apoapsis(item["r1_km"], item["r2_km"], mu)
        if not result["event_detected"]:
            raise ValueError(f"missing apoapsis: {item['case_id']}")
        rows.append({**item, **result})
    wrong_gravity = integrate_to_apoapsis(cases[0]["r1_km"], cases[0]["r2_km"], mu, gravity_sign=-1)
    summary = {
        key: max(row[key] for row in rows)
        for key in (
            "relative_tof_error", "relative_final_position_error", "relative_final_velocity_error",
            "relative_energy_drift", "relative_angular_momentum_drift",
        )
    }
    checks = {
        "ten_apoapses_detected": len(rows) == GATES["case_count"] and all(row["event_detected"] for row in rows),
        "time_agreement": summary["relative_tof_error"] <= GATES["relative_tof_error_max"],
        "position_agreement": summary["relative_final_position_error"] <= GATES["relative_final_position_error_max"],
        "velocity_agreement": summary["relative_final_velocity_error"] <= GATES["relative_final_velocity_error_max"],
        "energy_conservation": summary["relative_energy_drift"] <= GATES["relative_energy_drift_max"],
        "angular_momentum_conservation": summary["relative_angular_momentum_drift"] <= GATES["relative_angular_momentum_drift_max"],
        "repulsive_gravity_rejected": wrong_gravity["event_detected"] is False,
    }
    source_paths = (
        ROOT / "scripts/verify_t1_external_orbit.py",
        ROOT / "scripts/verify_t1_nasa_factsheets.py",
        ROOT / "scripts/verify_t3_external_scipy.py",
        ROOT / "src/auditable_scientist/tools/numerical.py",
        fixture_path,
        ROOT / "artifacts/t1-nasa-factsheet-snapshot.json",
        ROOT / "artifacts/t1-nasa-factsheet-audit.json",
        ROOT / "requirements-t3-scipy-win-py312.txt",
    )
    return {
        "schema_version": "t1-external-orbit-audit-v1",
        "status": "passed-within-circular-two-body-scope" if all(checks.values()) else "failed",
        "scope": "Event-driven, dimensionless, heliocentric two-body apoapsis integration for nine synthetic T1 cases and one NASA-rounded-axis sensitivity case",
        "solver": {"api": "scipy.integrate.solve_ivp", "method": "DOP853", "rtol": RTOL, "atol": ATOL},
        "environment": environment,
        "gates": GATES,
        "rows": rows,
        "summary": summary,
        "checks": checks,
        "negative_control": {"gravity_sign": -1, **wrong_gravity},
        "source_files": [
            {"path": path.relative_to(ROOT).as_posix(), "sha256": sha256(path), "bytes": path.stat().st_size}
            for path in source_paths
        ],
        "boundaries": {
            "core_dependency": False,
            "circular_two_body_numerical_cross_check": True,
            "real_data": False,
            "dated_ephemeris": False,
            "mission_trajectory_validated": False,
            "publication_ready": False,
            "nasa_source_rights_status": "unreviewed-page-specific",
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--write", action="store_true")
    group.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    current = build_receipt()
    if current["status"] != "passed-within-circular-two-body-scope":
        raise SystemExit(f"T1 external orbit audit failed: {current['checks']}")
    if args.write:
        current["recorded_at"] = datetime.now(timezone.utc).isoformat()
        OUTPUT.write_text(json.dumps(current, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    else:
        saved = json.loads(OUTPUT.read_text(encoding="utf-8"))
        recorded_at = saved.pop("recorded_at", None)
        if not recorded_at or datetime.fromisoformat(recorded_at).tzinfo is None or saved != current:
            raise ValueError("T1 external orbit audit differs from pinned environment, inputs, source, or result")
    print(json.dumps({"status": current["status"], "checks": current["checks"], "summary": current["summary"]}, indent=2))


if __name__ == "__main__":
    main()
