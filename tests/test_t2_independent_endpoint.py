"""Independent endpoint calculation and fail-closed T2 audit checks."""

from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import sys

import pytest

from auditable_scientist.tracks import physical_world


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import verify_t2_independent_endpoint as endpoint_audit  # noqa: E402


def test_endpoint_estimator_does_not_call_grid_simulator(monkeypatch: pytest.MonkeyPatch) -> None:
    case = physical_world.PhysicalCase.model_validate(endpoint_audit.expected_varied_input()["cases"][4])
    reference = physical_world.compare(case)

    def forbidden(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("grid simulator was called by the independent estimator")

    monkeypatch.setattr(physical_world, "simulate", forbidden)
    factual, changed, effect = endpoint_audit.estimate_effect(case)
    assert abs(factual - reference.factual.states[-1]["x_m"]) < 1e-8
    assert abs(changed - reference.counterfactual.states[-1]["x_m"]) < 1e-8
    assert abs(effect - reference.final_x_effect_m) < 1e-8


@pytest.mark.parametrize("mutation", ["effect", "gate", "boundary", "source", "timestamp"])
def test_saved_audit_rejects_mutation(mutation: str) -> None:
    current = endpoint_audit.build_audit()
    saved = deepcopy(json.loads(endpoint_audit.AUDIT.read_text(encoding="utf-8")))
    if mutation == "effect":
        saved["rows"][0]["estimated_effect_m"] += 0.1
    elif mutation == "gate":
        saved["gates"]["effect_max_1e-8_m"] = False
    elif mutation == "boundary":
        saved["boundaries"]["real_intervention_data"] = True
    elif mutation == "source":
        saved["source_files"][0]["sha256"] = "0" * 64
    else:
        saved["recorded_at"] = "2026-09-27T08:53:38"
    with pytest.raises(ValueError):
        endpoint_audit.verify_saved(saved, current)


def test_varied_case_inventory_rejects_changed_input(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    changed = endpoint_audit.expected_varied_input()
    changed["cases"][0]["initial_state"]["y_m"] = 0.9
    fixture = tmp_path / "changed.json"
    fixture.write_text(json.dumps(changed), encoding="utf-8")
    monkeypatch.setattr(endpoint_audit, "VARIED_INPUT", fixture)
    with pytest.raises(ValueError, match="inventory differs"):
        endpoint_audit._load_cases()
