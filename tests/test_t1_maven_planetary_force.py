"""Guard the Sun-relative force law and the saved scientific boundary."""

from __future__ import annotations

import copy
import math
from pathlib import Path
import sys

import pytest

from scripts import verify_acceptance


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from verify_t1_maven_planetary_force import (  # noqa: E402
    propagate, third_body_acceleration,
)


def test_planetary_tide_uses_indirect_sun_frame_term() -> None:
    position = (100_000_000.0, 0.0, 0.0)
    planet = (150_000_000.0, 0.0, 0.0)
    gm = 403_503.23562548019
    actual = third_body_acceleration(position, planet, gm)
    expected = gm * (1 / (planet[0]-position[0])**2 - 1 / planet[0]**2)
    assert math.isclose(actual[0], expected, rel_tol=1e-15)
    assert actual[1:] == (0.0, 0.0)
    assert third_body_acceleration((0.0, 0.0, 0.0), planet, gm) == (0.0, 0.0, 0.0)
    assert third_body_acceleration((0.0, 0.0, 0.0), planet, gm, indirect_sign=1)[0] > 0


def test_time_dependent_rk4_refines_against_constant_perturber() -> None:
    mu = 132_712_440_041.27942
    radius = 149_597_870.7
    speed = math.sqrt(mu / radius)
    initial = (radius, 0.0, 0.0, 0.0, speed, 0.0)
    gm = {10: mu, 3: 403_503.23562548019, 4: 42_828.375815756102}

    def position_at(body: int, _time: float) -> tuple[float, ...]:
        return (250_000_000.0, 0.0, 0.0) if body == 3 else (0.0, 300_000_000.0, 0.0)

    coarse = propagate(initial, 0.0, 86_400.0, 14_400.0, gm, position_at)
    fine = propagate(initial, 0.0, 86_400.0, 7_200.0, gm, position_at)
    finer = propagate(initial, 0.0, 86_400.0, 3_600.0, gm, position_at)
    assert math.dist(fine[:3], finer[:3]) < math.dist(coarse[:3], fine[:3])
    assert math.dist(fine[:3], finer[:3]) < 0.001


def test_acceptance_rejects_planetary_force_claim_promotion(
        monkeypatch: pytest.MonkeyPatch) -> None:
    original_load = verify_acceptance.load

    def tampered_load(path: str) -> dict:
        value = original_load(path)
        if path == "artifacts/t1-maven-planetary-force-snapshot.json":
            value = copy.deepcopy(value)
            value["scientific_boundaries"]["mission_validation"] = True
        return value

    monkeypatch.setattr(verify_acceptance, "load", tampered_load)
    with pytest.raises(ValueError, match="MAVEN planetary-force source"):
        verify_acceptance.verify_optional_t1_maven_planetary_force()
