"""Bounded, package-installable T3 convergence evaluator.

The evaluator deliberately stays within a dimensionless linear harmonic
oscillator grid.  It is useful for checking solver order, conservation drift,
and a negative control after installation, but it is not a general dynamics
or mission-validity test.
"""

from __future__ import annotations

import hashlib
import json
import math
from datetime import datetime
from pathlib import Path
from typing import Any

from auditable_scientist.runtime.paths import source_path

from .dynamics import DynamicsCase, _energy, _euler, _verlet
from .reference_rk4 import rk4_oscillator


SCHEMA_VERSION = "t3-sweep-v1"
OMEGAS = (0.7, 1.0, 1.6)
INITIAL_STATES = ((1.0, 0.0), (0.8, 0.25), (-1.2, -0.3))
STEPS = (128, 256, 512)
END_PHASE = 7 * math.pi / 2
GATES = {
    "verlet_order_ratio_min": 3.5,
    "verlet_order_ratio_max": 4.5,
    "rk4_order_ratio_min": 12.0,
    "rk4_order_ratio_max": 20.0,
    "fine_verlet_position_error_max": 1e-3,
    "fine_rk4_position_error_max": 1e-6,
    "fine_verlet_energy_drift_max": 1e-3,
    "fine_rk4_energy_drift_max": 1e-6,
    "fine_backend_position_delta_max": 1e-3,
    "fine_euler_energy_drift_min": 1e-2,
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _source_fingerprint(relative: str) -> dict[str, object]:
    path = source_path(relative)
    return {"path": relative, "bytes": path.stat().st_size, "sha256": _sha256(path)}


def _convergence_ratio(coarse: float, fine: float) -> float:
    if coarse <= 0 or fine <= 0:
        raise ValueError("nonpositive error makes convergence order undefined")
    return coarse / fine


def build_receipt() -> dict[str, Any]:
    """Run the fixed T3 grid and return a JSON-serializable receipt."""

    rows: list[dict[str, Any]] = []
    convergence: list[dict[str, Any]] = []
    for omega in OMEGAS:
        for state_index, (x0, v0) in enumerate(INITIAL_STATES, start=1):
            group: list[dict[str, Any]] = []
            for steps in STEPS:
                case = DynamicsCase(
                    case_id=f"omega-{omega}-state-{state_index}-steps-{steps}",
                    split="holdout",
                    omega=omega,
                    dt=END_PHASE / (omega * steps),
                    steps=steps,
                    x0=x0,
                    v0=v0,
                )
                initial_energy = _energy(x0, v0, omega)
                amplitude = math.hypot(x0, v0 / omega)
                verlet_x, exact_x, verlet_drift = _verlet(case)
                rk4_x, _, rk4_drift = rk4_oscillator(x0, v0, omega, case.dt, steps)
                _, euler_energy = _euler(case)
                row = {
                    "case_id": case.case_id,
                    "omega": omega,
                    "x0": x0,
                    "v0": v0,
                    "steps": steps,
                    "dt": case.dt,
                    "omega_dt": omega * case.dt,
                    "end_phase": END_PHASE,
                    "verlet_position_error": abs(verlet_x - exact_x) / amplitude,
                    "rk4_position_error": abs(rk4_x - exact_x) / amplitude,
                    "verlet_energy_drift": verlet_drift / initial_energy,
                    "rk4_energy_drift": rk4_drift / initial_energy,
                    "backend_position_delta": abs(verlet_x - rk4_x) / amplitude,
                    "euler_energy_drift": abs(euler_energy - initial_energy) / initial_energy,
                }
                rows.append(row)
                group.append(row)
            convergence.append({
                "omega": omega,
                "state_index": state_index,
                "verlet_ratios": [
                    _convergence_ratio(group[i]["verlet_position_error"], group[i + 1]["verlet_position_error"])
                    for i in (0, 1)
                ],
                "rk4_ratios": [
                    _convergence_ratio(group[i]["rk4_position_error"], group[i + 1]["rk4_position_error"])
                    for i in (0, 1)
                ],
            })

    fine_rows = [row for row in rows if row["steps"] == STEPS[-1]]
    all_verlet_ratios = [ratio for item in convergence for ratio in item["verlet_ratios"]]
    all_rk4_ratios = [ratio for item in convergence for ratio in item["rk4_ratios"]]
    summary = {
        "case_count": len(rows),
        "min_verlet_ratio": min(all_verlet_ratios),
        "max_verlet_ratio": max(all_verlet_ratios),
        "min_rk4_ratio": min(all_rk4_ratios),
        "max_rk4_ratio": max(all_rk4_ratios),
        "max_fine_verlet_position_error": max(row["verlet_position_error"] for row in fine_rows),
        "max_fine_rk4_position_error": max(row["rk4_position_error"] for row in fine_rows),
        "max_fine_verlet_energy_drift": max(row["verlet_energy_drift"] for row in fine_rows),
        "max_fine_rk4_energy_drift": max(row["rk4_energy_drift"] for row in fine_rows),
        "max_fine_backend_position_delta": max(row["backend_position_delta"] for row in fine_rows),
        "min_fine_euler_energy_drift": min(row["euler_energy_drift"] for row in fine_rows),
    }
    checks = {
        "verlet_second_order": GATES["verlet_order_ratio_min"] <= summary["min_verlet_ratio"] <= GATES["verlet_order_ratio_max"]
        and GATES["verlet_order_ratio_min"] <= summary["max_verlet_ratio"] <= GATES["verlet_order_ratio_max"],
        "rk4_fourth_order": GATES["rk4_order_ratio_min"] <= summary["min_rk4_ratio"] <= GATES["rk4_order_ratio_max"]
        and GATES["rk4_order_ratio_min"] <= summary["max_rk4_ratio"] <= GATES["rk4_order_ratio_max"],
        "fine_position_error": summary["max_fine_verlet_position_error"] <= GATES["fine_verlet_position_error_max"]
        and summary["max_fine_rk4_position_error"] <= GATES["fine_rk4_position_error_max"],
        "fine_energy_drift": summary["max_fine_verlet_energy_drift"] <= GATES["fine_verlet_energy_drift_max"]
        and summary["max_fine_rk4_energy_drift"] <= GATES["fine_rk4_energy_drift_max"],
        "fine_backend_agreement": summary["max_fine_backend_position_delta"] <= GATES["fine_backend_position_delta_max"],
        "euler_negative_control": summary["min_fine_euler_energy_drift"] >= GATES["fine_euler_energy_drift_min"],
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "scope": "unit-mass linear harmonic oscillator; dimensionless normalized errors",
        "grid": {
            "omegas": list(OMEGAS),
            "initial_states": [list(state) for state in INITIAL_STATES],
            "steps": list(STEPS),
            "end_phase": END_PHASE,
        },
        "gates": GATES,
        "rows": rows,
        "convergence": convergence,
        "summary": summary,
        "checks": checks,
        "passed": all(checks.values()),
        "source_files": [
            _source_fingerprint("src/auditable_scientist/tracks/convergence.py"),
            _source_fingerprint("src/auditable_scientist/tracks/dynamics.py"),
            _source_fingerprint("src/auditable_scientist/tracks/reference_rk4.py"),
        ],
        "boundaries": {
            "fixture_reproduction": True,
            "real_mission_validation": False,
            "multi_body_validation": False,
            "external_solver_validation": False,
        },
    }


def verify_saved_receipt(path: str | Path) -> dict[str, Any]:
    """Verify a saved checkout receipt against the installed evaluator code."""

    saved = json.loads(Path(path).read_text(encoding="utf-8"))
    recorded_at = saved.pop("recorded_at", None)
    if not recorded_at or datetime.fromisoformat(recorded_at).tzinfo is None:
        raise ValueError("T3 sweep audit timestamp is missing or lacks timezone")
    expected = build_receipt()
    if saved != expected or not expected["passed"]:
        raise ValueError("T3 sweep audit differs from the current grid, gates, source, or solver outputs")
    return expected


__all__ = ["build_receipt", "verify_saved_receipt", "SCHEMA_VERSION"]
