"""Core acceptance rejects inflated or altered optional T3 horizon receipts."""

from copy import deepcopy

import pytest

from scripts.verify_acceptance import load, verify_optional_t3_horizon_static


def test_saved_horizon_grid_passes_static_scope() -> None:
    result = verify_optional_t3_horizon_static()
    assert result["admitted_case_count"] == 2
    assert result["excluded_stress_case_count"] == 2
    assert result["pinned_scipy_recomputation_required"] is True


@pytest.mark.parametrize("mutation", [
    "source", "fine-error", "separation", "event", "budget", "scope", "grid",
    "boundary", "timestamp", "provider", "stress-admission", "source-normalization",
])
def test_horizon_grid_rejects_tampering(mutation: str) -> None:
    changed = deepcopy(load("artifacts/t3-horizon-grid-audit.json"))
    if mutation == "source":
        changed["source_files"][0]["sha256"] = "0" * 64
    elif mutation == "fine-error":
        changed["admitted_rows"][0]["fine_verlet_position_error"] = 2e-5
    elif mutation == "separation":
        changed["admitted_rows"][0]["sampled_minimum_pair_separation_ratio"] = 0.4
    elif mutation == "event":
        changed["admitted_rows"][0]["inward_threshold_event_count"] = 1
    elif mutation == "budget":
        changed["observed_budget"]["dop853_function_calls_total"] = 12001
    elif mutation == "scope":
        changed["scope"] = "validated long-horizon dynamics"
    elif mutation == "grid":
        changed["stress_grid"][0]["horizon_fraction"] = 0.75
    elif mutation == "boundary":
        changed["boundaries"]["chaotic_long_horizon_validated"] = True
    elif mutation == "timestamp":
        changed["recorded_at"] = "2026-09-27T09:09:23"
    elif mutation == "provider":
        changed["provider_environment"]["platform_and_packages"]["scipy"] = "0.0.0"
    elif mutation == "source-normalization":
        next(item for item in changed["source_files"] if item["path"] == "artifacts/t3-perturbed-audit.json")["normalization"] = "raw"
    else:
        changed["excluded_stress_rows"][0]["admission"] = "admitted"
    with pytest.raises(ValueError):
        verify_optional_t3_horizon_static(changed)
