"""Independent, standard-library checker for exact linear-invariant certificates."""

from __future__ import annotations

from datetime import datetime
from fractions import Fraction
from hashlib import sha256
import json
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
INPUT = ROOT / "artifacts/t4-linear-systems-input.json"
AUDIT = ROOT / "artifacts/t4-linear-formal-audit.json"
RATIONAL = re.compile(r"^-?(?:0|[1-9][0-9]*)(?:/[1-9][0-9]*)?$")
SYSTEM_KEYS = {
    "system_id", "state_names", "control_names", "transition_matrix", "control_matrix",
    "invariant_coefficients", "sample_state", "sample_control",
}
CERTIFICATE_KEYS = {
    "system_id", "state_dimension", "control_dimension", "residual_state_coefficients",
    "residual_control_coefficients", "sample_next_state", "sample_invariant_delta",
    "universal_conservation_proved",
}
SOURCE_PATHS = {
    "artifacts/t4-linear-systems-input.json",
    "scripts/verify_t4_linear_formal.py",
    "scripts/check_t4_linear_certificate.py",
    "src/auditable_scientist/tracks/proof.py",
    "docs/T4_LINEAR_INVARIANTS.md",
}


def exact(value: str) -> Fraction:
    if not isinstance(value, str) or not RATIONAL.fullmatch(value):
        raise ValueError(f"noncanonical rational syntax: {value!r}")
    number = Fraction(value)
    if str(number) != value:
        raise ValueError(f"rational is not reduced and canonical: {value!r}")
    return number


def _vector(values: list[str], length: int) -> list[Fraction]:
    if not isinstance(values, list) or len(values) != length:
        raise ValueError("vector dimension differs")
    return [exact(value) for value in values]


def _matrix(rows: list[list[str]], height: int, width: int) -> list[list[Fraction]]:
    if not isinstance(rows, list) or len(rows) != height:
        raise ValueError("matrix height differs")
    return [_vector(row, width) for row in rows]


def expected_certificate(system: dict) -> dict:
    if not isinstance(system, dict) or set(system) != SYSTEM_KEYS:
        raise ValueError("linear system has missing or unknown fields")
    state_names = system["state_names"]
    control_names = system["control_names"]
    if (not isinstance(state_names, list) or not isinstance(control_names, list)
            or not state_names or not control_names
            or any(not isinstance(name, str) or not name for name in [*state_names, *control_names])
            or len(set(state_names)) != len(state_names) or len(set(control_names)) != len(control_names)):
        raise ValueError("linear system has invalid state or control names")
    n, m = len(state_names), len(control_names)
    transition = _matrix(system["transition_matrix"], n, n)
    control = _matrix(system["control_matrix"], n, m)
    invariant = _vector(system["invariant_coefficients"], n)
    state = _vector(system["sample_state"], n)
    signal = _vector(system["sample_control"], m)
    residual_state = [sum(invariant[i] * transition[i][j] for i in range(n)) - invariant[j] for j in range(n)]
    residual_control = [sum(invariant[i] * control[i][j] for i in range(n)) for j in range(m)]
    next_state = [
        sum(transition[i][j] * state[j] for j in range(n))
        + sum(control[i][j] * signal[j] for j in range(m))
        for i in range(n)
    ]
    sample_delta = sum(invariant[i] * (next_state[i] - state[i]) for i in range(n))
    return {
        "system_id": system["system_id"],
        "state_dimension": n, "control_dimension": m,
        "residual_state_coefficients": [str(value) for value in residual_state],
        "residual_control_coefficients": [str(value) for value in residual_control],
        "sample_next_state": [str(value) for value in next_state],
        "sample_invariant_delta": str(sample_delta),
        "universal_conservation_proved": all(value == 0 for value in (*residual_state, *residual_control)),
    }


def check_audit(audit: dict, *, root: Path = ROOT) -> dict:
    input_path = root / INPUT.relative_to(ROOT)
    input_body = input_path.read_bytes()
    source = json.loads(input_body)
    systems = source.get("systems")
    if (source.get("schema_version") != "t4-linear-systems-input-v1"
            or not isinstance(systems, list) or len(systems) != 3
            or [item.get("system_id") for item in systems] != [
                "two-compartment-transfer", "three-compartment-exchange", "leaky-exchange-negative",
            ]):
        raise ValueError("linear-system input inventory differs")
    if (audit.get("schema_version") != "t4-linear-formal-audit-v1"
            or audit.get("status") != "verified-exact-linear-class-only"
            or audit.get("input_sha256") != sha256(input_body).hexdigest()
            or audit.get("boundaries") != {
                "exact_linear_invariant_class": True,
                "physical_model_validated": False,
                "nonlinear_dynamics_proved": False,
                "floating_implementation_proved": False,
                "nonnegative_state_for_all_controls": False,
                "general_formal_backend": False,
                "real_data": False,
                "publication_ready": False,
            }):
        raise ValueError("linear-invariant audit identity or scientific boundary differs")
    recorded_at = datetime.fromisoformat(audit["recorded_at"].replace("Z", "+00:00"))
    if recorded_at.tzinfo is None or recorded_at.utcoffset() is None:
        raise ValueError("linear-invariant audit timestamp is naive")
    source_files = audit.get("source_files", [])
    if len(source_files) != len(SOURCE_PATHS) or {item.get("path") for item in source_files} != SOURCE_PATHS:
        raise ValueError("linear-invariant source inventory differs")
    for item in source_files:
        path = (root / item["path"]).resolve()
        if not path.is_relative_to(root.resolve()) or not path.is_file():
            raise ValueError("linear-invariant source path is unsafe or missing")
        body = path.read_bytes()
        if item.get("sha256") != sha256(body).hexdigest() or item.get("bytes") != len(body):
            raise ValueError(f"linear-invariant source bytes differ: {item['path']}")
    expected = [expected_certificate(item) for item in systems]
    actual = audit.get("certificates")
    if not isinstance(actual, list) or any(not isinstance(item, dict) or set(item) != CERTIFICATE_KEYS for item in actual):
        raise ValueError("linear-invariant certificate shape differs")
    if actual != expected or [item["universal_conservation_proved"] for item in actual] != [True, True, False]:
        raise ValueError("linear-invariant coefficients or negative control differ")
    if actual[-1]["sample_invariant_delta"] != "-2":
        raise ValueError("leaky-system finite counterexample differs")
    return {"verified": True, "systems": len(actual), "positive_proofs": 2, "negative_controls": 1}


def main() -> None:
    audit = json.loads(AUDIT.read_text(encoding="utf-8"))
    print(json.dumps(check_audit(audit), sort_keys=True))


if __name__ == "__main__":
    main()
