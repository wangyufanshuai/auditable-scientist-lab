"""Recompute a dependency-free, bounded T1 two-body propagation audit."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from math import hypot, isfinite, sqrt
from pathlib import Path
import platform

from auditable_scientist.tools.numerical import hohmann_baseline
from auditable_scientist.tools.orbit_integrator import propagate_to_apoapsis


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "artifacts/t1-core-orbit-audit.json"
COARSE_STEPS = 2048
FINE_STEPS = 4096
METRICS = (
    "relative_tof_error", "relative_final_position_error", "relative_final_velocity_error",
    "relative_energy_drift", "relative_angular_momentum_drift", "relative_step_delta",
)
GATES = {key + "_max": 1e-9 for key in METRICS}


def _fingerprint(path: Path) -> dict[str, str | int]:
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "bytes": path.stat().st_size,
    }


def build_audit() -> dict:
    fixture = json.loads((ROOT / "examples/hohmann/dataset.json").read_text(encoding="utf-8"))
    cases = fixture["cases"]
    if (fixture.get("schema_version") != "hohmann-dataset-v1" or len(cases) != 9
            or [row["split"] for row in cases] != ["train"] * 6 + ["holdout"] * 3):
        raise ValueError("T1 synthetic fixture and declared splits differ")
    rows = []
    for item in cases:
        inputs = (item["r1_km"], item["r2_km"], item["mu_km3_s2"])
        coarse = propagate_to_apoapsis(*inputs, steps=COARSE_STEPS)
        fine = propagate_to_apoapsis(*inputs, steps=FINE_STEPS)
        if not coarse["event_detected"] or not fine["event_detected"]:
            raise ValueError(f"no first apoapsis for {item['case_id']}")
        reference = hohmann_baseline(*inputs)
        ratio = item["r2_km"] / item["r1_km"]
        transfer_a = (1 + ratio) / 2
        final_speed = sqrt(2 / ratio - 1 / transfer_a)
        x, y, vx, vy = fine["event_state"]
        time_s = fine["event_time_s"]
        coarse_time_s = coarse["event_time_s"]
        rows.append({
            "case_id": item["case_id"], "split": item["split"],
            "r1_km": inputs[0], "r2_km": inputs[1], "mu_km3_s2": inputs[2],
            "coarse_steps_executed": coarse["steps_executed"],
            "fine_steps_executed": fine["steps_executed"],
            "coarse_tof_days": coarse_time_s / 86400,
            "numerical_tof_days": time_s / 86400,
            "analytic_tof_days": reference.time_of_flight_days,
            "relative_tof_error": abs(time_s - reference.time_of_flight_s) / reference.time_of_flight_s,
            "relative_final_position_error": hypot(x + ratio, y) / ratio,
            "relative_final_velocity_error": hypot(vx, vy + final_speed) / final_speed,
            "relative_energy_drift": fine["relative_energy_drift"],
            "relative_angular_momentum_drift": fine["relative_angular_momentum_drift"],
            "relative_step_delta": abs(time_s - coarse_time_s) / reference.time_of_flight_s,
            "time_error_shrank": abs(time_s - reference.time_of_flight_s)
            < abs(coarse_time_s - reference.time_of_flight_s) / 4,
        })
    wrong_gravity = propagate_to_apoapsis(
        cases[0]["r1_km"], cases[0]["r2_km"], cases[0]["mu_km3_s2"],
        steps=FINE_STEPS, gravity_sign=-1,
    )
    summary = {metric: max(row[metric] for row in rows) for metric in METRICS}
    checks = {
        "nine_apoapses_detected": len(rows) == 9,
        "all_errors_bounded": all(isfinite(summary[key]) and summary[key] <= GATES[key + "_max"] for key in METRICS),
        "time_error_shrinks_on_refinement": all(row["time_error_shrank"] for row in rows),
        "repulsive_force_rejected": wrong_gravity == {"event_detected": False, "steps_executed": FINE_STEPS},
        "bounded_compute": all(row["coarse_steps_executed"] <= COARSE_STEPS
                               and row["fine_steps_executed"] <= FINE_STEPS for row in rows),
    }
    sources = [
        ROOT / "scripts/verify_t1_core_orbit.py",
        ROOT / "src/auditable_scientist/tools/orbit_integrator.py",
        ROOT / "src/auditable_scientist/tools/numerical.py",
        ROOT / "examples/hohmann/dataset.json",
        ROOT / "docs/T1_CORE_ORBIT.md",
    ]
    return {
        "schema_version": "t1-core-orbit-audit-v1",
        "status": "verified-synthetic-two-body-only" if all(checks.values()) else "failed",
        "scope": "Nine synthetic outward circular-to-circular transfers; event-detected planar two-body propagation",
        "solver": {"method": "pure-python-fixed-step-rk4", "coarse_steps": COARSE_STEPS,
                   "fine_steps": FINE_STEPS, "event_bisections": 40,
                   "search_window": "four-transfer-half-periods"},
        "environment": {"python": platform.python_version(), "implementation": platform.python_implementation()},
        "gates": GATES, "rows": rows, "summary": summary, "checks": checks,
        "negative_control": {"gravity_sign": -1, **wrong_gravity},
        "source_files": [_fingerprint(path) for path in sources],
        "boundaries": {
            "core_cli_run_integrated": False,
            "independent_time_propagation": True,
            "independent_orbit_derivation": False,
            "real_data": False,
            "dated_ephemeris": False,
            "mission_trajectory_validated": False,
            "publication_ready": False,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--write", action="store_true")
    action.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    current = build_audit()
    if current["status"] != "verified-synthetic-two-body-only":
        raise SystemExit(f"T1 core numerical audit failed: {current['checks']}")
    if args.write:
        current["recorded_at"] = datetime.now(timezone.utc).isoformat()
        OUTPUT.write_text(json.dumps(current, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    else:
        saved = json.loads(OUTPUT.read_text(encoding="utf-8"))
        timestamp = saved.pop("recorded_at", None)
        if not isinstance(timestamp, str) or datetime.fromisoformat(timestamp).tzinfo is None or saved != current:
            raise ValueError("T1 core orbit audit differs from its source, environment, or recomputation")
    print(json.dumps({"status": current["status"], "checks": current["checks"], "summary": current["summary"]}, sort_keys=True))


if __name__ == "__main__":
    main()
