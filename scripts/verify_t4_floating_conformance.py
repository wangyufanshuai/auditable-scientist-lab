"""Check finite floating output conformance without changing historical T3 code."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from fractions import Fraction
import hashlib
import json
from math import isfinite
from pathlib import Path

from auditable_scientist.runtime.canonical import canonical_hash
from auditable_scientist.tracks.dynamics import DynamicsCase, _verlet
from auditable_scientist.tracks.proof import ProofPackage


ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = ROOT / "docs/T4_FLOATING_CONFORMANCE_PROTOCOL.json"
AUDIT = ROOT / "artifacts/t4-floating-conformance-audit.json"
SOLVER = ROOT / "src/auditable_scientist/tracks/dynamics.py"
SCRIPT = ROOT / "scripts/verify_t4_floating_conformance.py"
PARENT_FIXTURE = ROOT / "examples/proof/fixture.json"


def _hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _exact(value: str) -> Fraction:
    result = Fraction(value)
    if str(result) != value:
        raise ValueError(f"noncanonical rational: {value}")
    return result


def _exact_step(x: Fraction, v: Fraction, omega: Fraction, dt: Fraction) -> tuple[Fraction, Fraction]:
    acceleration = -(omega * omega) * x
    next_x = x + v * dt + acceleration * dt * dt / 2
    next_acceleration = -(omega * omega) * next_x
    return next_x, v + (acceleration + next_acceleration) * dt / 2


def _energy(x: Fraction, v: Fraction, omega: Fraction) -> Fraction:
    return (v * v + omega * omega * x * x) / 2


def _exact_trajectory(case: dict) -> tuple[Fraction, Fraction, Fraction]:
    omega, dt = _exact(case["omega"]), _exact(case["dt"])
    x, v = _exact(case["x0"]), _exact(case["v0"])
    initial_energy = _energy(x, v, omega)
    max_drift = Fraction(0)
    for _ in range(case["steps"]):
        x, v = _exact_step(x, v, omega, dt)
        max_drift = max(max_drift, abs(_energy(x, v, omega) - initial_energy))
    return x, v, max_drift


def _positive_case(case: dict, bounds: dict[str, Fraction]) -> dict:
    exact_x, _, exact_drift = _exact_trajectory(case)
    actual_x, _, actual_drift = _verlet(DynamicsCase(
        case_id=case["case_id"], split="holdout",
        omega=float(_exact(case["omega"])), dt=float(_exact(case["dt"])),
        x0=float(_exact(case["x0"])), v0=float(_exact(case["v0"])),
        steps=case["steps"],
    ))
    if not isfinite(actual_x) or not isfinite(actual_drift):
        raise ValueError("T3 floating solver returned nonfinite output")
    position_error = abs(Fraction.from_float(actual_x) - exact_x)
    drift_error = abs(Fraction.from_float(actual_drift) - exact_drift)
    return {
        "case_id": case["case_id"], "steps": case["steps"],
        "final_position_error": float(position_error),
        "max_energy_drift_error": float(drift_error),
        "passed": position_error <= bounds["max_final_position_error"]
        and drift_error <= bounds["max_energy_drift_error"],
    }


def _negative_case(case: dict, solver: str, bound: Fraction) -> dict:
    exact_x, _, _ = _exact_trajectory(case)
    omega, dt = float(_exact(case["omega"])), float(_exact(case["dt"]))
    x, v = float(_exact(case["x0"])), float(_exact(case["v0"]))
    for _ in range(case["steps"]):
        if solver == "explicit-euler":
            x, v = x + v * dt, v - omega * omega * x * dt
        else:
            acceleration = -(omega**2) * x
            next_x = x + v * dt + 0.5 * acceleration * dt**2 + 1e-6
            next_acceleration = -(omega**2) * next_x
            x, v = next_x, v + 0.5 * (acceleration + next_acceleration) * dt
    error = abs(Fraction.from_float(x) - exact_x)
    return {"solver": solver, "case_id": case["case_id"],
            "final_position_error": float(error), "rejected": error >= bound}


def evaluate() -> dict:
    protocol = json.loads(PROTOCOL.read_text(encoding="utf-8"))
    boundaries = {
        "finite_horizon_output_conformance": True,
        "finite_error_envelope": True,
        "floating_implementation_proved": False,
        "exact_rational_reference": True,
        "physical_model_validated": False,
        "general_formal_backend": False,
        "real_data": False,
        "publication_ready": False,
        "claim_status": "unverified",
    }
    if (protocol.get("schema_version") != "t4-floating-conformance-protocol-v1"
            or protocol.get("solver") != "velocity-verlet-v1"
            or protocol.get("boundaries") != boundaries):
        raise ValueError("floating conformance protocol identity or boundary differs")
    cases = protocol.get("cases")
    if (not isinstance(cases, list) or len(cases) != 3
            or [case.get("case_id") for case in cases] != ["nominal", "mixed-sign", "small-step"]
            or any(type(case.get("steps")) is not int or not 1 <= case["steps"] <= 1000
                   for case in cases)):
        raise ValueError("floating conformance case inventory differs")
    bounds = {key: _exact(value) for key, value in protocol["bounds"].items()}
    if (set(bounds) != {"max_final_position_error", "max_energy_drift_error",
                       "negative_control_min_final_position_error"}
            or any(value <= 0 for value in bounds.values())):
        raise ValueError("floating conformance bounds differ")
    positives = [_positive_case(case, bounds) for case in cases]
    negatives = [_negative_case(cases[0], solver, bounds["negative_control_min_final_position_error"])
                 for solver in ("explicit-euler", "perturbed-verlet")]
    return {
        "schema_version": "t4-floating-conformance-audit-v1",
        "status": "verified-finite-floating-output-conformance-only",
        "t4_parent_input_hash": canonical_hash(ProofPackage.model_validate(
            json.loads(PARENT_FIXTURE.read_text(encoding="utf-8"))).model_dump(mode="json")),
        "protocol_sha256": _hash(PROTOCOL),
        "source_files": [{"path": path.relative_to(ROOT).as_posix(),
                          "sha256": _hash(path), "bytes": path.stat().st_size}
                         for path in (PROTOCOL, SOLVER, SCRIPT)],
        "positive_cases": positives,
        "positive_cases_passed": all(row["passed"] for row in positives),
        "negative_controls": negatives,
        "negative_controls_rejected": all(row["rejected"] for row in negatives),
        "bounds": {key: str(value) for key, value in bounds.items()},
        "finite_horizon_steps": sum(case["steps"] for case in cases),
        "boundaries": boundaries,
    }


def check_audit(saved: dict) -> dict:
    if not isinstance(saved, dict):
        raise ValueError("floating conformance audit must be an object")
    stamp = saved.get("recorded_at")
    try:
        timestamp = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
    except (AttributeError, ValueError) as exc:
        raise ValueError("floating conformance audit has no valid timestamp") from exc
    if timestamp.tzinfo is None or timestamp.utcoffset() is None:
        raise ValueError("floating conformance audit timestamp is naive")
    expected = evaluate()
    if {key: value for key, value in saved.items() if key != "recorded_at"} != expected:
        raise ValueError("floating conformance audit differs from protocol or source")
    return expected


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--write", action="store_true")
    action.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    current = evaluate()
    if args.write:
        if AUDIT.exists():
            raise FileExistsError(f"refusing to overwrite floating conformance audit: {AUDIT}")
        current["recorded_at"] = datetime.now(timezone.utc).isoformat()
        AUDIT.write_text(json.dumps(current, indent=2, sort_keys=True) + "\n",
                         encoding="utf-8", newline="\n")
    else:
        check_audit(json.loads(AUDIT.read_text(encoding="utf-8")))
    print(json.dumps({"status": current["status"],
                      "positive_cases_passed": current["positive_cases_passed"],
                      "negative_controls_rejected": current["negative_controls_rejected"],
                      "floating_implementation_proved": False}, sort_keys=True))


if __name__ == "__main__":
    main()
