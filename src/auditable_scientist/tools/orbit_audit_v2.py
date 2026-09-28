"""Bounded numerical evaluator for a versioned Hohmann CLI Run."""

from __future__ import annotations

from math import hypot, isfinite, sqrt

from ..benchmark.hohmann import HohmannCase
from .numerical import hohmann_baseline
from .orbit_integrator import propagate_to_apoapsis


COARSE_STEPS = 2048
FINE_STEPS = 4096
METRICS = (
    "relative_tof_error", "relative_final_position_error", "relative_final_velocity_error",
    "relative_energy_drift", "relative_angular_momentum_drift", "relative_step_delta",
)
GATES = {f"{metric}_max": 1e-9 for metric in METRICS}


def evaluate_orbit_grid(cases: list[HohmannCase]) -> dict:
    """Check propagation without providing the analytic arrival time to RK4."""
    if not 1 <= len(cases) <= 32:
        raise ValueError("the numerical orbit grid requires 1 to 32 cases")
    rows = []
    for case in cases:
        inputs = (case.r1_km, case.r2_km, case.mu_km3_s2)
        if not all(isfinite(value) for value in (*inputs, case.target_tof_days)):
            raise ValueError(f"nonfinite orbit input: {case.case_id}")
        coarse = propagate_to_apoapsis(*inputs, steps=COARSE_STEPS)
        fine = propagate_to_apoapsis(*inputs, steps=FINE_STEPS)
        if not coarse["event_detected"] or not fine["event_detected"]:
            raise ValueError(f"first apoapsis was not detected: {case.case_id}")
        reference = hohmann_baseline(*inputs)
        ratio = case.r2_km / case.r1_km
        transfer_a = (1 + ratio) / 2
        final_speed = sqrt(2 / ratio - 1 / transfer_a)
        x, y, vx, vy = fine["event_state"]
        numerical_s, coarse_s = fine["event_time_s"], coarse["event_time_s"]
        rows.append({
            "case_id": case.case_id, "split": case.split,
            "r1_km": case.r1_km, "r2_km": case.r2_km, "mu_km3_s2": case.mu_km3_s2,
            "coarse_steps_executed": coarse["steps_executed"],
            "fine_steps_executed": fine["steps_executed"],
            "numerical_tof_days": numerical_s / 86400,
            "analytic_tof_days": reference.time_of_flight_days,
            "relative_tof_error": abs(numerical_s - reference.time_of_flight_s) / reference.time_of_flight_s,
            "relative_final_position_error": hypot(x + ratio, y) / ratio,
            "relative_final_velocity_error": hypot(vx, vy + final_speed) / final_speed,
            "relative_energy_drift": fine["relative_energy_drift"],
            "relative_angular_momentum_drift": fine["relative_angular_momentum_drift"],
            "relative_step_delta": abs(numerical_s - coarse_s) / reference.time_of_flight_s,
            "time_error_shrank": abs(numerical_s - reference.time_of_flight_s)
            < abs(coarse_s - reference.time_of_flight_s) / 4,
        })
    negative = propagate_to_apoapsis(
        cases[0].r1_km, cases[0].r2_km, cases[0].mu_km3_s2,
        steps=FINE_STEPS, gravity_sign=-1,
    )
    summary = {metric: max(row[metric] for row in rows) for metric in METRICS}
    checks = {
        "all_apoapses_detected": len(rows) == len(cases),
        "all_errors_bounded": all(
            isfinite(summary[metric]) and summary[metric] <= GATES[f"{metric}_max"]
            for metric in METRICS
        ),
        "time_error_shrinks_on_refinement": all(row["time_error_shrank"] for row in rows),
        "repulsive_force_rejected": negative == {"event_detected": False, "steps_executed": FINE_STEPS},
        "bounded_compute": all(
            row["coarse_steps_executed"] <= COARSE_STEPS
            and row["fine_steps_executed"] <= FINE_STEPS for row in rows
        ),
    }
    return {
        "schema_version": "t1-orbit-grid-v2",
        "status": "passed-synthetic-two-body" if all(checks.values()) else "failed",
        "case_count": len(rows),
        "solver": {"method": "pure-python-fixed-step-rk4", "coarse_steps": COARSE_STEPS,
                   "fine_steps": FINE_STEPS, "event_bisections": 40},
        "gates": GATES, "rows": rows, "summary": summary, "checks": checks,
        "negative_control": {"gravity_sign": -1, **negative},
        "boundaries": {
            "independent_time_propagation": True,
            "independent_orbit_derivation": False,
            "idealized_circular_two_body_model": True,
            "real_data": False,
            "dated_ephemeris": False,
            "mission_trajectory_validated": False,
            "publication_ready": False,
        },
    }
