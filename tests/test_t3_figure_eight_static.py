"""The published-orbit receipt cannot promote saved numerics into science."""

from __future__ import annotations

import copy

import pytest

from scripts import verify_acceptance


def test_figure_eight_saved_receipt_passes_bounded_static_check() -> None:
    result = verify_acceptance.verify_optional_t3_figure_eight_static()
    assert result["scenario_count"] == 3
    assert result["periods_max"] == 10
    assert result["pinned_scipy_recomputation_required"] is True
    assert result["scientific_holdout"] is False


@pytest.mark.parametrize("mutation", ["claim", "endpoint", "budget", "source"])
def test_figure_eight_static_rejects_promotion_or_mutation(mutation: str) -> None:
    receipt = copy.deepcopy(verify_acceptance.load("artifacts/t3-figure-eight-audit.json"))
    if mutation == "claim":
        receipt["scientific_boundaries"]["real_mission_validated"] = True
    elif mutation == "endpoint":
        receipt["rows"][2]["fine_rk4_endpoint_positions"][0][0] += 0.01
    elif mutation == "budget":
        receipt["observed_budget"]["dop853_rhs_calls_total"] -= 1
    else:
        receipt["source_files"][0]["sha256"] = "0"*64
    with pytest.raises(ValueError, match="T3 figure-eight"):
        verify_acceptance.verify_optional_t3_figure_eight_static(receipt)
