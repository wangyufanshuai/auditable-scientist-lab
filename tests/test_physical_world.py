"""Bounded causal-physics counterfactual and failure-path tests."""

import json
from math import sqrt
from pathlib import Path

import pytest
from pydantic import ValidationError

from auditable_scientist.tracks.physical_world import PhysicalCase, compare, evaluate_physical_fixture, simulate, standard_cases


ROOT = Path(__file__).resolve().parents[1]


def test_committed_hundred_case_suite_and_ignored_intervention_negative() -> None:
    fixture = json.loads((ROOT / "examples/causal/physical-fixture.json").read_text(encoding="utf-8"))
    cases = [PhysicalCase.model_validate(row) for row in fixture["cases"]]
    assert [case.model_dump(mode="json") for case in cases] == [case.model_dump(mode="json") for case in standard_cases()]
    result, receipt = evaluate_physical_fixture(cases)
    assert result.passed and receipt.passed and receipt.negative_case_passed
    assert (result.train_count, result.holdout_count) == (40, 60)
    assert result.query_counts == {"single": 60, "joint": 20, "policy": 20}
    assert result.ignored_intervention_holdout_rmse > 0.01
    assert "real physical intervention data and causal identification" in receipt.blocked_gates


def test_mass_friction_restitution_and_policy_have_declared_effects() -> None:
    cases = standard_cases()[:5]
    mass, friction, restitution, joint, policy = [compare(case) for case in cases]
    assert mass.final_x_effect_m < 0
    assert friction.counterfactual.first_post_impact_vx_m_s < friction.factual.first_post_impact_vx_m_s
    assert restitution.rebound_apex_effect_m > 0
    assert joint.rebound_apex_effect_m > 0
    assert joint.counterfactual.first_post_impact_vx_m_s < joint.factual.first_post_impact_vx_m_s
    assert policy.final_x_effect_m > 0
    assert all(result.common_initial_state == case.initial_state for result, case in zip((mass, friction, restitution, joint, policy), cases))


def test_closed_form_impact_and_noop_trajectory() -> None:
    case = standard_cases()[0]
    truth = simulate(case)
    noop = simulate(case, parameters=case.parameters, action=case.action)
    assert truth == noop
    assert truth.impact_count >= 1
    assert truth.first_impact_time_s == pytest.approx(sqrt(2 / case.parameters.gravity_m_s2))
    assert truth.first_rebound_apex_m == pytest.approx(case.parameters.restitution**2)
    assert truth.max_impact_energy_gain == 0


def test_invalid_intervention_and_missing_fields_fail_closed() -> None:
    case = standard_cases()[0].model_dump(mode="json")
    with pytest.raises(ValidationError):
        PhysicalCase.model_validate({**case, "intervention": {"query_type": "single", "parameter_updates": {"friction": 2}}})
    with pytest.raises(ValidationError):
        PhysicalCase.model_validate({**case, "initial_state": {"x_m": 0, "y_m": 1, "vx_m_s": 0}})
    with pytest.raises(ValidationError):
        PhysicalCase.model_validate({**case, "horizon_s": 0.5001})
    with pytest.raises(ValueError, match="100"):
        evaluate_physical_fixture(standard_cases()[:99])
