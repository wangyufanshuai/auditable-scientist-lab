from __future__ import annotations

import pytest

from auditable_scientist.tools import (
    check_expression_dimensions,
    compute_error_statistics,
    holdout_gate,
    hohmann_baseline,
)


def test_dimension_check_accepts_hohmann_time_expression() -> None:
    result = check_expression_dimensions(
        "pi*sqrt(((r1+r2)/2)^3/mu)",
        {"r1": "km", "r2": "km", "mu": "km^3/s^2"},
        expected_unit="s",
    )
    assert result.status == "valid"
    assert result.inferred_unit == "T^1"


def test_dimension_check_rejects_incompatible_addition() -> None:
    result = check_expression_dimensions("r1+t", {"r1": "km", "t": "s"})
    assert result.status == "invalid"
    assert "incompatible" in result.message


def test_hohmann_baseline_is_deterministic_and_positive() -> None:
    first = hohmann_baseline(149597870.7, 1.523679 * 149597870.7, 1.32712440018e11)
    second = hohmann_baseline(149597870.7, 1.523679 * 149597870.7, 1.32712440018e11)
    assert first.model_dump() == second.model_dump()
    assert 250 < first.time_of_flight_days < 300
    assert first.total_heliocentric_dv_km_s > 0
    with pytest.raises(ValueError, match="positive"):
        hohmann_baseline(0, 1, 1)


def test_error_statistics_and_holdout_gate_are_explicit() -> None:
    stats = compute_error_statistics([1, 2, 3], [1, 3, 2])
    assert stats.count == 3
    assert stats.mae == pytest.approx(2 / 3)
    assert stats.max_abs_error == 1
    passing = holdout_gate([1, 2], [1, 2], [3, 4], [3.01, 4.01], max_holdout_rmse=0.02)
    failing = holdout_gate([1, 2], [1, 2], [3, 4], [3.1, 4.1], max_holdout_rmse=0.02)
    assert passing.passed is True
    assert failing.passed is False
