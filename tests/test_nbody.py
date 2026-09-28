"""Numerical and evidence-boundary checks for the symmetric T3 subtrack."""

import json
from math import hypot
from pathlib import Path

import pytest
from pydantic import ValidationError

from auditable_scientist.tracks.nbody import NBodyCase, _acceleration, evaluate_nbody_fixture, initial_state


ROOT = Path(__file__).resolve().parents[1]


def _cases() -> list[NBodyCase]:
    fixture = json.loads((ROOT / "examples/dynamics/nbody-fixture.json").read_text(encoding="utf-8"))
    return [NBodyCase.model_validate(row) for row in fixture["cases"]]


def test_equilateral_force_matches_analytic_centripetal_acceleration() -> None:
    for case in _cases():
        positions, _, omega = initial_state(case)
        acceleration = _acceleration(positions, case.masses, case.gravitational_constant)
        assert max(hypot(ax + omega**2 * x, ay + omega**2 * y) for (x, y), (ax, ay) in zip(positions, acceleration)) < 1e-12


def test_train_holdout_reference_and_negative_force() -> None:
    evaluation, receipt = evaluate_nbody_fixture(_cases())
    assert evaluation.passed and receipt.passed and receipt.negative_case_passed
    assert evaluation.max_rk4_position_error < evaluation.max_verlet_position_error
    assert evaluation.negative_repulsive_force_error > 0.1
    assert receipt.evidence_level == "validated-reproduction"
    assert "perturbed or nonintegrable multi-body validation" in receipt.blocked_gates


def test_invalid_mass_and_incomplete_splits_fail_closed() -> None:
    cases = _cases()
    with pytest.raises(ValidationError):
        NBodyCase.model_validate({**cases[0].model_dump(), "masses": [1, -1, 1]})
    with pytest.raises(ValueError, match="train and holdout"):
        evaluate_nbody_fixture(cases[:1])
