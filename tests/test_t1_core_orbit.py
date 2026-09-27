"""Behavioral and receipt-tamper checks for the core T1 propagator."""

import copy
import json
from pathlib import Path

import pytest

from auditable_scientist.tools.numerical import hohmann_baseline
from auditable_scientist.tools.orbit_integrator import propagate_to_apoapsis
from scripts import verify_acceptance


ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("ratio", [1.12, 1.85, 2.6])
def test_new_radius_ratios_converge_without_given_flight_time(ratio: float) -> None:
    r1, mu = 149_597_870.7, 132_712_440_018.0
    coarse = propagate_to_apoapsis(r1, r1 * ratio, mu, steps=2048)
    fine = propagate_to_apoapsis(r1, r1 * ratio, mu, steps=4096)
    reference = hohmann_baseline(r1, r1 * ratio, mu).time_of_flight_s
    assert coarse["event_detected"] is True
    assert fine["event_detected"] is True
    assert abs(fine["event_time_s"] - reference) < abs(coarse["event_time_s"] - reference) / 4
    assert abs(fine["event_time_s"] / reference - 1) < 1e-9


def test_wrong_force_and_invalid_domains_fail_closed() -> None:
    inputs = (149_597_870.7, 227_939_134.0303053, 132_712_440_018.0)
    assert propagate_to_apoapsis(*inputs, steps=4096, gravity_sign=-1) == {
        "event_detected": False, "steps_executed": 4096,
    }
    for kwargs in ({"steps": 128}, {"gravity_sign": True}):
        with pytest.raises(ValueError):
            propagate_to_apoapsis(*inputs, **kwargs)
    with pytest.raises(ValueError):
        propagate_to_apoapsis(inputs[1], inputs[0], inputs[2])


@pytest.mark.parametrize("mutation", ["time", "negative", "scope", "source"])
def test_core_acceptance_rejects_changed_audit(monkeypatch: pytest.MonkeyPatch, mutation: str) -> None:
    original_load = verify_acceptance.load
    changed = copy.deepcopy(json.loads((ROOT / "artifacts/t1-core-orbit-audit.json").read_text(encoding="utf-8")))
    if mutation == "time":
        changed["rows"][0]["numerical_tof_days"] += 1
    elif mutation == "negative":
        changed["negative_control"]["event_detected"] = True
    elif mutation == "scope":
        changed["boundaries"]["real_data"] = True
    else:
        changed["source_files"][0]["sha256"] = "0" * 64

    def load(path: str) -> dict:
        return changed if path == "artifacts/t1-core-orbit-audit.json" else original_load(path)

    monkeypatch.setattr(verify_acceptance, "load", load)
    with pytest.raises(ValueError):
        verify_acceptance.verify_core_t1_orbit()
