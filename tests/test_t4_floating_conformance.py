"""Contract tests for the finite floating-conformance receipt."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts import verify_t4_floating_conformance as verifier

ROOT = Path(__file__).resolve().parents[1]


def test_floating_conformance_receipt_replays() -> None:
    saved = json.loads((ROOT / "artifacts/t4-floating-conformance-audit.json").read_text(encoding="utf-8"))
    expected = verifier.check_audit(saved)
    assert expected["positive_cases_passed"] is True
    assert expected["negative_controls_rejected"] is True
    assert expected["boundaries"]["floating_implementation_proved"] is False


def test_floating_conformance_rejects_boundary_promotion() -> None:
    saved = json.loads((ROOT / "artifacts/t4-floating-conformance-audit.json").read_text(encoding="utf-8"))
    saved["boundaries"]["floating_implementation_proved"] = True
    with pytest.raises(ValueError, match="differs"):
        verifier.check_audit(saved)


def test_floating_conformance_negative_controls_have_margin() -> None:
    saved = json.loads((ROOT / "artifacts/t4-floating-conformance-audit.json").read_text(encoding="utf-8"))
    errors = {row["solver"]: row["final_position_error"] for row in saved["negative_controls"]}
    assert set(errors) == {"explicit-euler", "perturbed-verlet"}
    assert all(error >= 1e-6 for error in errors.values())


def test_floating_conformance_rejects_wrong_solver_output(monkeypatch: pytest.MonkeyPatch) -> None:
    protocol = json.loads((ROOT / "docs/T4_FLOATING_CONFORMANCE_PROTOCOL.json").read_text(encoding="utf-8"))
    bounds = {key: verifier._exact(value) for key, value in protocol["bounds"].items()}
    monkeypatch.setattr(verifier, "_verlet", lambda _case: (0.0, 0.0, 0.0))
    observed = verifier._positive_case(protocol["cases"][0], bounds)
    assert observed["passed"] is False


def test_floating_conformance_rejects_noncanonical_rational() -> None:
    with pytest.raises(ValueError, match="noncanonical rational"):
        verifier._exact("2/4")
