"""Fail-closed checks for the saved optional external-orbit receipt."""

import copy

import pytest

from scripts import verify_acceptance


@pytest.mark.parametrize("mutation", ["source-hash", "time-gate", "numeric-time", "real-data-overclaim", "missing-negative"])
def test_static_orbit_audit_rejects_tampering(monkeypatch: pytest.MonkeyPatch, mutation: str) -> None:
    original_load = verify_acceptance.load
    changed = copy.deepcopy(original_load("artifacts/t1-external-orbit-audit.json"))
    if mutation == "source-hash":
        changed["source_files"][0]["sha256"] = "0" * 64
    elif mutation == "time-gate":
        changed["rows"][0]["relative_tof_error"] = 2e-9
    elif mutation == "numeric-time":
        changed["rows"][0]["numerical_tof_days"] += 10
    elif mutation == "real-data-overclaim":
        changed["boundaries"]["real_data"] = True
    else:
        changed["negative_control"]["event_detected"] = True

    def load(path: str) -> dict:
        return changed if path == "artifacts/t1-external-orbit-audit.json" else original_load(path)

    monkeypatch.setattr(verify_acceptance, "load", load)
    with pytest.raises(ValueError):
        verify_acceptance.verify_optional_t1_orbit_static()
