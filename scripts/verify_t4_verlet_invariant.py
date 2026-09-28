"""Verify an exact rational discrete invariant for one velocity-Verlet map."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from fractions import Fraction
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = ROOT / "docs/T4_VERLET_INVARIANT_PROTOCOL.json"
AUDIT = ROOT / "artifacts/t4-verlet-invariant-audit.json"
SOLVER = ROOT / "src/auditable_scientist/tracks/dynamics.py"
SOURCE_FILES = (PROTOCOL, SOLVER)


def _exact(value: str) -> Fraction:
    result = Fraction(value)
    if str(result) != value:
        raise ValueError(f"noncanonical rational: {value}")
    return result


def _matmul(left: list[list[Fraction]], right: list[list[Fraction]]) -> list[list[Fraction]]:
    return [[sum(left[i][k] * right[k][j] for k in range(len(right)))
             for j in range(len(right[0]))] for i in range(len(left))]


def _transpose(matrix: list[list[Fraction]]) -> list[list[Fraction]]:
    return [list(column) for column in zip(*matrix)]


def _sub(left: list[list[Fraction]], right: list[list[Fraction]]) -> list[list[Fraction]]:
    return [[left[i][j] - right[i][j] for j in range(len(left[0]))]
            for i in range(len(left))]


def _serial(matrix: list[list[Fraction]]) -> list[list[str]]:
    return [[str(value) for value in row] for row in matrix]


def _hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _expected_positive(protocol: dict) -> tuple[list[list[Fraction]], list[list[Fraction]], list[list[Fraction]]]:
    case = protocol["case"]
    omega = _exact(case["omega"])
    dt = _exact(case["dt"])
    q = omega * omega * dt * dt
    step = [
        [1 - q / 2, dt],
        [-omega * omega * dt * (1 - q / 4), 1 - q / 2],
    ]
    invariant = [[omega * omega * (1 - q / 4), Fraction(0)],
                 [Fraction(0), Fraction(1)]]
    return step, invariant, [[q]]


def evaluate() -> dict:
    protocol = json.loads(PROTOCOL.read_text(encoding="utf-8"))
    if (protocol.get("schema_version") != "t4-verlet-invariant-protocol-v1"
            or protocol.get("solver_source_sha256") != _hash(SOLVER)
            or protocol.get("boundaries") != {
                "exact_discrete_invariant_class": True,
                "floating_implementation_proved": False,
                "physical_model_validated": False,
                "general_formal_backend": False,
                "nonlinear_dynamics_proved": False,
                "real_data": False,
                "publication_ready": False,
                "claim_status": "unverified",
            }):
        raise ValueError("T4 Verlet protocol identity or boundary differs")
    step, invariant, q_box = _expected_positive(protocol)
    declared_step = [[_exact(value) for value in row] for row in protocol["case"]["step_matrix"]]
    declared_invariant = [[_exact(value) for value in row] for row in protocol["case"]["invariant_matrix"]]
    q = q_box[0][0]
    if (declared_step != step or declared_invariant != invariant
            or _exact(protocol["case"]["q"]) != q or not (0 < q < 4)):
        raise ValueError("T4 Verlet rational coefficients differ")
    residual = _sub(_matmul(_matmul(_transpose(step), invariant), step), invariant)
    omega = _exact(protocol["case"]["omega"])
    dt = _exact(protocol["case"]["dt"])
    euler = [[_exact(value) for value in row] for row in protocol["negative_control"]["step_matrix"]]
    expected_euler = [[Fraction(1), dt], [-omega * omega * dt, Fraction(1)]]
    if euler != expected_euler or protocol["negative_control"].get("solver") != "explicit-euler":
        raise ValueError("T4 negative control is not the declared explicit-Euler map")
    negative_residual = _sub(_matmul(_matmul(_transpose(euler), invariant), euler), invariant)
    if any(value != 0 for row in residual for value in row):
        raise ValueError("velocity-Verlet invariant residual is nonzero")
    if not any(value != 0 for row in negative_residual for value in row):
        raise ValueError("explicit-Euler negative control was admitted")
    return {
        "schema_version": "t4-verlet-invariant-audit-v1",
        "status": "verified-exact-verlet-discrete-invariant-only",
        "protocol_sha256": _hash(PROTOCOL),
        "source_files": [{"path": path.relative_to(ROOT).as_posix(),
                          "sha256": _hash(path), "bytes": path.stat().st_size}
                         for path in SOURCE_FILES],
        "positive_certificate": {
            "step_matrix": _serial(step),
            "invariant_matrix": _serial(invariant),
            "residual_matrix": _serial(residual),
            "positive_definite": True,
            "q": str(q),
        },
        "negative_control": {
            "solver": "explicit-euler",
            "residual_matrix": _serial(negative_residual),
            "rejected": True,
        },
        "boundaries": protocol["boundaries"],
    }


def check_audit(saved: dict) -> dict:
    """Reject changed receipt bytes and stale protocol or solver provenance."""

    if not isinstance(saved, dict):
        raise ValueError("T4 Verlet audit must be an object")
    stamp = saved.get("recorded_at")
    try:
        timestamp = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
    except (AttributeError, ValueError) as exc:
        raise ValueError("T4 Verlet audit has no valid timestamp") from exc
    if timestamp.tzinfo is None or timestamp.utcoffset() is None:
        raise ValueError("T4 Verlet audit timestamp is naive")
    expected = evaluate()
    if {key: value for key, value in saved.items() if key != "recorded_at"} != expected:
        raise ValueError("T4 Verlet audit differs from the exact protocol")
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
            raise FileExistsError(f"refusing to overwrite T4 Verlet audit: {AUDIT}")
        current["recorded_at"] = datetime.now(timezone.utc).isoformat()
        AUDIT.write_text(json.dumps(current, indent=2, sort_keys=True) + "\n",
                         encoding="utf-8", newline="\n")
    else:
        saved = json.loads(AUDIT.read_text(encoding="utf-8"))
        check_audit(saved)
    print(json.dumps({"status": current["status"], "q": current["positive_certificate"]["q"],
                      "negative_control_rejected": True, "physical_model_validated": False},
                     sort_keys=True))


if __name__ == "__main__":
    main()
