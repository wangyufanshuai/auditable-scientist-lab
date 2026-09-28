from auditable_scientist.tracks.causal_sensitivity import (
    candidate_set_hash,
    evaluate_context_sensitivity,
    load_builtin_cases,
)


def test_context_leaking_candidate_is_rejected_on_holdout() -> None:
    evaluation, receipt = evaluate_context_sensitivity(load_builtin_cases())

    assert evaluation.passed is True
    assert evaluation.baseline_holdout_rmse == 0.0
    assert evaluation.context_leakage_rejected is True
    assert evaluation.context_leak_holdout_rmse > 1.0
    assert receipt.negative_case_passed is True
    assert candidate_set_hash() == "736a67d5299697f211f3667a98173e921a7826aa87d3f48bbfb52fb0dfeb9d0a"
