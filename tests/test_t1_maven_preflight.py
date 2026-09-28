"""Independent RK4 preflight is checked against a closed-form orbit."""

from __future__ import annotations

import math
import copy
from pathlib import Path
import sys

import pytest
from scripts import verify_acceptance


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from verify_t1_maven_preflight import propagate, specific_energy  # noqa: E402


MU = 132_712_440_041.27942
RADIUS = 149_597_870.7


def test_sun_only_rk4_matches_closed_form_circular_arc() -> None:
    speed = math.sqrt(MU / RADIUS)
    initial = (RADIUS, 0.0, 0.0, 0.0, speed, 0.0)
    horizon = 86_400.0
    result = propagate(initial, MU, horizon, 600.0)
    angle = speed * horizon / RADIUS
    exact_position = (RADIUS * math.cos(angle), RADIUS * math.sin(angle), 0.0)
    exact_velocity = (-speed * math.sin(angle), speed * math.cos(angle), 0.0)
    assert math.dist(result[:3], exact_position) < 0.001
    assert math.dist(result[3:], exact_velocity) < 1e-9
    assert abs((specific_energy(result, MU) - specific_energy(initial, MU)) /
               specific_energy(initial, MU)) < 1e-10
    wrong_sign = propagate(initial, MU, horizon, 600.0, gravity_sign=-1)
    assert math.dist(wrong_sign[:3], exact_position) > 10_000


def test_rk4_rejects_nonintegral_or_unbounded_horizon() -> None:
    initial = (RADIUS, 0.0, 0.0, 0.0, 30.0, 0.0)
    with pytest.raises(ValueError, match="bounded exact"):
        propagate(initial, MU, 86_401.0, 600.0)
    with pytest.raises(ValueError, match="bounded exact"):
        propagate(initial, MU, 600.0 * 100_001, 600.0)


def test_preflight_acceptance_rejects_mission_validation_promotion(
        monkeypatch: pytest.MonkeyPatch) -> None:
    original_load = verify_acceptance.load

    def tampered_load(path: str) -> dict:
        value = original_load(path)
        if path == "artifacts/t1-maven-preflight-audit.json":
            value = copy.deepcopy(value)
            value["boundaries"]["mission_validation"] = True
        return value

    monkeypatch.setattr(verify_acceptance, "load", tampered_load)
    with pytest.raises(ValueError, match="MAVEN preflight source"):
        verify_acceptance.verify_optional_t1_maven_preflight()
