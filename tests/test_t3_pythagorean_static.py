"""Saved close-encounter evidence stays bound to its predeclared limits."""

from __future__ import annotations

import copy

import pytest

from scripts import verify_acceptance


def test_pythagorean_saved_receipt_passes_bounded_static_check() -> None:
    result = verify_acceptance.verify_optional_t3_pythagorean_static()
    assert result["scenario_count"] == 2
    assert result["pinned_scipy_recomputation_required"] is True
    assert result["chaotic_regime_validated"] is False


@pytest.mark.parametrize("mutation", ["claim", "endpoint", "event", "terminal", "budget", "source"])
def test_pythagorean_static_rejects_mutation(mutation: str) -> None:
    receipt = copy.deepcopy(verify_acceptance.load("artifacts/t3-pythagorean-audit.json"))
    if mutation == "claim":
        receipt["scientific_boundaries"]["chaotic_regime_validated"] = True
    elif mutation == "endpoint":
        receipt["rows"][1]["independent"]["samples"]["10.0"][0] += 0.01
    elif mutation == "event":
        receipt["rows"][0]["independent"]["event_time"] += 0.1
    elif mutation == "terminal":
        receipt["rows"][0]["independent"]["final_state"][2] += 0.01
    elif mutation == "budget":
        receipt["observed_budget"]["external_rhs_calls_total"] -= 1
    else:
        receipt["source_files"][0]["sha256"] = "0"*64
    with pytest.raises(ValueError, match="T3 Pythagorean"):
        verify_acceptance.verify_optional_t3_pythagorean_static(receipt)
