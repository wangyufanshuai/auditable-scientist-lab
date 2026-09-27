"""Recompute the bounded T3 oscillator step-size and parameter sweep."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path

from auditable_scientist.tracks.dynamics import DynamicsCase, _energy, _euler, _verlet
from auditable_scientist.tracks.reference_rk4 import rk4_oscillator


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "artifacts/t3-sweep.json"
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


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source_fingerprint(path: Path) -> dict[str, object]:
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": path.stat().st_size, "sha256": sha256(path)}


def convergence_ratio(coarse: float, fine: float) -> float:
    if coarse <= 0 or fine <= 0:
        raise ValueError("nonpositive error makes convergence order undefined")
    return coarse / fine


def build_receipt() -> dict[str, object]:
    rows: list[dict[str, object]] = []
    convergence: list[dict[str, object]] = []
    for omega in OMEGAS:
        for state_index, (x0, v0) in enumerate(INITIAL_STATES, start=1):
            group: list[dict[str, object]] = []
            for steps in STEPS:
                case = DynamicsCase(
                    case_id=f"omega-{omega}-state-{state_index}-steps-{steps}",
                    split="holdout", omega=omega, dt=END_PHASE / (omega * steps),
                    steps=steps, x0=x0, v0=v0,
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
                    convergence_ratio(group[i]["verlet_position_error"], group[i + 1]["verlet_position_error"])
                    for i in (0, 1)
                ],
                "rk4_ratios": [
                    convergence_ratio(group[i]["rk4_position_error"], group[i + 1]["rk4_position_error"])
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
        "verlet_second_order": GATES["verlet_order_ratio_min"] <= summary["min_verlet_ratio"] and summary["max_verlet_ratio"] <= GATES["verlet_order_ratio_max"],
        "rk4_fourth_order": GATES["rk4_order_ratio_min"] <= summary["min_rk4_ratio"] and summary["max_rk4_ratio"] <= GATES["rk4_order_ratio_max"],
        "fine_position_error": summary["max_fine_verlet_position_error"] <= GATES["fine_verlet_position_error_max"] and summary["max_fine_rk4_position_error"] <= GATES["fine_rk4_position_error_max"],
        "fine_energy_drift": summary["max_fine_verlet_energy_drift"] <= GATES["fine_verlet_energy_drift_max"] and summary["max_fine_rk4_energy_drift"] <= GATES["fine_rk4_energy_drift_max"],
        "fine_backend_agreement": summary["max_fine_backend_position_delta"] <= GATES["fine_backend_position_delta_max"],
        "euler_negative_control": summary["min_fine_euler_energy_drift"] >= GATES["fine_euler_energy_drift_min"],
    }
    return {
        "schema_version": "t3-sweep-v1",
        "scope": "unit-mass linear harmonic oscillator; dimensionless normalized errors",
        "grid": {"omegas": list(OMEGAS), "initial_states": [list(state) for state in INITIAL_STATES], "steps": list(STEPS), "end_phase": END_PHASE},
        "gates": GATES,
        "rows": rows,
        "convergence": convergence,
        "summary": summary,
        "checks": checks,
        "passed": all(checks.values()),
        "source_files": [
            source_fingerprint(ROOT / "src/auditable_scientist/tracks/dynamics.py"),
            source_fingerprint(ROOT / "src/auditable_scientist/tracks/reference_rk4.py"),
            source_fingerprint(Path(__file__).resolve()),
        ],
        "boundaries": {
            "fixture_reproduction": True,
            "real_mission_validation": False,
            "multi_body_validation": False,
            "external_solver_validation": False,
        },
    }


def verify_saved() -> dict[str, object]:
    saved = json.loads(OUTPUT.read_text(encoding="utf-8"))
    expected = build_receipt()
    recorded_at = saved.pop("recorded_at", None)
    if not recorded_at or datetime.fromisoformat(recorded_at).tzinfo is None:
        raise ValueError("T3 sweep audit timestamp is missing or lacks timezone")
    if saved != expected or not expected["passed"]:
        raise ValueError("T3 sweep audit differs from the current grid, gates, source, or solver outputs")
    return expected


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true", help="write the current sweep audit")
    parser.add_argument("--verify", action="store_true", help="verify the committed sweep audit")
    args = parser.parse_args()
    if args.write == args.verify:
        parser.error("choose exactly one of --write or --verify")
    if args.write:
        result = build_receipt()
        if not result["passed"]:
            raise SystemExit(f"T3 bounded sweep failed: {result['checks']}")
        result["recorded_at"] = datetime.now(timezone.utc).isoformat()
        OUTPUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    else:
        result = verify_saved()
    print(json.dumps({"passed": result["passed"], "checks": result["checks"], "summary": result["summary"]}, indent=2))


if __name__ == "__main__":
    main()
