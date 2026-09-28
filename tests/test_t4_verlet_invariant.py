"""Exact T4 Verlet invariant and negative-control tests."""

from __future__ import annotations

from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import verify_t4_verlet_invariant as verifier  # noqa: E402


def test_exact_verlet_certificate_passes_without_physical_claim() -> None:
    result = verifier.evaluate()
    assert result["status"] == "verified-exact-verlet-discrete-invariant-only"
    assert result["positive_certificate"]["residual_matrix"] == [["0", "0"], ["0", "0"]]
    assert result["negative_control"]["rejected"] is True
    assert result["boundaries"]["physical_model_validated"] is False


@pytest.mark.parametrize("mutation", ["positive_residual", "negative_admitted", "physical_claim", "source_hash", "timestamp"])
def test_certificate_rejects_mutation(mutation: str) -> None:
    audit = verifier.evaluate()
    audit["recorded_at"] = "2026-09-28T00:00:00+00:00"
    if mutation == "positive_residual":
        audit["positive_certificate"]["residual_matrix"][0][0] = "1"
    elif mutation == "negative_admitted":
        audit["negative_control"]["rejected"] = False
    elif mutation == "physical_claim":
        audit["boundaries"]["physical_model_validated"] = True
    elif mutation == "source_hash":
        audit["source_files"][0]["sha256"] = "0" * 64
    else:
        audit["recorded_at"] = "2026-09-28T00:00:00"
    with pytest.raises(ValueError):
        verifier.check_audit(audit)


def test_saved_certificate_passes() -> None:
    audit = verifier.evaluate()
    audit["recorded_at"] = "2026-09-28T00:00:00+00:00"
    assert verifier.check_audit(audit)["positive_certificate"]["positive_definite"] is True
