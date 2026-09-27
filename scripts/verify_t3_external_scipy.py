"""Optional, separately installed SciPy cross-check for the bounded T3 oscillator."""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import math
import platform
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import scipy
from scipy.integrate import solve_ivp

from auditable_scientist.tracks.dynamics import DynamicsCase, _verlet
from auditable_scientist.tracks.reference_rk4 import rk4_oscillator


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "artifacts/t3-external-scipy.json"
LOCK = ROOT / "requirements-t3-scipy-win-py312.txt"
OMEGAS = (0.7, 1.0, 1.6)
INITIAL_STATES = ((1.0, 0.0), (0.8, 0.25), (-1.2, -0.3))
PHASE = 7 * math.pi / 2
STEPS = 512
RTOL = 1e-11
ATOL = 1e-13
WHEEL_SHA256 = {
    "numpy": "c1f9540be57940698ed329904db803cf7a402f3fc200bfe599334c9bd84a40b2",
    "scipy": "5e4d44984abc0020154ea81b247adeddcc3ac5527b975ff798bd1ba0adc513c2",
}
SCIPY_SOURCE_TAG = "v1.18.1"
SCIPY_SOURCE_COMMIT = "c2df8ace0d9859f090e79058b2bd2ffc584f19e6"
SCIPY_LICENSE_SHA256 = "f0f5c56b298ec9795df1199edc328a987242716d14a1bde6813112e22dc15f99"
NUMPY_SOURCE_TAG = "v2.2.6"
NUMPY_SOURCE_COMMIT = "bbb76e7d76c3748fb2747fc3d8e06b944005362a"
NUMPY_LICENSE_SHA256 = "14256cc3a2c9d32ac284da96b937feb44f72dd90bee2317ac3020166846ad99d"
GATES = {
    "position_error_max": 1e-8,
    "velocity_error_max": 1e-8,
    "energy_drift_max": 1e-8,
    "verlet_position_delta_max": 1e-3,
    "rk4_position_delta_max": 1e-6,
    "wrong_sign_position_error_min": 1e-2,
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_environment() -> dict[str, object]:
    actual = {
        "python": platform.python_version(),
        "implementation": platform.python_implementation(),
        "system": platform.system(),
        "machine": platform.machine(),
        "numpy": np.__version__,
        "scipy": scipy.__version__,
    }
    expected = {
        "python": "3.12.3", "implementation": "CPython", "system": "Windows",
        "machine": "AMD64", "numpy": "2.2.6", "scipy": "1.18.1",
    }
    if actual != expected:
        raise ValueError(f"SciPy audit environment differs from pinned version: {actual}")
    lock_text = LOCK.read_text(encoding="utf-8")
    for package, wheel_hash in WHEEL_SHA256.items():
        version = expected[package]
        if f"{package}=={version} --hash=sha256:{wheel_hash}" not in lock_text:
            raise ValueError(f"{package} wheel pin or hash differs")
    license_path = importlib.metadata.distribution("scipy").locate_file("scipy-1.18.1.dist-info/LICENSE.txt")
    if sha256(license_path) != SCIPY_LICENSE_SHA256:
        raise ValueError("installed SciPy license notice differs from the audited wheel")
    numpy_license = importlib.metadata.distribution("numpy").locate_file("numpy-2.2.6.dist-info/LICENSE.txt")
    if sha256(numpy_license) != NUMPY_LICENSE_SHA256:
        raise ValueError("installed NumPy license notice differs from the audited wheel")
    return {
        "platform_and_packages": actual,
        "lock_sha256": sha256(LOCK),
        "wheel_sha256": WHEEL_SHA256,
        "scipy_source_tag": SCIPY_SOURCE_TAG,
        "scipy_source_commit": SCIPY_SOURCE_COMMIT,
        "scipy_installed_license_sha256": SCIPY_LICENSE_SHA256,
        "numpy_source_tag": NUMPY_SOURCE_TAG,
        "numpy_source_commit": NUMPY_SOURCE_COMMIT,
        "numpy_installed_license_sha256": NUMPY_LICENSE_SHA256,
    }


def build_receipt() -> dict[str, object]:
    environment = verify_environment()
    rows: list[dict[str, object]] = []
    for omega in OMEGAS:
        for state_index, (x0, v0) in enumerate(INITIAL_STATES, start=1):
            end_time = PHASE / omega
            times = np.linspace(0.0, end_time, STEPS + 1)
            def oscillator(_time: float, state: np.ndarray) -> tuple[float, float]:
                return state[1], -(omega * omega) * state[0]
            result = solve_ivp(
                oscillator, (0.0, end_time), (x0, v0), method="DOP853",
                t_eval=times, rtol=RTOL, atol=ATOL,
            )
            if not result.success or result.status != 0 or result.y.shape != (2, STEPS + 1):
                raise ValueError(f"SciPy solver failed: omega={omega}, state={state_index}")
            amplitude = math.hypot(x0, v0 / omega)
            initial_energy = 0.5 * (v0 * v0 + (omega * x0) ** 2)
            phase = omega * times
            exact_x = x0 * np.cos(phase) + (v0 / omega) * np.sin(phase)
            exact_v = -omega * x0 * np.sin(phase) + v0 * np.cos(phase)
            energy = 0.5 * (result.y[1] ** 2 + (omega * result.y[0]) ** 2)
            case = DynamicsCase(
                case_id=f"scipy-omega-{omega}-state-{state_index}", split="holdout",
                omega=omega, dt=end_time / STEPS, steps=STEPS, x0=x0, v0=v0,
            )
            verlet_x, _, _ = _verlet(case)
            rk4_x, _, _ = rk4_oscillator(x0, v0, omega, case.dt, STEPS)
            final_x = float(result.y[0, -1])
            rows.append({
                "case_id": case.case_id,
                "omega": omega,
                "x0": x0,
                "v0": v0,
                "success": bool(result.success),
                "function_calls": int(result.nfev),
                "max_position_error": float(np.max(np.abs(result.y[0] - exact_x))) / amplitude,
                "max_velocity_error": float(np.max(np.abs(result.y[1] - exact_v))) / (omega * amplitude),
                "max_energy_drift": float(np.max(np.abs(energy - initial_energy))) / initial_energy,
                "final_verlet_delta": abs(final_x - verlet_x) / amplitude,
                "final_rk4_delta": abs(final_x - rk4_x) / amplitude,
            })
    bad = solve_ivp(
        lambda _time, state: (state[1], state[0]),
        (0.0, PHASE), (1.0, 0.0), method="DOP853", rtol=RTOL, atol=ATOL,
    )
    if not bad.success:
        raise ValueError("wrong-sign negative solver failed before comparison")
    wrong_sign_error = abs(float(bad.y[0, -1]) - math.cos(PHASE))
    summary = {
        "case_count": len(rows),
        "max_position_error": max(row["max_position_error"] for row in rows),
        "max_velocity_error": max(row["max_velocity_error"] for row in rows),
        "max_energy_drift": max(row["max_energy_drift"] for row in rows),
        "max_verlet_position_delta": max(row["final_verlet_delta"] for row in rows),
        "max_rk4_position_delta": max(row["final_rk4_delta"] for row in rows),
        "wrong_sign_position_error": wrong_sign_error,
    }
    checks = {
        "external_solver_success": all(row["success"] for row in rows),
        "analytic_position": summary["max_position_error"] <= GATES["position_error_max"],
        "analytic_velocity": summary["max_velocity_error"] <= GATES["velocity_error_max"],
        "energy_drift": summary["max_energy_drift"] <= GATES["energy_drift_max"],
        "verlet_agreement": summary["max_verlet_position_delta"] <= GATES["verlet_position_delta_max"],
        "rk4_agreement": summary["max_rk4_position_delta"] <= GATES["rk4_position_delta_max"],
        "wrong_sign_rejected": summary["wrong_sign_position_error"] >= GATES["wrong_sign_position_error_min"],
    }
    return {
        "schema_version": "t3-external-scipy-audit-v1",
        "status": "passed-optional-oscillator-cross-check" if all(checks.values()) else "failed",
        "scope": "optional SciPy DOP853 cross-check of nine unit-mass linear-oscillator cases",
        "environment": environment,
        "solver": {"api": "scipy.integrate.solve_ivp", "method": "DOP853", "rtol": RTOL, "atol": ATOL},
        "grid": {"omegas": list(OMEGAS), "initial_states": [list(state) for state in INITIAL_STATES], "steps": STEPS, "end_phase": PHASE},
        "gates": GATES,
        "rows": rows,
        "summary": summary,
        "checks": checks,
        "source_files": [
            {"path": path.relative_to(ROOT).as_posix(), "sha256": sha256(path), "bytes": path.stat().st_size}
            for path in (
                ROOT / "src/auditable_scientist/tracks/dynamics.py",
                ROOT / "src/auditable_scientist/tracks/reference_rk4.py",
                Path(__file__).resolve(),
            )
        ],
        "boundaries": {
            "core_dependency": False,
            "oscillator_grid_validated": True,
            "multi_body_validated": False,
            "real_mission_validated": False,
            "publication_ready": False,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    if args.write == args.verify:
        parser.error("choose exactly one of --write or --verify")
    current = build_receipt()
    if current["status"] != "passed-optional-oscillator-cross-check":
        raise SystemExit(f"optional SciPy cross-check failed: {current['checks']}")
    if args.write:
        current["recorded_at"] = datetime.now(timezone.utc).isoformat()
        OUTPUT.write_text(json.dumps(current, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    else:
        saved = json.loads(OUTPUT.read_text(encoding="utf-8"))
        recorded_at = saved.pop("recorded_at", None)
        if not recorded_at or datetime.fromisoformat(recorded_at).tzinfo is None or saved != current:
            raise ValueError("optional SciPy audit differs from current packages, source, or output")
    print(json.dumps({"status": current["status"], "checks": current["checks"], "summary": current["summary"]}, indent=2))


if __name__ == "__main__":
    main()
