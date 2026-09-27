"""Numerical behavior checks, run only when the optional SciPy backend is installed."""

from pathlib import Path
import sys

import pytest


pytest.importorskip("scipy")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from verify_t1_external_orbit import integrate_to_apoapsis  # noqa: E402


def test_apoapsis_event_recovers_analytic_time_across_radius_ratios() -> None:
    mu = 132712440018.0
    r1 = 149597870.7
    for ratio in (1.15, 1.5, 2.0):
        result = integrate_to_apoapsis(r1, r1 * ratio, mu)
        assert result["event_detected"] is True
        assert result["relative_tof_error"] < 1e-9
        assert result["relative_final_position_error"] < 1e-9


def test_repulsive_force_does_not_fake_the_apoapsis_event() -> None:
    result = integrate_to_apoapsis(149597870.7, 227939134.0303053, 132712440018.0, gravity_sign=-1)
    assert result["event_detected"] is False
