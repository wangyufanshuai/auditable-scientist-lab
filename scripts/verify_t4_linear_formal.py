"""Generate exact SymPy certificates for a bounded linear-invariant class."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path

import sympy
from sympy import Matrix, Rational

from check_t4_linear_certificate import AUDIT, INPUT, ROOT, check_audit


SOURCE_PATHS = (
    INPUT,
    Path(__file__).resolve(),
    ROOT / "scripts/check_t4_linear_certificate.py",
    ROOT / "src/auditable_scientist/tracks/proof.py",
    ROOT / "docs/T4_LINEAR_INVARIANTS.md",
)


def sympy_certificate(system: dict) -> dict:
    n = len(system["state_names"])
    m = len(system["control_names"])
    transition = Matrix([[Rational(value) for value in row] for row in system["transition_matrix"]])
    control = Matrix([[Rational(value) for value in row] for row in system["control_matrix"]])
    invariant = Matrix([[Rational(value) for value in system["invariant_coefficients"]]])
    state = Matrix([Rational(value) for value in system["sample_state"]])
    signal = Matrix([Rational(value) for value in system["sample_control"]])
    if (transition.shape != (n, n) or control.shape != (n, m)
            or invariant.shape != (1, n) or state.shape != (n, 1) or signal.shape != (m, 1)):
        raise ValueError("linear-system matrix dimensions differ")
    residual_state = invariant * transition - invariant
    residual_control = invariant * control
    next_state = transition * state + control * signal
    sample_delta = (invariant * (next_state - state))[0]
    return {
        "system_id": system["system_id"],
        "state_dimension": n, "control_dimension": m,
        "residual_state_coefficients": [str(value) for value in residual_state],
        "residual_control_coefficients": [str(value) for value in residual_control],
        "sample_next_state": [str(value) for value in next_state],
        "sample_invariant_delta": str(sample_delta),
        "universal_conservation_proved": all(value == 0 for value in [*residual_state, *residual_control]),
    }


def build_audit() -> dict:
    source = json.loads(INPUT.read_text(encoding="utf-8"))
    if source.get("schema_version") != "t4-linear-systems-input-v1":
        raise ValueError("linear-system input schema differs")
    certificates = [sympy_certificate(item) for item in source["systems"]]
    if ([item["universal_conservation_proved"] for item in certificates] != [True, True, False]
            or certificates[-1]["sample_invariant_delta"] != "-2"):
        raise ValueError("linear-invariant positive or negative cases differ")
    return {
        "schema_version": "t4-linear-formal-audit-v1",
        "status": "verified-exact-linear-class-only",
        "input_sha256": sha256(INPUT.read_bytes()).hexdigest(),
        "method": "SymPy exact rational matrix identity, independently checked with stdlib Fraction",
        "sympy_version": sympy.__version__,
        "certificates": certificates,
        "source_files": [
            {"path": path.relative_to(ROOT).as_posix(), "sha256": sha256(path.read_bytes()).hexdigest(), "bytes": path.stat().st_size}
            for path in SOURCE_PATHS
        ],
        "boundaries": {
            "exact_linear_invariant_class": True,
            "physical_model_validated": False,
            "nonlinear_dynamics_proved": False,
            "floating_implementation_proved": False,
            "nonnegative_state_for_all_controls": False,
            "general_formal_backend": False,
            "real_data": False,
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
    if args.write:
        current["recorded_at"] = datetime.now(timezone.utc).isoformat()
        AUDIT.write_text(json.dumps(current, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
        result = check_audit(current)
    else:
        saved = json.loads(AUDIT.read_text(encoding="utf-8"))
        result = check_audit(saved)
        recorded_at = saved.pop("recorded_at")
        if not recorded_at or datetime.fromisoformat(recorded_at).tzinfo is None or saved != current:
            raise ValueError("linear-invariant audit differs from current SymPy computation")
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
